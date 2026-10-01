# Kontrak input dan validasi

Contoh lengkap yang dapat dieksekusi: [`../data/sample-project.json`](../data/sample-project.json). Semua nilai uang dalam IDR, tanpa pemisah ribuan. Versi schema **1**.

## Struktur

```text
schemaVersion: 1
 event:
   id, name, type, city, attendees, eventDays, setupDays, date, environment
 finance:
   clientBudget, budgetIncludesVat, overheadPercent, contingencyPercent,
   targetMarginPercent, minimumMarginPercent, vatPercent, taxStatus,
   taxVerified, withholdingPercent, withholdingBasePercent,
   downPaymentPercent, offerPrice, rounding
 items[]:
   id, name, category, quantity, unit, duration, unitPrice,
   kind, priority, quantityBasis, durationBasis, advancePercent,
   confidence, vendor, reference, verifiedAt, validUntil, tags,
   actualUnitPrice
 observations[]:
   itemId, eventId, eventType, city, unit, specification,
   unitPrice, recordedAt
 audit[]:
   itemId, proposalId, previousPrice, newPrice, sampleCount, reviewedAt
```

- `type`: `corporate`, `launch`, `activation`.
- `environment`: `indoor`, `outdoor`, `hybrid`.
- `category`: `production`, `creative`, `management`, `venue`, `hospitality`, `talent`, `logistics`, `safety`.
- `kind`: `direct` atau `overhead`. Jika ada baris overhead, persentase overhead harus **0**.
- `priority`: `essential`, `flexible`, `optional`. Safety tidak menjadi opsi pemotongan otomatis, meskipun ditandai opsional.
- `quantityBasis`: `fixed` atau `attendees`; `durationBasis`: `fixed`, `eventDays`, `totalDays`. Basis membantu scaling UI; engine tetap menggunakan volume/durasi input eksplisit dan melaporkan mismatch.
- `confidence`: `estimate`, `quote`, `contract`. Quote/contract wajib vendor, referensi, dan tanggal verifikasi tidak di masa depan.
- Quote aktif: usia verifikasi ≤30 hari dan masa berlaku mencakup tanggal event. Kontrak tanpa expiry dianggap terikat pada event yang dimasukkan pengguna; tidak ada verifikasi dokumen otomatis.
- `reference`: nomor dokumen atau URL, sebagai metadata; backend tidak mengunjungi URL input ini.
- `actualUnitPrice`: `null` berarti belum diketahui; **0 berbeda dari null**. Nilai ini tidak otomatis menjadi observasi sebelum pengguna mencatatnya.
- `observations`/`audit` opsional, dinormalisasi ke array kosong. Riwayat pembelajaran harus sebanding sampai nama/spesifikasi item, bukan sekadar kategori.
- `offerPrice: 0` memakai harga ideal otomatis. Nilai manual positif mengaktifkan simulasi penawaran itu.
- `withholdingBasePercent`: porsi nilai jasa sebelum PPN yang menjadi basis pemotongan, bukan faktor DPP PPN.
- `rounding`: 1, 1.000, 10.000, 50.000, 100.000, atau 1.000.000 rupiah.

## Batas

1–250 baris; 1–100.000 peserta; 1–30 hari show dan 0–30 hari setup; tarif/budget ≤Rp1 triliun; total per baris ≤Rp1.000 triliun. Budget/harga penawaran harus rupiah bulat; volume/durasi/tarif mendukung maksimal 6 desimal. Margin <80%, minimum ≤target. Semua angka wajib finite/non-negatif; volume/durasi >0.

Tanggal format `YYYY-MM-DD` dengan kalender valid, tahun 2000–2100. ID alfanumerik ditambah `._:-`, maksimal 80 karakter; ID item unik. Riwayat maksimal 2.000 observasi, unik per event/item; audit lokal maksimal 500 revisi.

API menolak input tidak valid dengan HTTP **422**, JSON rusak dengan **400**, tipe body salah dengan **415**, body >1 MB dengan **413**, dan origin berbeda dengan **403**. Riset tidak aktif: **503**; upstream bermasalah: **502**; slot riset habis: **429**.

Output uang rupiah bulat; persentase informasi dibulatkan ke 2 desimal. Keputusan floor/budget memakai nominal sebelum pembulatan persentase tampilan. RAB CSV menggunakan angka yang sama dengan kalkulasi server.
