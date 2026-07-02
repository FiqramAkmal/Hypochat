# PHASE

## Phase 1 — Foundation
Target: aplikasi dasar usable, stabil, dan aman untuk penyimpanan key lokal.

Includes:
- struktur repo
- command CLI utama
- launcher menu interaktif
- encrypted key storage
- identity and contact flow
- basic chat session
- ghost mode dasar
- reopen room transcript cache

Status:
- DONE

Notes:
- CLI utama, launcher menu, contact flow, dan sesi chat dasar sudah jalan
- key store lokal sudah terenkripsi password
- transcript cache room reopen sudah ada
- fondasi ini stabil, tetapi bukan layer forward secrecy tingkat lanjut

---

## Phase 2 — Metadata Privacy
Target: tingkatkan privasi metadata dan usability chat tanpa server sendiri.

Includes:
- private/gift-wrapped message flow
- ghost mode ephemeral
- offline sync dasar
- `last_seen`
- event dedup
- transcript ordering
- padding policy
- local trace minimization strategy
- Hypochat-only inner payload enabled by default

Status:
- DONE

Notes:
- outgoing payload padding sudah ada
- peer sync state dan transcript cache terenkripsi untuk mode sinkron
- `strict-no-trace` mematikan transcript persistence dan peer-state persistence
- payload default sekarang Hypochat-only, jadi client Nostr biasa tidak bisa membaca isi inner payload Hypochat
- metadata relay masih belum sepenuhnya hilang di level network; itu bukan target utama phase ini

---

## Phase 3 — IP Privacy
Target: IP asli user tersembunyi sebisa mungkin secara default, lalu nanti bisa dinaikkan ke mode enforced.

Includes:
- default Tor-on
- auto-detect existing SOCKS Tor
- auto-launch bundled Tor
- bundled Tor binary per platform
- status indicator Tor
- optional `require_tor` hard-fail mode

Status:
- IN PROGRESS

Notes:
- runtime Tor default-on sudah ada
- auto-detect SOCKS proxy yang sudah jalan sudah ada
- auto-launch bundled Tor dan layout binary per platform sudah ada
- doctor validation untuk bundle layout sudah ada
- fallback direct connection masih diizinkan secara sengaja bila Tor gagal
- `require_tor` enforced mode belum selesai, jadi phase ini belum boleh disebut DONE
- validasi lifecycle Tor nyata lintas platform masih perlu dibuktikan lebih jauh

---

## Phase 4A — Session Security Lite
Target: session crypto lebih aman tanpa langsung full ratchet.

Includes:
- session key per sesi
- encrypted session state lokal
- rotasi key antar sesi
- context sesi terpisah dari identity key

Status:
- DONE

Notes:
- outgoing session rotate per chat/ghost run sudah ada
- incoming/outgoing session state sudah terenkripsi di local storage
- session context sudah dipisah dari identity key utama

---

## Phase 4B — Prekey Handshake
Target: root secret per peer/session melalui handshake yang lebih kuat.

Includes:
- prekey bundle
- X3DH-lite handshake
- root secret per peer/session
- replay protection handshake
- reliable first-message bootstrap queue
- out-of-order session payload buffering

Status:
- DONE

Notes:
- bootstrap prekey request/reply sudah ada
- first message tidak lagi diam-diam drop saat peer prekey belum tersedia; sekarang masuk queue terenkripsi lokal lalu di-flush
- session payload yang datang lebih dulu dari control/handshake sekarang dibuffer dan diproses ulang
- replay id handshake disimpan dan dicek lokal per peer
- ini sudah menutup flaw reliabilitas utama phase 4B, tetapi belum sama dengan advanced double-ratchet

---

## Phase 4C — Advanced Ratchet
Target: forward secrecy dan post-compromise resilience tingkat lanjut.

Includes:
- ratchet per pesan
- chain keys
- skipped message handling
- out-of-order resilience

Status:
- BELUM / future hardening

Notes:
- belum ada double-ratchet per pesan
- belum ada chain key evolution dan skipped-message key store
- phase ini adalah gap keamanan besar berikutnya setelah 4B

---

## Ringkasan Audit
Status implementasi paling jujur saat ini:
- Phase 1: DONE
- Phase 2: DONE
- Phase 3: IN PROGRESS
- Phase 4A: DONE
- Phase 4B: DONE
- Phase 4C: BELUM

Artinya:
- stack fitur dan crypto yang sudah terimplementasi sudah sampai Phase 4B
- roadmap keseluruhan belum complete karena Phase 3 dan Phase 4C masih tersisa
