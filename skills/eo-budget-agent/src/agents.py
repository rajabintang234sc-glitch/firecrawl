"""Six independent, inspectable domain agents. They never edit the shared snapshot."""

from datetime import date, timedelta
from math import ceil
from finance import dec, percent

AGENT_ORDER = ("rab", "hpp", "budget", "pricing", "creative", "operations")


def insight(level, code, title, description):
    return {"level": level, "code": code, "title": title, "description": description}


def finish(agent_id, name, role, summary, insights, **details):
    status = "blocked" if any(i["level"] == "critical" for i in insights) else "review" if any(i["level"] == "warning" for i in insights) else "complete"
    return {"id": agent_id, "name": name, "role": role, "summary": summary, "status": status,
            "insights": insights, **details}


def rab_agent(project, result, today):
    issues = []
    quality = result["quality"]
    if quality["unpricedCount"]:
        issues.append(insight("critical", "unpriced", "Ada biaya bernilai nol", f"{quality['unpricedCount']} baris belum memiliki harga. Konfirmasi apakah benar gratis atau belum dihitung."))
    mismatches = [i["name"] for i in project["items"] if i["quantityBasis"] == "attendees" and i["quantity"] != project["event"]["attendees"]]
    if mismatches:
        issues.append(insight("warning", "pax-mismatch", "Volume peserta perlu dicek", ", ".join(mismatches) + ". Ubah basis menjadi tetap jika volume berbeda memang disengaja."))
    days = project["event"]["eventDays"]
    duration_mismatches = [i["name"] for i in project["items"] if (i["durationBasis"] == "eventDays" and i["duration"] != days) or (i["durationBasis"] == "totalDays" and i["duration"] != days + project["event"]["setupDays"])]
    if duration_mismatches:
        issues.append(insight("warning", "duration-mismatch", "Periode sewa / crew perlu dicek", ", ".join(duration_mismatches)))
    issues.append(insight("info", "line-formula", "Volume × durasi × tarif", "Setiap baris dibulatkan ke rupiah terdekat; load-in/out harus tercakup di tarif atau periode sewa, bukan dihitung dua kali."))
    return finish("rab", "RAB Agent", "Estimator produksi", f"{quality['itemCount']} baris biaya dipetakan ke produksi, creative, dan management.", issues,
                  categoryCount=len(result["rab"]["categories"]))


def hpp_agent(project, result, today):
    issues, q = [], result["quality"]
    if q["pendingQuoteCount"]:
        issues.append(insight("warning", "quotes-pending", "Penawaran vendor belum lengkap", f"{q['pendingQuoteCount']} baris belum didukung quote yang baru dan berlaku untuk tanggal event. Tarif contoh bukan harga pasar."))
    if q["expiredCount"]:
        issues.append(insight("warning", "quotes-expired", "Ada quote kedaluwarsa", f"{q['expiredCount']} quote melewati masa berlaku. Minta penawaran baru."))
    if not result["totals"]["overhead"]:
        issues.append(insight("warning", "no-overhead", "Overhead belum dialokasikan", "Pastikan waktu tim internal, administrasi, utilitas, dan biaya usaha tidak terlewat."))
    if not project["finance"]["contingencyPercent"]:
        issues.append(insight("warning", "no-contingency", "Tidak ada cadangan risiko", "Review overtime, perubahan brief, cuaca, pembatalan, serta penggantian alat. Cadangan bukan laba."))
    issues.append(insight("info", "hpp-definition", "HPP proyek memakai full cost", "Biaya langsung + overhead. Cadangan risiko ditampilkan terpisah; PPN keluaran dan PPh dipotong klien bukan komponen HPP."))
    return finish("hpp", "HPP Agent", "Cost controller", f"{q['verifiedCostPercent']:.0f}% nilai biaya didukung quote aktif; overhead dihitung satu kali.", issues,
                  verifiedCostPercent=q["verifiedCostPercent"])


