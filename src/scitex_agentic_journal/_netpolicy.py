"""Outbound-network policy for fetches a submission can steer.

A submission names URLs the journal then fetches (today: the repository it
clones). Without a policy, an ``https://`` URL could point the journal at
its own loopback services, the cloud metadata endpoint or private networks
(server-side request forgery).

The policy is **resolve-then-connect**:

1. resolve the host once;
2. refuse if *any* resolved address is loopback, private, link-local,
   multicast, reserved, unspecified or otherwise not globally routable
   (IPv4-mapped IPv6 addresses are checked as IPv4);
3. connect only to the vetted address. For git this pins libcurl with
   ``http.curloptResolve`` and disables redirects, so a later DNS answer
   (rebinding) or a redirect cannot reach a different host.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlsplit


class OutboundBlockedError(RuntimeError):
    """The destination is not allowed by the outbound-network policy."""


@dataclass(frozen=True)
class VettedTarget:
    host: str
    port: int
    address: str


def _is_public(addr: str) -> bool:
    ip = ipaddress.ip_address(addr)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_global and not (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def resolve_public(host: str, port: int) -> str:
    """Resolve ``host`` and return one address, refusing any non-public answer."""
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise OutboundBlockedError(f"cannot resolve {host!r}: {e}") from e
    addresses = sorted({info[4][0] for info in infos})
    if not addresses:
        raise OutboundBlockedError(f"{host!r} resolved to no address")
    blocked = [a for a in addresses if not _is_public(a)]
    if blocked:
        raise OutboundBlockedError(
            f"{host!r} resolves to non-public address(es) {blocked}; "
            "outbound fetches may only reach globally routable hosts"
        )
    return addresses[0]


def vet_https_url(url: str) -> VettedTarget:
    """Check an ``https://`` URL against the policy and return the pinned target."""
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        raise OutboundBlockedError(f"{url!r} is not an https:// URL with a host")
    if parts.username or parts.password:
        raise OutboundBlockedError(f"{url!r} embeds credentials")
    port = parts.port or 443
    return VettedTarget(parts.hostname, port, resolve_public(parts.hostname, port))


def git_pin_args(target: VettedTarget) -> list[str]:
    """``git -c`` arguments that pin the connection to the vetted address."""
    address = f"[{target.address}]" if ":" in target.address else target.address
    return [
        "-c",
        f"http.curloptResolve={target.host}:{target.port}:{address}",
        "-c",
        "http.followRedirects=false",
    ]
