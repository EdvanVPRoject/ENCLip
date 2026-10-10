# Kebijakan Keamanan

## Pelaporan kerentanan

Jangan membuat issue public untuk kerentanan keamanan, API key, token, password,
atau data pribadi.

Gunakan GitHub Security Advisories atau hubungi pemilik repository melalui
kanal privat yang tersedia di profil GitHub. Sertakan:

- versi atau commit yang terdampak;
- langkah reproduksi;
- dampak yang ditemukan;
- bukti minimal yang tidak membocorkan data sensitif;
- saran perbaikan jika tersedia.

## Jika rahasia terlanjur ter-push

Segera cabut atau rotasi API key, token, password, dan credential tersebut.
Menghapus file dari commit terbaru saja tidak cukup karena data dapat tetap berada
di riwayat Git.

## Cakupan

Laporan dapat mencakup aplikasi desktop, backend lokal, proses download, proses
render, serta konfigurasi packaging. Model GGUF dan dependency pihak ketiga
memiliki kebijakan serta lisensi masing-masing.
