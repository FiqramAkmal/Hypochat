# Hypochat CLI

Hypochat CLI adalah aplikasi chat terminal berbasis Python di jaringan relay Nostr dengan fokus pada privasi, usability, dan setup tanpa server sendiri.

Tujuan proyek ini:
- user cukup clone repo lalu jalankan
- tidak perlu membangun server chat sendiri
- bisa menambah contact lewat `npub` lalu langsung chat
- pesan memakai private message flow modern Nostr
- payload dalam pesan memakai format Hypochat-only secara default
- key lokal disimpan terenkripsi dengan password
- ghost mode tersedia untuk sesi ephemeral
- Tor aktif otomatis secara best-effort, dengan opsi opt-out

## Fitur

- Encrypted key store dengan password
- NIP-44 helper untuk enkripsi konten
- Private chat flow via gift-wrapped private messages
- Hypochat-only inner encrypted payload by default
- Contact list berbasis nickname
- Ghost mode dengan identity sementara
- History lokal default `OFF`
- Privacy defaults untuk Tor dan history
- Default mencoba memakai Tor otomatis saat launcher dibuka
- Bundled Tor resmi disiapkan untuk Linux/macOS/Windows x86_64 serta macOS arm64
- Fallback direct connection kalau Tor gagal start

## Struktur jalan

Normal mode:
- Anda buat identity lokal
- Identity disimpan terenkripsi di disk
- Anda tukar `npub` dengan teman
- Anda add contact teman
- Anda chat lewat relay publik

Ghost mode:
- Identity dibuat sementara per sesi
- Tidak disimpan ke disk
- Cocok untuk sesi yang lebih anonim

## Kebutuhan

- Python 3.13 atau kompatibel
- `venv` aktif atau interpreter yang punya dependency repo
- koneksi internet ke relay Nostr

Catatan platform:
- Linux/macOS cukup pakai dependensi default di `requirements.txt`
- Windows butuh `windows-curses` untuk UI terminal

## Install

Clone repo lalu masuk folder project:

```bash
git clone <repo-url>
cd Hypochat-CLI
```

Buat virtualenv dan install dependency:

```bash
python3 -m venv hyvenv
source hyvenv/bin/activate
pip install -r requirements.txt
```

Catatan penting:
- `pip install -r requirements.txt --exclude ...` bukan flag pip yang valid
- untuk Linux/macOS, cukup pakai `pip install -r requirements.txt`
- untuk Windows, jalankan dari PowerShell:

```powershell
py -3 -m venv hyvenv
hyvenv\Scripts\activate
pip install -r requirements.txt
```

Kalau virtualenv repo sudah ada, Anda bisa pakai langsung:

```bash
source hyvenv/bin/activate
```

## Menjalankan CLI

Cara utama:

```bash
python -m hypochat --help
```

Alternatif launcher kompatibilitas:

```bash
python3 hypochat.py
```

Kalau `hypochat.py` dijalankan tanpa subcommand, aplikasi masuk ke menu interaktif.

## 1. Buat identity

Identity disimpan terenkripsi dengan password.

Interaktif:

```bash
python -m hypochat init
```

Atau non-interaktif dengan env var:

```bash
export HYPOCHAT_PASSWORD='ganti-dengan-password-kuat'
python -m hypochat init
```

Lihat `npub` Anda:

```bash
python -m hypochat id
```

Export recovery key `nsec`:

```bash
python -m hypochat export
```

Import identity dari `nsec`:

```bash
python -m hypochat import nsec1...
```

## 2. Tambah contact

Tambahkan teman dengan `npub` mereka:

```bash
python -m hypochat add npub1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx --name alice
```

Lihat daftar contact:

```bash
python -m hypochat contacts
```

Hapus contact:

```bash
python -m hypochat remove alice
```

## 3. Mulai chat

Dengan nickname:

```bash
python -m hypochat chat alice
```

Atau langsung dengan `npub`:

