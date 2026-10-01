# Panggung — EO Budget Multi-Agent

Workspace berbahasa Indonesia untuk **budget, RAB, HPP, harga jual, creative, produksi, dan management Event Organizer**. Dapat langsung dijalankan tanpa API key atau dependency Python tambahan. Tidak mengubah API inti Firecrawl.

> **Batas yang penting:** enam agent ini merupakan spesialis **rule-based**, bukan LLM. Tarif template adalah angka ilustrasi, **bukan tarif pasar Indonesia 2026 yang sudah disurvei**. Sistem menghasilkan harga yang masuk akal secara biaya/margin; validasi pasar tetap membutuhkan penawaran vendor dan pembanding dengan scope setara. Jangan kirim draft tanpa review manusia.

## Menjalankan dashboard

Dari root repository:

```bash
python3 skills/eo-budget-agent/src/server.py --host 0.0.0.0 --port 8080
```

Buka preview port **8080** di Arena, atau alamat server pada lingkungan Anda. UI dan API menggunakan origin yang sama; seluruh request browser memakai URL relatif. Tidak ada API key atau pemanggilan backend `localhost` dalam kode browser.

### Yang bisa dilakukan

- Mulai dari **corporate gathering**, **product launch**, atau **brand activation**.
- Edit kota, tanggal, indoor/outdoor/hybrid, peserta, hari setup, dan hari event.
- Item dengan basis peserta/hari ikut menyesuaikan; item tetap tidak berubah. Perubahan brief membatalkan status quote untuk dikonfirmasi ulang.
- Edit RAB, tambah/hapus item, cari/filter kategori, klasifikasikan esensial/fleksibel/opsional, serta isi DP vendor dan bukti penawaran.
- Hitung overhead, HPP full cost, cadangan, batas negosiasi, harga ideal, pajak, margin, dan gap modal kerja.
- Lihat temuan enam agent, ide creative, risiko operasional, dan jadwal produksi.
- Catat realisasi **tarif per satuan**; review usulan pembelajaran tanpa mengganti harga secara diam-diam.
- Export **CSV internal**, **draft penawaran HTML** (buka lalu cetak/simpan PDF dari browser), dan **backup JSON**. Import backup divalidasi dan dihitung ulang di server.

## Agent simultan

```text
Brief + input -> validasi -> snapshot biaya immutable (Decimal)
                              |-- RAB Agent        : volume, durasi, kebutuhan produksi
                              |-- HPP Agent        : full cost, quote, overhead, cadangan
                              |-- Budget Agent     : plafon, gap, review scope non-esensial
                              |-- Pricing Agent    : margin, floor, invoice, pajak
                              |-- Creative Agent   : konsep, asset, deliverable, value
                              `-- Operations Agent : safety, crew, timeline, modal kerja
                            -> coordinator -> review manusia
