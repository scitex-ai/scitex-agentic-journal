"""Unit tests for :mod:`scitex_agentic_journal._orcid` — pure-Python only.

Network tests live alongside ``test_gate1_orcid.py``; this file
deliberately exercises only the link / URL / parsing layer so the suite
stays hermetic by default.
"""

from __future__ import annotations

import pytest
from scitex_agentic_journal._gate1._errors import GateFailure
from scitex_agentic_journal._orcid import OrcidClient, OrcidLink, orcid_url

# A real, valid ORCID iD with correct ISO 7064 MOD 11-2 checksum.
# (Josiah Carberry, the canonical ORCID test record.)
VALID_ID = "0000-0002-1825-0097"


# ----- orcid_url() ----------------------------------------------------------


def test_orcid_url_bare_id_returns_prod_url() -> None:
    # Arrange
    orcid_id = VALID_ID
    # Act
    url = orcid_url(orcid_id)
    # Assert
    assert url == f"https://orcid.org/{VALID_ID}"


def test_orcid_url_sandbox_env_uses_sandbox_host() -> None:
    # Arrange
    orcid_id = VALID_ID
    # Act
    url = orcid_url(orcid_id, env="sandbox")
    # Assert
    assert url == f"https://sandbox.orcid.org/{VALID_ID}"


def test_orcid_url_full_https_input_is_normalised() -> None:
    # Arrange
    full_url_input = f"https://orcid.org/{VALID_ID}/"
    # Act
    url = orcid_url(full_url_input)
    # Assert
    assert url == f"https://orcid.org/{VALID_ID}"


def test_orcid_url_explicit_env_overrides_input_host_hint() -> None:
    # Arrange
    sandbox_url_input = f"https://sandbox.orcid.org/{VALID_ID}"
    # Act
    url = orcid_url(sandbox_url_input, env="prod")
    # Assert
    assert url == f"https://orcid.org/{VALID_ID}"


def test_orcid_url_malformed_id_raises_gate_failure() -> None:
    # Arrange
    bad_input = "not-an-orcid"
    # Act / (we assert by expected exception)
    # Assert
    with pytest.raises(GateFailure):
        orcid_url(bad_input)


def test_orcid_url_checksum_mismatch_raises_gate_failure() -> None:
    # Arrange
    # Last char flipped so the checksum is wrong.
    bad_checksum = "0000-0002-1825-0098"
    # Act
    # Assert
    with pytest.raises(GateFailure):
        orcid_url(bad_checksum)


# ----- OrcidLink.parse() ----------------------------------------------------


def test_link_parse_bare_id_keeps_canonical() -> None:
    # Arrange
    orcid_id = VALID_ID
    # Act
    link = OrcidLink.parse(orcid_id)
    # Assert
    assert link.canonical == VALID_ID


def test_link_parse_bare_id_defaults_to_prod_env() -> None:
    # Arrange
    orcid_id = VALID_ID
    # Act
    link = OrcidLink.parse(orcid_id)
    # Assert
    assert link.env == "prod"


def test_link_parse_bare_id_is_not_sandbox() -> None:
    # Arrange
    orcid_id = VALID_ID
    # Act
    link = OrcidLink.parse(orcid_id)
    # Assert
    assert link.is_sandbox is False


def test_link_parse_bare_id_renders_prod_url() -> None:
    # Arrange
    orcid_id = VALID_ID
    # Act
    link = OrcidLink.parse(orcid_id)
    # Assert
    assert link.url == f"https://orcid.org/{VALID_ID}"


def test_link_parse_explicit_sandbox_env_marks_sandbox() -> None:
    # Arrange
    orcid_id = VALID_ID
    # Act
    link = OrcidLink.parse(orcid_id, env="sandbox")
    # Assert
    assert link.is_sandbox is True


def test_link_parse_explicit_sandbox_renders_sandbox_url() -> None:
    # Arrange
    orcid_id = VALID_ID
    # Act
    link = OrcidLink.parse(orcid_id, env="sandbox")
    # Assert
    assert link.url == f"https://sandbox.orcid.org/{VALID_ID}"


def test_link_parse_sandbox_host_input_infers_sandbox_env() -> None:
    # Arrange
    sandbox_url_input = f"https://sandbox.orcid.org/{VALID_ID}"
    # Act
    link = OrcidLink.parse(sandbox_url_input)
    # Assert
    assert link.is_sandbox is True


def test_link_parse_sandbox_host_input_keeps_canonical() -> None:
    # Arrange
    sandbox_url_input = f"https://sandbox.orcid.org/{VALID_ID}"
    # Act
    link = OrcidLink.parse(sandbox_url_input)
    # Assert
    assert link.canonical == VALID_ID


def test_link_parse_equivalent_inputs_compare_equal() -> None:
    # Arrange
    bare = OrcidLink.parse(VALID_ID)
    full = OrcidLink.parse(f"https://orcid.org/{VALID_ID}")
    # Act
    are_equal = bare == full
    # Assert
    assert are_equal is True


def test_link_parse_equivalent_inputs_hash_equal() -> None:
    # Arrange
    bare = OrcidLink.parse(VALID_ID)
    full = OrcidLink.parse(f"https://orcid.org/{VALID_ID}")
    # Act
    hashes_equal = hash(bare) == hash(full)
    # Assert
    assert hashes_equal is True


def test_link_parse_distinguishes_prod_from_sandbox() -> None:
    # Arrange
    prod = OrcidLink.parse(VALID_ID)
    sandbox = OrcidLink.parse(VALID_ID, env="sandbox")
    # Act
    are_equal = prod == sandbox
    # Assert
    assert are_equal is False


def test_link_str_returns_canonical_id() -> None:
    # Arrange
    link = OrcidLink.parse(f"https://orcid.org/{VALID_ID}")
    # Act
    rendered = str(link)
    # Assert
    assert rendered == VALID_ID


def test_link_parse_malformed_input_raises_gate_failure() -> None:
    # Arrange
    bad_input = "orcid:0000"
    # Act
    # Assert
    with pytest.raises(GateFailure):
        OrcidLink.parse(bad_input)


# ----- OrcidClient (no network) --------------------------------------------


def test_client_default_env_is_prod() -> None:
    # Arrange
    client = OrcidClient()
    # Act
    env = client.env
    # Assert
    assert env == "prod"


def test_client_default_base_url_is_prod_api() -> None:
    # Arrange
    client = OrcidClient()
    # Act
    base_url = client.base_url
    # Assert
    assert base_url == "https://pub.orcid.org/v3.0"


def test_client_sandbox_env_picks_sandbox_api() -> None:
    # Arrange
    client = OrcidClient(env="sandbox")
    # Act
    base_url = client.base_url
    # Assert
    assert base_url == "https://pub.sandbox.orcid.org/v3.0"


def test_client_link_prod_returns_prod_url() -> None:
    # Arrange
    client = OrcidClient()
    # Act
    link = client.link(VALID_ID)
    # Assert
    assert link.url == f"https://orcid.org/{VALID_ID}"


def test_client_link_sandbox_returns_sandbox_link() -> None:
    # Arrange
    client = OrcidClient(env="sandbox")
    # Act
    link = client.link(VALID_ID)
    # Assert
    assert link.is_sandbox is True
