# Bundled Tor binaries

Bundled from official Tor expert bundles.

Included now:

- `bin/tor/linux-x86_64/...`
- `bin/tor/macos-arm64/...`
- `bin/tor/macos-x86_64/...`
- `bin/tor/windows-x86_64/...`

Each platform folder keeps the extracted Tor layout, including:

- `tor/tor` or `tor/tor.exe`
- `data/geoip`
- `data/geoip6`
- `data/torrc-defaults`

Hypochat starts the bundled runtime from these folders automatically when Tor is enabled and no existing local SOCKS Tor proxy is already available.
