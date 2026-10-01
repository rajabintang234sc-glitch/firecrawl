"""Safe spreadsheet and printable client-facing draft exports."""

import csv
import html
import io
from validation import CATEGORIES


def safe_csv(value):
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def export_csv(project, report):
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["RAB INTERNAL — ESTIMASI / WAJIB REVIEW VENDOR DAN PAJAK"])
    writer.writerow(["Event", safe_csv(project["event"]["name"])])
    writer.writerow(["Tanggal", project["event"]["date"], "Kota", safe_csv(project["event"]["city"])])
    writer.writerow([])
    writer.writerow(["ID", "Kategori", "Deskripsi", "Jenis biaya", "Volume", "Satuan", "Durasi", "Tarif satuan IDR", "Total IDR", "Status tarif", "Vendor", "Referensi", "DP vendor %"])
    for item in report["rab"]["items"]:
        writer.writerow([safe_csv(v) for v in [item["id"], CATEGORIES[item["category"]], item["name"], item["kind"],
                         item["quantity"], item["unit"], item["duration"], item["unitPrice"], item["total"],
                         item["confidence"], item["vendor"], item["reference"], item["advancePercent"]]])
    writer.writerow([])
    t, p = report["totals"], report["pricing"]
    for label, value in (("Biaya langsung", t["directCost"]), ("Overhead rincian", t["detailedOverhead"]),
                         ("Overhead alokasi (tidak ada di baris)", t["allocatedOverhead"]), ("HPP proyek full cost", t["hpp"]),
                         ("Cadangan risiko (bukan HPP)", t["contingency"]), ("Basis pricing", t["riskAdjustedCost"]),
                         ("Batas negosiasi sebelum PPN", p["floorPrice"]), ("Harga ideal sebelum PPN", p["recommendedPrice"]),
                         ("Harga aktif sebelum PPN", p["selectedPrice"]), ("PPN keluaran", p["vat"]),
                         ("Total invoice", p["invoiceTotal"]), ("Potongan PPh klien (kredit pajak)", p["withholding"]),
                         ("Penerimaan kas invoice", p["clientReceipt"]), ("Laba proyeksi setelah cadangan, sebelum PPh badan", p["projectedProfit"]),
                         ("Margin setelah cadangan %", p["marginPercent"])):
        writer.writerow([label, value])
    writer.writerow(["Aturan", "PPN vendor yang tidak dapat dikreditkan harus termasuk biaya input. PPN keluaran dan PPh dipotong klien tidak ditambahkan ke HPP."])
    return "\ufeff" + output.getvalue()


def export_proposal(project, report):
    esc = lambda value: html.escape(str(value), quote=True)
    rp = lambda value: "Rp " + f"{value:,.0f}".replace(",", ".")
    e, f, p = project["event"], project["finance"], report["pricing"]
    scope = "".join(f"<tr><td>{esc(CATEGORIES[i['category']])}</td><td>{esc(i['name'])}</td><td>{esc(i['quantity'])} {esc(i['unit'])} × {esc(i['duration'])}</td></tr>" for i in project["items"] if i["kind"] == "direct")
    return f"""<!doctype html>
<html lang="id"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Draft penawaran — {esc(e['name'])}</title>
<style>body{{font:15px/1.6 system-ui,sans-serif;color:#163b35;max-width:900px;margin:48px auto;padding:0 24px}}h1{{font-size:32px;line-height:1.2}}small{{color:#667873}}.warning{{padding:16px;background:#fff4dd;border:1px solid #ebd7a9;border-radius:8px}}table{{width:100%;border-collapse:collapse;margin:24px 0}}td,th{{text-align:left;padding:10px;border-bottom:1px solid #dce5df}}.summary{{margin-left:auto;width:420px}}.total{{font-weight:bold;font-size:20px}}button{{padding:10px 16px;border:0;background:#163b35;color:white;border-radius:8px;cursor:pointer}}@media print{{button{{display:none}}body{{margin:0}}thead{{display:table-header-group}}tr{{break-inside:avoid}}}}</style></head>
<body><small>PANGGUNG / DRAFT PENAWARAN</small><h1>{esc(e['name'])}</h1><p>{esc(e['city'])} · {esc(e['date'])} · {esc(e['attendees'])} peserta · {esc(e['eventDays'])} hari event</p>
<div class="warning"><strong>DRAFT — belum disetujui untuk dikirim.</strong> Quote, spesifikasi, ketersediaan vendor, izin, status dan tarif pajak, serta kontrak perlu dikonfirmasi. Laporan ini bukan faktur pajak atau kontrak mengikat.</div>
<h2>Ruang lingkup</h2><table><thead><tr><th>Area</th><th>Deliverable / kebutuhan</th><th>Volume × durasi</th></tr></thead><tbody>{scope}</tbody></table>
<table class="summary"><tr><td>Nilai penawaran sebelum PPN</td><td>{rp(p['selectedPrice'])}</td></tr><tr><td>PPN efektif input ({esc(f['vatPercent'])}%)</td><td>{rp(p['vat'])}</td></tr><tr class="total"><td>Total invoice</td><td>{rp(p['invoiceTotal'])}</td></tr></table>
<p>Rencana pembayaran: DP {esc(f['downPaymentPercent'])}% dari invoice; termin pelunasan harus disepakati dalam kontrak. Potongan PPh sesuai ketentuan dan bukti potong, jika berlaku, tidak mengurangi nilai jasa.</p>
<h2>Hal yang perlu disepakati</h2><ul><li>Spesifikasi, jam sewa, akses load-in/out, lembur, hak asset, deliverable creative, dan batas revisi.</li><li>Masa berlaku penawaran, jadwal pembayaran, pembatalan, force majeure, dan mekanisme change order.</li><li>Semua perubahan scope harus disetujui tertulis sebelum menambah biaya.</li></ul>
<p><small>Dibuat {esc(report['analyzedAt'])}. Seluruh harga template merupakan simulasi, bukan tarif pasar terverifikasi. Rincian HPP/margin internal tidak disertakan.</small></p><button id="print">Cetak / simpan PDF melalui browser</button><script>document.getElementById('print').addEventListener('click',()=>window.print());</script></body></html>"""
