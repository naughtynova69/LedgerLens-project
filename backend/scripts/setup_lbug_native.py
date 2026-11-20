#!/usr/bin/env python3
"""Download the pinned native LadybugDB (lbug) C-API library for this platform.

The ``ladybug`` PyPI wheel ships the ctypes C-API binding but NOT the native
shared library. This script fetches the release asset matching the pinned
version (LADYBUGDB_VERSION) into ``<repo>/.cache/lbug-prebuilt/lib`` — the
location ``app.graph.client`` resolves automatically. The cache directory is
gitignored: native binaries never enter the repository.

Usage (from repo root or backend/):
    python backend/scripts/setup_lbug_native.py

Env overrides:
    LADYBUGDB_VERSION   release tag to fetch (default: 0.22.3, must be x.y.z)

Security: HTTPS-only, fixed host allowlist (github.com and its release asset
CDN), every URL and redirect target is validated (scheme + host + resolved IP
must be public), and archive members are checked against zip-slip/tar-slip
before extraction.
"""
from __future__ import annotations

import ipaddress
import os
import platform
import re
import socket
import ssl
import stat
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from urllib.parse import urlparse

LADYBUGDB_VERSION = os.getenv("LADYBUGDB_VERSION", "0.22.3")
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
RELEASE_BASE = f"https://github.com/LadybugDB/ladybug/releases/download/v{LADYBUGDB_VERSION}"

ALLOWED_HOSTS = {"github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com"}
MAX_DOWNLOAD_BYTES = 256 * 1024 * 1024

REPO_ROOT = Path(__file__).resolve().parents[2]
TARGET_DIR = REPO_ROOT / ".cache" / "lbug-prebuilt" / "lib"


def _asset_name() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    arch = "x86_64" if machine in ("amd64", "x86_64") else "arm64"
    if system == "windows":
        return f"liblbug-windows-{arch}.zip"
    if system == "darwin":
        return f"liblbug-osx-{arch}.tar.gz"
    return f"liblbug-linux-{arch}.tar.gz"


def _validate_url(url: str) -> None:
    """HTTPS-only, host allowlist, and public-IP resolution (SSRF guard)."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError(f"only https is allowed: {url}")
    host = parsed.hostname or ""
    if host not in ALLOWED_HOSTS:
        raise ValueError(f"host not allowed: {host}")
    for _family, _type, _proto, _canonname, sockaddr in socket.getaddrinfo(host, 443):
        ip = ipaddress.ip_address(sockaddr[0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise ValueError(f"host resolves to a non-public address: {host} -> {ip}")


class _ValidatedRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Follow redirects only when every target passes the same SSRF guard."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _http_get(url: str, destination: Path) -> None:
    _validate_url(url)
    context = ssl.create_default_context()
    opener = urllib.request.build_opener(
        _ValidatedRedirectHandler(), urllib.request.HTTPSHandler(context=context)
    )
    request = urllib.request.Request(url, headers={"User-Agent": "ledgerlens-setup"})
    with opener.open(request, timeout=300) as response:
        expected = response.headers.get("Content-Length")
        if expected and int(expected) > MAX_DOWNLOAD_BYTES:
            raise ValueError("release asset exceeds the size limit")
        downloaded = 0
        chunks: list[bytes] = []
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            downloaded += len(chunk)
            if downloaded > MAX_DOWNLOAD_BYTES:
                raise ValueError("release asset exceeds the size limit")
            chunks.append(chunk)
    destination.write_bytes(b"".join(chunks))


def _safe_members(archive: Path, destination: Path) -> list:
    """Archive members with the destination as the strictly allowed root."""
    safe: list = []
    destination_resolved = destination.resolve()
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as bundle:
            for info in bundle.infolist():
                name = info.filename
                candidate = (destination / name).resolve()
                if name.startswith("/") or ".." in Path(name).parts:
                    raise ValueError(f"unsafe archive member: {name}")
                if not candidate.is_relative_to(destination_resolved):
                    raise ValueError(f"archive member escapes target: {name}")
                safe.append(info)
        return safe
    with tarfile.open(archive) as bundle:
        for member in bundle.getmembers():
            name = member.name
            candidate = (destination / name).resolve()
            if name.startswith("/") or ".." in Path(name).parts:
                raise ValueError(f"unsafe archive member: {name}")
            if not candidate.is_relative_to(destination_resolved):
                raise ValueError(f"archive member escapes target: {name}")
            if member.issym() or member.islnk():
                raise ValueError(f"archive member is a link: {name}")
            safe.append(member)
    return safe


def _extract(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    members = _safe_members(archive, destination)
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(destination, members=members)
    else:
        with tarfile.open(archive) as bundle:
            bundle.extractall(destination, members=members, filter="data")


def main() -> int:
    if not VERSION_PATTERN.match(LADYBUGDB_VERSION):
        print(
            f"ERROR: LADYBUGDB_VERSION must be x.y.z, got: {LADYBUGDB_VERSION}",
            file=sys.stderr,
        )
        return 1

    asset = _asset_name()
    url = f"{RELEASE_BASE}/{asset}"
    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    print(f"LedgerLens graph engine setup — LadybugDB v{LADYBUGDB_VERSION}")
    print(f"Downloading {url}")

    with tempfile.TemporaryDirectory() as tmp:
        archive_path = Path(tmp) / asset
        try:
            _http_get(url, archive_path)
        except (urllib.error.URLError, ValueError, OSError) as exc:
            print(f"ERROR: download failed: {exc}", file=sys.stderr)
            print(
                "Manual fallback: fetch the archive from "
                f"https://github.com/LadybugDB/ladybug/releases/tag/v{LADYBUGDB_VERSION} "
                f"and extract it into {TARGET_DIR}",
                file=sys.stderr,
            )
            return 1
        try:
            _extract(archive_path, TARGET_DIR)
        except (ValueError, tarfile.TarError, zipfile.BadZipFile) as exc:
            print(f"ERROR: extraction failed: {exc}", file=sys.stderr)
            return 1

    for shared in TARGET_DIR.iterdir():
        if shared.suffix in (".so", ".dylib", ".dll"):
            try:
                shared.chmod(shared.stat().st_mode | stat.S_IEXEC)
            except OSError:  # pragma: no cover - best effort on platforms that allow it
                pass

    print(f"Extracted native library into {TARGET_DIR}:")
    for entry in sorted(TARGET_DIR.iterdir()):
        print(f"  - {entry.name}")
    print("app.graph.client resolves this path automatically (LBUG_C_API_LIB_PATH).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
