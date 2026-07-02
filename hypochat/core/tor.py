import os
import platform
import socket
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from hypochat.storage import get_data_dir


BUNDLED_TOR_LAYOUTS = {
    "linux-x86_64": [
        "tor/tor",
        "data/geoip",
        "data/geoip6",
        "data/torrc-defaults",
        "tor/libcrypto.so.3",
        "tor/libssl.so.3",
        "tor/libevent-2.1.so.7",
    ],
    "macos-x86_64": [
        "tor/tor",
        "data/geoip",
        "data/geoip6",
        "data/torrc-defaults",
        "tor/libevent-2.1.7.dylib",
    ],
    "macos-arm64": [
        "tor/tor",
        "data/geoip",
        "data/geoip6",
        "data/torrc-defaults",
        "tor/libevent-2.1.7.dylib",
    ],
    "windows-x86_64": [
        "tor/tor.exe",
        "tor/tor-gencert.exe",
        "data/geoip",
        "data/geoip6",
        "data/torrc-defaults",
    ],
}


@dataclass
class TorStatus:
    enabled: bool
    using_bundle: bool
    started: bool
    proxy: str | None
    warning: str | None = None


class TorManager:
    def __init__(self, proxy_url: str = "socks5://127.0.0.1:9050"):
        self.proxy_url = proxy_url
        self.process: subprocess.Popen | None = None
        self.socks_host = "127.0.0.1"
        self.socks_port = 9050

    def _platform_key(self) -> str:
        system = platform.system().lower()
        machine = platform.machine().lower()
        aliases = {
            "amd64": "x86_64",
            "x64": "x86_64",
            "arm64": "arm64",
            "aarch64": "arm64",
        }
        machine = aliases.get(machine, machine)
        if system == "darwin":
            system = "macos"
        elif system == "windows":
            system = "windows"
        elif system == "linux":
            system = "linux"
        return f"{system}-{machine}"


    def supported_platform_keys(self) -> list[str]:
        return sorted(BUNDLED_TOR_LAYOUTS.keys())

    def validate_bundle_layout(self, platform_key: str | None = None) -> tuple[bool, list[str], Path | None]:
        target_key = platform_key or self._platform_key()
        root = Path(__file__).resolve().parents[2] / "bin" / "tor" / target_key
        required = BUNDLED_TOR_LAYOUTS.get(target_key)
        if required is None:
            return False, [f"unsupported platform key: {target_key}"], root
        missing = [entry for entry in required if not (root / entry).exists()]
        return len(missing) == 0, missing, root

    def validate_all_bundles(self) -> dict[str, dict[str, object]]:
        report: dict[str, dict[str, object]] = {}
        for platform_key in self.supported_platform_keys():
            ok, missing, root = self.validate_bundle_layout(platform_key)
            report[platform_key] = {
                "ok": ok,
                "missing": missing,
                "root": root,
            }
        return report

    def bundled_root(self) -> Path | None:
        root = Path(__file__).resolve().parents[2]
        platform_key = self._platform_key()
        base = root / "bin" / "tor" / platform_key
        if base.exists():
            return base
        return None

    def bundled_binary(self) -> Path | None:
        base = self.bundled_root()
        if base is None:
            return None
        names = ["tor.exe", "tor"] if platform.system().lower() == "windows" else ["tor", "tor.exe"]
        for name in names:
            candidate = base / "tor" / name
            if candidate.exists():
                return candidate
        return None

    def _bundle_env(self, bundle_root: Path) -> dict[str, str]:
        env = dict(os.environ)
        tor_dir = bundle_root / "tor"
        current_platform = platform.system().lower()
        if current_platform == "linux":
            existing = env.get("LD_LIBRARY_PATH", "")
            env["LD_LIBRARY_PATH"] = f"{tor_dir}{':' + existing if existing else ''}"
        elif current_platform == "darwin":
            existing = env.get("DYLD_LIBRARY_PATH", "")
            env["DYLD_LIBRARY_PATH"] = f"{tor_dir}{':' + existing if existing else ''}"
        path_existing = env.get("PATH", "")
        env["PATH"] = f"{tor_dir}{':' + path_existing if path_existing else ''}"
        return env

    def _runtime_root(self) -> Path:
        candidates = [get_data_dir() / "tor_runtime", Path(tempfile.gettempdir()) / "hypochat-tor-runtime"]
        for candidate in candidates:
            try:
                candidate.mkdir(parents=True, exist_ok=True)
                return candidate
            except OSError:
                continue
        raise OSError("No writable directory available for Tor runtime")

    def is_proxy_ready(self, timeout: float = 0.5) -> bool:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((self.socks_host, self.socks_port))
            return True
        except OSError:
            return False
        finally:
            try:
                sock.close()
            except Exception:
                pass

    def start(self, wait_seconds: float = 8.0) -> TorStatus:
        if self.is_proxy_ready():
            return TorStatus(enabled=True, using_bundle=False, started=False, proxy=self.proxy_url, warning=None)

        bundle_root = self.bundled_root()
        binary = self.bundled_binary()
        if binary is None or bundle_root is None:
            return TorStatus(
                enabled=True,
                using_bundle=False,
                started=False,
                proxy=None,
                warning="Bundled Tor binary not found; falling back to direct connection.",
            )

        if platform.system().lower() != "windows":
            binary.chmod(binary.stat().st_mode | 0o111)

        try:
            tor_dir = self._runtime_root()
        except OSError as exc:
            return TorStatus(
                enabled=True,
                using_bundle=True,
                started=False,
                proxy=None,
                warning=f"Failed to prepare Tor runtime directory: {exc}",
            )
        data_dir = tor_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        log_file = tor_dir / "tor.log"

        cmd = [
            str(binary),
            "--defaults-torrc", str(bundle_root / "data" / "torrc-defaults"),
            "--SocksPort", str(self.socks_port),
            "--DataDirectory", str(data_dir),
            "--GeoIPFile", str(bundle_root / "data" / "geoip"),
            "--GeoIPv6File", str(bundle_root / "data" / "geoip6"),
            "--Log", f"notice file {log_file}",
        ]

        try:
            self.process = subprocess.Popen(
                cmd,
                cwd=bundle_root,
                env=self._bundle_env(bundle_root),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            return TorStatus(
                enabled=True,
                using_bundle=True,
                started=False,
                proxy=None,
                warning=f"Failed to start bundled Tor: {exc}",
            )

        deadline = time.time() + wait_seconds
        while time.time() < deadline:
            if self.is_proxy_ready():
                return TorStatus(enabled=True, using_bundle=True, started=True, proxy=self.proxy_url, warning=None)
            if self.process.poll() is not None:
                break
            time.sleep(0.2)

        self.stop()
        return TorStatus(
            enabled=True,
            using_bundle=True,
            started=False,
            proxy=None,
            warning="Bundled Tor did not become ready; falling back to direct connection.",
        )

    def stop(self):
        if self.process is None:
            return
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.process = None
