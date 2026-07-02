# NOTE

## Status Ringkas
- Phase 1: DONE
- Phase 2: DONE
- Phase 3: IN PROGRESS
- Phase 4A: DONE
- Phase 4B: DONE

## Checklist Phase

### Phase 1 — Foundation
- [x] Struktur project dasar berjalan
- [x] Command CLI utama tersedia
- [x] Launcher menu interaktif tanpa subcommand
- [x] Encrypted key storage dengan password
- [x] Identity init / export / import
- [x] Contact management
- [x] Basic chat session berjalan
- [x] Ghost mode dasar
- [x] Transcript cache reopen room
- [x] README dasar
- [x] UI responsiveness pass untuk input/render dasar

### Phase 2 — Metadata Privacy
- [x] Private/gift-wrapped message flow dipakai
- [x] Ghost mode ephemeral tersedia
- [x] Offline sync dasar dengan `last_seen`
- [x] Dedup event dasar
- [x] Transcript ordering diperbaiki
- [x] Padding policy eksplisit
- [x] Hypochat-only inner payload default
- [x] Peer sync state encryption
- [x] Transcript cache encryption
- [x] Strict no-trace mode vs usable mode
- [x] End-to-end privacy validation untuk komponen lokal/storage/mode

### Phase 3 — IP Privacy
- [ ] `require_tor` enforcement
- [ ] Optional hard-fail mode jika Tor wajib aktif
- [x] Auto-detect existing Tor SOCKS
- [x] Auto-launch bundled Tor jika binary tersedia
- [x] Bundled Tor binary per platform dimasukkan ke repo/release
- [x] Runtime Tor status indicator
- [x] Cross-platform packaging/lifecycle validation dasar

### Phase 4A — Session Security Lite
- [x] Session key rotation per sesi
- [x] Encrypted session state lokal
- [x] Session context terpisah dari identity context
- [x] Resume session state aman

### Phase 4B — Prekey Handshake
- [x] Prekey bundle
- [x] X3DH-lite handshake
- [x] Root secret per peer/session
- [x] Replay protection handshake
- [x] Handshake state validation


## Catatan Optimasi Terakhir
- Cache render conversation ditambahkan agar ketik karakter tidak me-wrap ulang seluruh room setiap frame
- Loop chat tidak lagi sleep tetap 30ms pada setiap iterasi; idle sleep diperkecil agar input lebih responsif
- Partial redraw untuk input box saat mengetik
- Bubble `you` sekarang muncul langsung saat Enter, tanpa menunggu network send selesai
- Load transcript tidak lagi menulis ulang transcript file per pesan saat room dibuka

- doctor sekarang memvalidasi layout bundle Tor untuk semua platform bundle