```bash
python -m hypochat chat npub1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Command di dalam chat:

```text
/help   tampilkan bantuan
/id     tampilkan npub Anda
/clear  bersihkan layar
/exit   keluar chat
```

## 4. Ghost mode

Ghost mode memakai identity sementara yang tidak disimpan.

Buka ghost mode pasif untuk menerima pesan di sesi itu:

```bash
python -m hypochat ghost
```

CLI akan menampilkan `Temp Public ID`.
Bagikan ID itu ke lawan chat.

Atau langsung chat ke target dengan identity ephemeral:

```bash
python -m hypochat ghost npub1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

## 5. Privacy defaults

Set default privacy config:

```bash
python -m hypochat privacy set --tor --no-store-history
```

Atur SOCKS proxy Tor custom:

```bash
python -m hypochat privacy set --tor-proxy socks5://127.0.0.1:9050
```

## 6. Tor mode

Default sekarang: Hypochat akan mencoba konek lewat Tor otomatis.

Urutan perilaku:
- saat `python3 hypochat.py` dibuka tanpa subcommand, launcher mencoba menyalakan Tor lebih dulu
- kalau SOCKS Tor di `127.0.0.1:9050` sudah ada, Hypochat pakai itu
- kalau tidak ada, Hypochat mencoba start bundled Tor dari folder `bin/tor/...`
- kalau bundle gagal start, Hypochat **tidak hard-fail** dan fallback ke koneksi direct sambil memberi warning

Struktur bundle yang sekarang dibundling:

```text
bin/
  tor/
    linux-x86_64/tor
    macos-arm64/tor
    macos-x86_64/tor
    windows-x86_64/tor.exe
```

Paksa Tor aktif untuk satu sesi:

```bash
python -m hypochat chat alice --tor
```

Nonaktifkan Tor untuk satu sesi:

```bash
python -m hypochat chat alice --no-tor
```

Ghost mode dengan default Tor:

```bash
python -m hypochat ghost alice
```

Kalau Anda mau memastikan route lewat Tor sistem sendiri, wrapper OS tetap bisa dipakai:

```bash
torify python -m hypochat chat alice
```

atau:

```bash
torsocks python -m hypochat chat alice
```

## 7. History lokal

Default saat ini: history lokal `OFF`.

Aktifkan hanya untuk satu sesi:

```bash
python -m hypochat chat alice --store-history
```

Aktifkan sebagai default:

```bash
python -m hypochat privacy set --store-history
```

Nonaktifkan lagi:

```bash
python -m hypochat privacy set --no-store-history
```

## Relay

Lihat relay aktif:

```bash
python -m hypochat relay list
```

Tambah relay:

```bash
python -m hypochat relay add wss://relay.example.com
```

Hapus relay:

```bash
python -m hypochat relay remove wss://relay.example.com
```

## Doctor

Jalankan diagnosis lokal:

```bash
python -m hypochat doctor
```

Opsional, verifikasi juga bahwa password key-store memang bisa membuka identity:

```bash
python -m hypochat doctor --password 'password-anda'
```

## Lokasi data lokal

Data aplikasi disimpan melalui `platformdirs`.
Biasanya di Linux akan berada di bawah home user, misalnya:

```text
~/.local/share/hypochat/
```

Isinya bisa mencakup:
- `key.json` — key store terenkripsi
- `contacts.json` — daftar contact
- `config.json` — privacy config dan relay
- `history/` — history lokal jika diaktifkan

## Catatan keamanan

Yang sudah ada:
- key store terenkripsi password
- ghost mode ephemeral
- history default off
- private message flow modern

Yang perlu Anda pahami:
- relay publik tetap pihak ketiga
- Tor mode di app ini masih best-effort
- untuk anonimitas IP lebih kuat, gunakan `torify` atau `torsocks`
- kalau password salah, key store tidak bisa dibuka
- kalau recovery key `nsec` bocor, identity Anda dianggap bocor penuh

## Smoke test cepat

Cek CLI:

```bash
python -m hypochat --help
```

Cek versi:

```bash
python -m hypochat version
```

## Troubleshooting

Kalau muncul error dependency belum ada:

```bash
pip install -r requirements.txt
```

Kalau password salah:

```text
Wrong password or corrupted key store.
```

Kalau identity belum ada:

```bash
python -m hypochat init
```

Kalau ingin reset identity, hapus file data lokal secara manual dengan hati-hati.
Pastikan Anda sudah backup `nsec` sebelum melakukannya.
