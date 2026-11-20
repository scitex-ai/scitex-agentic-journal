"""Outbound-network policy: resolve-then-connect, refusing non-public targets.

IP-literal URLs resolve without DNS, so these tests run offline.
"""

from __future__ import annotations

import pytest
from scitex_agentic_journal._netpolicy import (
    OutboundBlockedError,
    git_pin_args,
    vet_https_url,
)

BLOCKED = [
    "https://127.0.0.1/repo.git",
    "https://localhost/repo.git",
    "https://169.254.169.254/latest/meta-data/",
    "https://10.1.2.3/repo.git",
    "https://192.168.1.10/repo.git",
    "https://100.64.0.6/repo.git",
    "https://0.0.0.0/repo.git",
    "https://[::1]/repo.git",
    "https://[::ffff:127.0.0.1]/repo.git",
    "https://[fe80::1]/repo.git",
]


@pytest.mark.parametrize("url", BLOCKED)
def test_non_public_destinations_are_refused(url):
    # Arrange
    target = url
    # Act
    call = lambda: vet_https_url(target)
    # Assert
    with pytest.raises(OutboundBlockedError):
        call()


@pytest.mark.parametrize(
    "url",
    ["http://1.1.1.1/repo.git", "https://user:pw@1.1.1.1/repo.git", "file:///etc"],
)
def test_non_https_or_credentialed_urls_are_refused(url):
    # Arrange
    target = url
    # Act
    call = lambda: vet_https_url(target)
    # Assert
    with pytest.raises(OutboundBlockedError):
        call()


def test_public_address_is_vetted_and_pinned():
    # Arrange
    target = vet_https_url("https://1.1.1.1:8443/repo.git")
    # Act
    args = git_pin_args(target)
    # Assert
    assert args == [
        "-c",
        "http.curloptResolve=1.1.1.1:8443:1.1.1.1",
        "-c",
        "http.followRedirects=false",
    ]


def test_public_ipv6_address_is_bracketed_in_the_pin():
    # Arrange
    target = vet_https_url("https://[2606:4700:4700::1111]/repo.git")
    # Act
    args = git_pin_args(target)
    # Assert
    assert (
        args[1] == "http.curloptResolve=2606:4700:4700::1111:443:[2606:4700:4700::1111]"
    )
