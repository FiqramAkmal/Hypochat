# TODO

- Audit Phase 4B interop vs non-Hypochat Nostr clients
- Tambah delivery/queued indicator yang bisa update realtime setelah flush background
- Rancang Phase 4C double-ratchet dan skipped-message keys

## Prioritas Berikutnya

### 1. Hardening lanjutan setelah Phase 2
- [ ] Audit ulang offline sync untuk edge case relay lambat / duplicate / missing backlog di relay nyata
- [ ] Tambah command repair/cache inspect untuk transcript dan peer state

### 2. Rapikan Menu UI
- [ ] Tambah submenu pada contact item: chat / ghost / remove / show public ID
- [ ] Tambah panel info user (`npub`) di header menu
- [ ] Tambah mode konfirmasi sebelum aksi destruktif
- [ ] Tambah fallback jika terminal tidak mendukung `curses`

### 3. Mulai Phase 3
- [ ] Tambah `--require-tor`
- [ ] Tambah mode optional hard-fail `--require-tor`
- [ ] Tambah bootstrap `torrc` minimal yang lebih ketat
- [ ] Tambah smoke test lifecycle Tor nyata pada Windows host
- [x] Tambah doctor check untuk status bundle/proxy Tor

### 4. Quality / Stability
- [ ] Add handshake retry/peer prekey fetch loop so first message never waits for next round trip
- [ ] Tangani out-of-order session announce vs session message saat relay mengirim tidak berurutan
- [ ] Tambah cache in-memory untuk peer-state dedup agar disk read per event berkurang
- [ ] Kurangi full sort transcript/messages saat append in-order agar room besar tetap ringan
- [ ] Tambah benchmark internal untuk ukur full redraw vs input-only redraw
- [ ] Tambah fallback Windows non-curses / `windows-curses` path yang lebih halus
- [ ] Tambah unit test untuk transcript sorting
- [ ] Tambah unit test untuk peer state / last seen
- [ ] Tambah test untuk menu action dispatch
- [ ] Tambah `debug` command untuk inspect relay/event flow
- [ ] Tambah migrasi otomatis data namespace lama `ghostchat` -> `hypochat`
