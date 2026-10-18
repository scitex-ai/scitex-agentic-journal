#!/usr/bin/env bash
# Example: Gate-1 code-repo cloneability check (issue #3 / M1.2).
#
# Shallow-clones an author's code repo via real `git clone`, prints
# the HEAD commit + subject, then cleans up. Mirrors what the M1 CLI
# orchestrator (#5) will do per submission.
#
# Usage:
#   ./examples/02_gate1_code_repo_clone.sh https://github.com/octocat/Hello-World.git
set -eu
REPO_URL="${1:-https://github.com/octocat/Hello-World.git}"
exec python -c "
import sys
from scitex_agentic_journal._gate1 import GateFailure, cloned_code_repo

try:
    with cloned_code_repo('${REPO_URL}') as repo:
        print(f'GATE-1 PASS — cloned {repo.repo_url}')
        print(f'  on-disk path : {repo.path}')
        print(f'  HEAD commit  : {repo.head_commit}')
        print(f'  HEAD subject : {repo.head_subject}')
except GateFailure as fail:
    print(f'GATE-1 FAIL: {fail}')
    sys.exit(1)
"