```

Keenam agent dijadwalkan dengan `ThreadPoolExecutor` terhadap snapshot yang sama. Kalkulasi uang dilakukan **sekali**, bukan enam jawaban yang berbeda. Ini konkurensi tugas rule-based; bukan klaim percepatan CPU atau enam panggilan model AI. Pembelajaran dijalankan setelah koordinasi.

## Rumus dan perlakuan biaya

1. **Total baris** = volume × durasi × tarif; dibulatkan ke rupiah terdekat (`Decimal`, half-up).
2. **HPP proyek full cost** = biaya langsung + overhead. Dalam aplikasi ini HPP adalah definisi manajemen proyek, bukan otomatis klasifikasi HPP laporan keuangan badan.
3. **Overhead**: pilih rincian per baris **atau** persentase biaya langsung. Menggunakan keduanya ditolak untuk mencegah penghitungan ganda.
4. **Cadangan risiko** = HPP × persentase cadangan, **ditampilkan terpisah** dari HPP. Basis pricing = HPP + cadangan.
5. **Harga jual** = basis pricing ÷ (1 − margin target). Harga dibulatkan **ke atas** sesuai kelipatan pilihan. Margin bukan markup; fee EO tidak ditambahkan lagi di atas harga ini.
6. **Laba proyeksi** = harga sebelum PPN − basis pricing, sebelum pajak penghasilan badan. Cadangan diasumsikan terpakai penuh secara konservatif; aktual dapat berbeda.
7. **PPN keluaran** = harga jual × tarif efektif input; bukan omzet/laba/HPP. PPN vendor yang dapat dikreditkan harus dikeluarkan dari biaya input; pajak vendor yang tidak dapat dikreditkan harus termasuk biaya input.
8. **PPh dipotong klien** = harga sebelum PPN × porsi basis pemotongan × tarif input. Simulasi memperlakukannya sebagai kredit pajak: mengurangi kas, **bukan** menambah HPP atau mengurangi laba proyek. Tidak melakukan gross-up otomatis.
9. Budget yang termasuk PPN dibandingkan dengan invoice; budget sebelum PPN dibandingkan dengan harga sebelum PPN.
10. **Kebutuhan pra-event** = DP biaya per baris + seluruh overhead alokasi + seluruh cadangan. Kas DP tersedia dihitung setelah pemotongan PPh dan tanpa PPN. Ini simulasi satu termin, **bukan** jadwal akuntansi/kas harian.

### Contoh matematika, bukan harga pasar

Biaya langsung Rp100 juta, overhead 10%, cadangan 10%:

- HPP Rp110 juta; cadangan Rp11 juta; basis pricing Rp121 juta.
- Margin target 25% menghasilkan Rp161.333.333,33, **bukan** Rp151.250.000 (markup 25%).
- Pembulatan ke Rp100.000 menghasilkan harga ideal **Rp161.400.000 sebelum PPN**.

Margin minimum 15%, target 25%, cadangan 7,5%, dan overhead 8% di template merupakan **asumsi demo yang bisa diedit**, bukan rekomendasi universal industri.

## Pajak: konfigurasi, bukan keputusan otomatis

Default PPN/PPh **0%** dan status **belum dikonfirmasi** berarti belum diasumsikan, bukan menyatakan bebas pajak. Status non-PKP dengan PPN > 0 ditolak. Perubahan status/tarif/basis membatalkan checkbox review pajak.

Referensi awal:

- Artikel DJP tentang PMK 131/2024 menjelaskan mekanisme tarif efektif 12% × 11/12 dalam konteks yang dibahas, dengan pengecualian untuk perlakuan tertentu. Sumber 6 Januari 2025: [1](https://pajak.go.id/index.php/en/node/113453).
- DDTC membahas PPh 23 atas jasa EO, tarif 2% atas jumlah bruto tidak termasuk PPN, serta pengecualian basis pengadaan/pembayaran pihak ketiga/reimbursement yang memerlukan bukti. Sumber 14 Oktober 2024: [1](https://news.ddtc.co.id/berita/nasional/1806174/jasa-event-organizer-kena-pph-pasal-23-begini-ketentuannya).

**Periksa peraturan terbaru, bentuk badan, status PKP, objek transaksi, faktur, dan basis pajak bersama penanggung jawab pajak.** Aplikasi ini bukan penerbit faktur pajak, mesin kepatuhan, atau modul pajak vendor/talent/venue yang lengkap.

## Pembelajaran / pengembangan otomatis yang terkendali

Kebijakan di [`config/policy.json`](config/policy.json):

- Minimal **3 event ID berbeda**; mencatat ulang satu event memperbarui observasi, bukan menggandakan sampel.
- Hanya observasi ≤180 hari dengan item ID, spesifikasi, satuan, kota, dan jenis event yang sama.
- Median realisasi dipakai sebagai pusat, lalu `tarif usulan = tarif lama + 25% × (median − tarif lama)`.
- Deviasi median >25%, sebaran >50%, atau harga nol menahan penerapan; perlu review manual/pemisahan spesifikasi.
- Proposal tidak pernah diterapkan oleh kalkulasi biasa. **Review & terapkan** mengirim ID proposal ke server, yang menghitung ulang kelayakan dan menolak proposal stale/tampered.
- Penerapan batch atomic, membuat audit lokal, dan membatalkan quote lama. Harga baru tetap **estimasi**.

Sistem tidak mencatat estimasi sebagai realisasi otomatis, tidak mengeksekusi instruksi halaman web, dan tidak mengubah kode sendiri. Untuk menambah kemampuan agent melalui coding agent, gunakan [`references/automatic-development.md`](references/automatic-development.md): usulkan perubahan + regression test, verifikasi, lalu review manusia.

## Riset pasar opsional dengan Firecrawl

Riset adalah discovery sumber vendor, **bukan** scraping harga yang langsung disahkan. Endpoint backend memakai `/v2/search`, hasil dibatasi 5 sumber dan selalu ditandai belum terverifikasi. Referensi tidak dimasukkan ke pembelajaran atau harga otomatis.

Administrator dapat memasang melalui environment/secret manager:

```bash
export EO_ENABLE_RESEARCH=1
# Pasang FIRECRAWL_API_KEY lewat secret manager atau environment server.
# Opsional: FIRECRAWL_API_URL untuk deployment Firecrawl sendiri.
python3 skills/eo-budget-agent/src/server.py --host 0.0.0.0 --port 8080
```

Kalkulasi tetap berfungsi tanpa key. Riset berpotensi memakai kredit dan hanya dipanggil ketika pengguna menekan tombol. Adapter telah diuji dengan transport mock; **panggilan live belum diverifikasi tanpa key**. Untuk deployment publik berbayar, wajib tambahkan autentikasi, otorisasi, dan rate limit sebelum mengaktifkan riset.

## CLI / integrasi

```bash
# Laporan JSON ke stdout
python3 skills/eo-budget-agent/src/cli.py

