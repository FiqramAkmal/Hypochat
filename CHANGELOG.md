# CHANGELOG

## Unreleased

### Added
- Reliable Phase 4B bootstrap with prekey request/reply, encrypted pending-first-message queue, and out-of-order session payload buffering
- Phase 4B prekey handshake with replay-protected local state
- Phase 4A session-key transport with encrypted local session state
- Outgoing session rotation now happens per chat/ghost run
- Incoming and outgoing session contexts now persist in encrypted local session state
- Hypochat-only inner encrypted payload as the default message format
- Encrypted key storage with password protection
- Encrypted peer sync state storage tied to session/key-store password
- Encrypted transcript cache storage tied to session/key-store password
- Interactive launcher menu for no-subcommand startup
- Contact selection directly from `Chat` and `Ghost` menu
- Offline sync basics with `last_seen`
- Peer transcript cache for room reopen
- `curses`-based chat UI with fixed header, conversation pane, and input box
- Scroll support in conversation pane (`PgUp`, `PgDn`, `Up`, `Down`)
- Editable message box cursor movement (`Left`, `Right`, `Home`, `End`, `Backspace`, `Delete`)
- Privacy mode presets: `usable-sync` and `strict-no-trace`
- Payload padding policy for outgoing private messages
- Tor runtime manager scaffold with bundled binary lookup under `bin/tor/<platform-arch>/...`
- Official bundled Tor expert runtimes for `linux-x86_64`, `macos-x86_64`, `macos-arm64`, and `windows-x86_64`

### Changed
- Project branding normalized from `ghostchat` to `hypochat`
- Local app data namespace changed to `hypochat`
- Chat timestamps now follow local computer timezone
- Chat header now shows live sync/activity status in the chat UI
- Transcript ordering normalized on load and rewritten on room open
- Reopen room now loads transcript after backlog sync merge
- Strict no-trace mode now disables transcript persistence and peer sync-state persistence
- Invalid privacy modes are now rejected explicitly
- Tor is now enabled by default in runtime config
- Runtime now attempts existing SOCKS proxy first, then bundled Tor, then clean fallback to direct connection
- `python3 hypochat.py` and `python -m hypochat` now pre-start Tor on launcher startup when Tor is enabled

### Fixed
- Package/import bootstrap issues
- Missing package metadata and missing storage module issues
- Multiple `nostr_sdk` API mismatches:
  - `RelayUrl` vs `str`
  - `wait_for_connection(timeout)`
  - `subscribe(filter)` vs list
  - `send_private_msg(..., None)`
- Chat session task errors no longer explode as raw task exceptions
- Curses input box draw error on some terminals (`addnwstr() returned ERR`)
- Message ordering issues for stored transcript reopen flow
- Tor readiness probing now degrades safely when socket probing is unavailable in restricted environments

### Known Limitations
- Tor privacy is best-effort by default and not enforced yet
- Phase 4C advanced ratchet is not implemented yet
- Offline sync is functional but not yet fully battle-tested across many relay behaviors