def budget_agent(project, result, today):
    b, p = result["budget"], result["pricing"]
    issues = []
    floor = next(s for s in p["scenarios"] if s["id"] == "floor")
    floor_budget = floor["invoiceTotal"] if b["includesVat"] else floor["price"]
    if b["recommendedGap"]:
        level = "critical" if floor_budget > b["clientBudget"] else "warning"
        issues.append(insight(level, "budget-gap", "Budget belum mendukung harga ideal", "Naikkan budget atau negosiasikan scope/vendor. Jangan menghilangkan safety, menghapus overhead, atau menyamarkan margin."))
    else:
        issues.append(insight("success", "budget-fits", "Harga ideal masuk budget", "Kecukupan ini bersifat simulasi sampai quote dan pajak terkonfirmasi."))
    if not b["offerFits"]:
        issues.append(insight("warning", "offer-over-budget", "Penawaran aktif melebihi budget", "Bandingkan pada basis pajak yang sama: termasuk atau sebelum PPN."))
    if not b["clientBudget"]:
        issues.append(insight("warning", "no-budget", "Budget klien belum diisi", "Isi plafon budget agar analisis kelayakan bermakna."))
    return finish("budget", "Budget Agent", "Kelayakan & scope", "Harga ideal sesuai plafon klien." if b["recommendedFits"] else "Ada gap budget; revisi scope perlu persetujuan.", issues,
                  scopeOptions=b["scopeOptions"], maximumHppAtTarget=b["maximumHppAtTarget"])


def pricing_agent(project, result, today):
    f, p = project["finance"], result["pricing"]
    issues = []
    if p["marginPercent"] is None:
        issues.append(insight("critical", "zero-revenue", "Harga jual belum dapat ditentukan", "Lengkapi biaya dan harga sebelum menerbitkan proposal."))
    elif p["selectedPrice"] < p["floorPrice"]:
        issues.append(insight("critical", "below-floor", "Harga di bawah batas negosiasi", "Margin minimum setelah cadangan tidak terpenuhi. Butuh perubahan scope atau persetujuan pengecualian bisnis."))
    elif dec(p["selectedPrice"] - result["totals"]["riskAdjustedCost"]) * 100 < dec(p["selectedPrice"]) * dec(f["targetMarginPercent"]):
        issues.append(insight("warning", "below-target", "Margin di bawah target", "Penawaran masih di atas batas minimum, tetapi belum mencapai target perusahaan."))
    else:
        issues.append(insight("success", "margin-ok", "Margin target terjaga", "Rumus harga = (HPP + cadangan) ÷ (1 − margin). Ini margin penjualan, bukan markup biaya."))
    if not f["taxVerified"] or f["taxStatus"] == "unconfirmed":
        issues.append(insight("warning", "tax-unconfirmed", "Status dan pajak belum dikonfirmasi", "PPN efektif, status PKP, pemotongan, serta basis PPh harus ditinjau bagian pajak. Default 0% berarti belum diasumsikan, bukan bebas pajak."))
    if f["taxStatus"] == "pkp" and f["vatPercent"] == 0:
        issues.append(insight("warning", "pkp-zero-vat", "PKP dengan PPN 0% perlu review", "Jangan memakai 0% tanpa memastikan dasar perlakuan pajak transaksi."))
    issues.append(insight("info", "market-not-verified", "Wajar secara biaya, belum tervalidasi pasar", "Skenario hanya mengubah margin untuk scope yang sama. Uji terhadap penawaran pembanding dengan spesifikasi setara; tidak ada standar margin industri yang dipaksakan."))
    return finish("pricing", "Pricing Agent", "Margin & penawaran", "Tiga skenario harga dengan margin, pajak, dan batas negosiasi yang transparan.", issues)


def creative_agent(project, result, today):
    event = project["event"]
    tags = {tag for item in project["items"] for tag in item["tags"]}
    issues = []
    if "design" not in tags:
        issues.append(insight("warning", "creative-scope", "Scope creative belum terpetakan", "Pastikan konsep, key visual, art direction, revisi, dan approval klien tertulis."))
    if "video" not in tags:
        issues.append(insight("warning", "documentation-scope", "Dokumentasi belum terpetakan", "Tentukan deliverable, format, hak penggunaan, waktu editing, dan indikator keberhasilan."))
    ideas = {
        "corporate": ["Bangun narasi satu tema untuk opening, sesi utama, dan closing.", "Gunakan desain modular untuk signage dan backdrop, tanpa mengurangi keselamatan.", "Pisahkan approval key visual, script MC, dan rundown sebelum technical meeting."],
        "launch": ["Prioritaskan momen reveal, product storytelling, dan hasil konten untuk kanal brand.", "Uji sinkronisasi motion, audio cue, pencahayaan, serta rehearsal bersama talent.", "Batasi jumlah revisi dan tetapkan hak penggunaan musik, footage, serta asset brand."],
        "activation": ["Rancang alur pengunjung, titik interaksi, antrean, dan aksesibilitas sejak awal.", "Gunakan kit creative modular untuk deployment lintas hari dan lokasi.", "Tetapkan KPI interaksi/lead dengan persetujuan penggunaan data peserta."],
    }[event["type"]]
    creative_total = sum(i["total"] for i in result["rab"]["items"] if i["category"] == "creative" and i["kind"] == "direct")
    issues.append(insight("info", "creative-deliverables", "Value creative harus terdefinisi", "Pisahkan biaya konsep, produksi asset, lisensi, dan revisi. Harga premium memerlukan deliverable tambahan yang disepakati, bukan sekadar menaikkan margin."))
    return finish("creative", "Creative Agent", "Konsep & value", f"Alokasi creative {percent(creative_total, result['totals']['directCost']) or 0:.1f}% dari biaya langsung.", issues,
                  ideas=ideas, creativeCost=creative_total)