# Input proyek sendiri + export
python3 skills/eo-budget-agent/src/cli.py \
  --input skills/eo-budget-agent/data/sample-project.json \
  --format csv --output skills/eo-budget-agent/artifacts/rab.csv
```

API JSON:

| Endpoint | Kegunaan |
| --- | --- |
| `GET /api/health` | Liveness |
| `GET /api/bootstrap` | Template, kebijakan, tanggal server, status riset |
| `POST /api/analyze` | Body proyek → proyek ternormalisasi + report |
| `POST /api/learning/apply` | `{project, proposalIds}` → revision + audit + report |
| `POST /api/export` | `{project, format: "csv" atau "proposal"}` → download |
| `POST /api/market/search` | `{query, city}` → sumber vendor, jika diaktifkan |

Lihat [`data/sample-project.json`](data/sample-project.json) dan [`references/input-and-validation.md`](references/input-and-validation.md) untuk kontrak input. API membatasi body 1 MB dan menolak angka non-finite, harga negatif, ID duplikat, quote tanpa bukti, serta input lintas origin.

## Pengujian

```bash
python3 -m unittest discover -s skills/eo-budget-agent/tests -v
node --check skills/eo-budget-agent/web/app.js
```

Browser E2E opsional (server sudah berjalan di port 8080):

```bash
cd skills/eo-budget-agent
npm ci
npx playwright install chromium
npm run test:ui
# Opsional: EO_TEST_BASE_URL=http://server:port npm run test:ui
# Jika browser sudah terpasang: EO_TEST_BROWSER_PATH=/path/chromium npm run test:ui
```

Test mencakup happy/failure paths API, margin vs markup, pembulatan, VAT/PPh, HPP/cadangan, cashflow, quote stale, snapshot paralel, anti-duplikasi pembelajaran, atomic apply, ekspor aman, input UI, import/export, persistence, dan tampilan mobile.

## Batas deployment

- Server `http.server` ditujukan untuk **preview/prototipe**, bukan production multi-tenant.
- Input aktif, observasi, dan audit hanya disimpan di `localStorage` browser ini. Tidak ada database, akun, sinkronisasi tim, atau histori semua proyek. Buat backup JSON sebelum mengganti proyek/perangkat.
- Semua data observasi/bukti/audit berasal dari pengguna dan belum diautentikasi; audit lokal **tidak tamper-proof**. Quote “aktif” berarti memenuhi pemeriksaan tanggal/metadata, bukan verifikasi legal terhadap dokumen.
- Tidak mengelola invoice legal, PPN masukan, PPh vendor, depresiasi, pajak badan, multi-currency, ticket revenue, pembayaran nyata, PO nyata, atau pemesanan vendor.
- Timeline dan staffing merupakan draft/heuristik, bukan sertifikasi keselamatan. Gunakan tenaga produksi/safety yang kompeten.
- Sebelum production: database + migrasi, auth/RBAC, audit append-only, enkripsi/backup, request/rate limits, reverse proxy, jadwal kas multi-termin, pengujian pajak, dan approval workflow resmi.
