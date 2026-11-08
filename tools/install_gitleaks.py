"""Install the checksum-pinned scanner in ignored local storage; no credentials used."""

import hashlib
import io
import json
from pathlib import Path
import platform
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
PIN = ROOT / "tools/gitleaks-release.json"


def platform_key():
    system = platform.system().lower()
    machine = {"x86_64":"x64", "amd64":"x64", "aarch64":"arm64", "arm64":"arm64"}.get(platform.machine().lower())
    return f"{system}_{machine}"


def verified_binary(archive, expected):
    if hashlib.sha256(archive).hexdigest() != expected:
        raise ValueError("Scanner archive checksum mismatch")
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as contents:
        member = contents.getmember("gitleaks")
        if not member.isfile():
            raise ValueError("Scanner archive entry is not a regular binary")
        return contents.extractfile(member).read()


def scanner_path(*, download=False):
    pin = json.loads(PIN.read_text())
    system = platform_key()
    if system not in pin["archives"]:
        raise ValueError("Pinned scanner supports Linux/macOS on x64/arm64; this platform needs a reviewed release pin")
    cache = ROOT / ".cache/tools" / ("gitleaks-" + pin["version"]) / system
    archive_path, binary_path = cache / "release.tar.gz", cache / "gitleaks"
    if not archive_path.exists():
        if not download:
            raise ValueError("Install the pinned scanner first: python3 tools/install_gitleaks.py")
        asset = f"gitleaks_{pin['version']}_{system}.tar.gz"
        url = f"https://github.com/gitleaks/gitleaks/releases/download/v{pin['version']}/{asset}"
        with urllib.request.urlopen(url, timeout=60) as response:
            archive = response.read(50 * 1024 * 1024)
        binary = verified_binary(archive, pin["archives"][system])
        cache.mkdir(parents=True, exist_ok=True)
        archive_path.write_bytes(archive)
        binary_path.write_bytes(binary)
        binary_path.chmod(0o700)
    archive = archive_path.read_bytes()
    binary = verified_binary(archive, pin["archives"][system])
    if not binary_path.is_file() or hashlib.sha256(binary_path.read_bytes()).digest() != hashlib.sha256(binary).digest():
        raise ValueError("Cached scanner binary does not match the verified release; remove its cache and reinstall")
    return binary_path, {"version":pin["version"], "archiveSha256":pin["archives"][system], "binarySha256":hashlib.sha256(binary).hexdigest()}


if __name__ == "__main__":
    try:
        path, pin = scanner_path(download=True)
    except (OSError, ValueError, tarfile.TarError, KeyError) as error:
        raise SystemExit(f"Scanner installation failed: {error}")
    print(f"Verified Gitleaks {pin['version']} in local tool cache.")