def operations_agent(project, result, today):
    event, cash = project["event"], result["cashflow"]
    tags = {tag for item in project["items"] for tag in item["tags"]}
    issues = []
    for required, label in (("power", "Backup daya & distribusi listrik"), ("safety", "Safety & pengamanan"), ("medical", "Kesiapan medis")):
        if required not in tags:
            issues.append(insight("critical", f"missing-{required}", f"{label} belum terpetakan", "Jangan memangkas kebutuhan ini untuk mengejar budget. Review dengan vendor/venue yang kompeten."))
    if "permits" not in tags:
        issues.append(insight("warning", "permits-review", "Izin, asuransi, dan ketentuan venue perlu review", "Kebutuhan bergantung pada kota, venue, peserta, jenis aktivitas, dan kebijakan setempat."))
    if cash["fundingGap"]:
        issues.append(insight("warning", "working-capital", "Ada kebutuhan modal sebelum event", "DP neto belum menutup uang muka vendor + overhead alokasi + cadangan. Negosiasikan termin atau siapkan modal kerja."))
    if event["environment"] in {"outdoor", "hybrid"}:
        issues.append(insight("warning", "weather-plan", "Siapkan rencana cuaca", "Review penutup alat, wind load, grounding, drainase, rute evakuasi, serta batas penghentian acara dengan tenaga ahli."))
    crew_count = sum(i["quantity"] for i in project["items"] if "crew" in i["tags"])
    heuristic = ceil(event["attendees"] / 50)
    if crew_count < heuristic:
        issues.append(insight("warning", "crew-review", "Kapasitas crew perlu ditinjau", f"Heuristik internal 1 crew per 50 peserta menghasilkan {heuristic} crew. Bukan standar keselamatan; validasi role, shift, venue, dan kompleksitas."))
    show_date = date.fromisoformat(event["date"])
    phases = [(-30, "Brief & kickoff", "Account / Producer", "Scope, KPI, plafon budget, dan kontrak klien."),
              (-21, "Creative lock", "Creative Lead", "Key visual, storyboard, revisi, dan hak asset."),
              (-14, "Vendor & PO lock", "Production / Finance", "Quote aktif, spesifikasi, DP, dan alternatif vendor."),
              (-7, "Technical meeting", "Show Director", "Rundown, cue sheet, listrik, crowd plan, dan safety."),
              (-event["setupDays"], "Load-in & rehearsal", "Production Manager", "Uji peralatan, akses vendor, checklist, dan briefing crew."),
              (0, "Show day", "Show Director / All Leads", "Jalankan rundown, incident log, dan approval perubahan."),
              (event["eventDays"] + 7, "Rekonsiliasi & evaluasi", "Finance / Producer", "Faktur, bukti potong, realisasi HPP, KPI, dan pembelajaran tarif.")]
    timeline = [{"offsetDays": offset, "date": (show_date + timedelta(days=offset)).isoformat(),
                 "title": title, "owner": owner, "deliverable": deliverable,
                 "pastDue": show_date + timedelta(days=offset) < today}
                for offset, title, owner, deliverable in phases]
    return finish("operations", "Operations Agent", "Produksi & cashflow", "Jadwal produksi, kebutuhan modal kerja, dan risiko eksekusi dipetakan.", issues,
                  timeline=timeline, crewHeuristic=heuristic)


AGENTS = {"rab": rab_agent, "hpp": hpp_agent, "budget": budget_agent, "pricing": pricing_agent,
          "creative": creative_agent, "operations": operations_agent}
