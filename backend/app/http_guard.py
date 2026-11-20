"""SSRF guard for outbound HTTP with user-influenced URLs.

Used by the webhook dispatcher (app.copilot) and the live FX fetcher
(app.normalize.fx_service). Validation is deliberately layered:

1. HTTPS-only scheme.
2. Hostname denylist (localhost variants, cloud metadata hosts, *.local,
   *.internal, bare IP literals in non-public ranges).
3. Best-effort DNS resolution: every resolved address must be public.
   Unresolvable hosts are allowed to proceed (the subsequent request will
   simply fail) — this keeps offline/test environments working.
4. ``guarded_urlopen`` funnels every outbound call through a validating
   opener that re-checks redirect targets (anti DNS-rebinding posture).
"""
from __future__ import annotations

import ipaddress
import socket
import ssl
import urllib.parse
import urllib.request

_BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
    "metadata.goog",
    "instance-data",
}

_BLOCKED_SUFFIXES = (".local", ".internal", ".localhost", ".home.arpa")


def _is_public_ip(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value.strip("[]"))
    except ValueError:
        return True  # not an IP literal — hostname; DNS layer handles it
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def validate_public_http_url(url: str) -> None:
    """Raise ``ValueError`` when ``url`` targets a non-public HTTP endpoint."""
    parsed = urllib.parse.urlparse(str(url or ""))
    if parsed.scheme != "https":
        raise ValueError(f"only https URLs are allowed, got scheme: {parsed.scheme!r}")
    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError("URL is missing a hostname")
    if host in _BLOCKED_HOSTNAMES or host.endswith(_BLOCKED_SUFFIXES):
        raise ValueError(f"blocked hostname: {host}")
    if not _is_public_ip(host):
        raise ValueError(f"blocked non-public IP literal: {host}")
    try:
        infos = socket.getaddrinfo(host, parsed.port or 443)
    except (socket.gaierror, OSError):
        return  # unresolvable: not an internal address; let the request fail naturally
    for info in infos:
        ip_value = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_value)
        except ValueError:
            continue
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise ValueError(f"host {host} resolves to a non-public address: {ip}")


class _ValidatedRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Follow redirects only when every target passes the same SSRF guard."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_public_http_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def guarded_urlopen(request_or_url, timeout: float = 5.0, **kwargs):
    """Validate the target, then open it through a redirect-validating opener.

    Drop-in for ``urllib.request.urlopen`` for outbound calls whose URL is
    influenced by configuration or user input.
    """
    url = getattr(request_or_url, "full_url", None) or str(request_or_url)
    validate_public_http_url(url)
    context = ssl.create_default_context()
    opener = urllib.request.build_opener(_ValidatedRedirectHandler(), context)
    return opener.open(request_or_url, timeout=timeout, **kwargs)
