#!/usr/bin/env bash
# Example: Gate-1 ORCID resolvability check (issue #2 / M1.1).
#
# Invokes the public Python API from a one-liner so the same path
# Gate-1 will take from the M1 CLI orchestrator (#5) is exercised
# end-to-end. Real HTTP against pub.orcid.org — no mocks.
#
# Usage:
#   ./examples/01_gate1_orcid_resolve.sh 0000-0002-1825-0097
set -eu
ORCID_ID="${1:-0000-0002-1825-0097}"
exec python -c "
import sys
from scitex_agentic_journal._gate1 import GateFailure, verify_orcid

try:
    rec = verify_orcid('${ORCID_ID}')
except GateFailure as fail:
    print(f'GATE-1 FAIL: {fail}')
    sys.exit(1)
print(f'GATE-1 PASS — {rec.orcid_id} -> {rec.display_name!r}')
"
