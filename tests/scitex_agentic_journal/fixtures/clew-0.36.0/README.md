# Released Clew fixture

This synthetic standard-library analysis adds `[1, 2, 3]` and writes a total
of `6`. It was actually executed with CPython 3.12.14 inside the pinned CI
image. The published `scitex-clew==0.36.0` wheel recorded the run through
`clew.session`, registered the input with `register_source`, and registered
the manuscript value with `add_claim` using JSON pointer `/total`.

`evidence-bundle.json` is the unchanged output of the public `bundle export`
CLI, including its genuinely supported claim. `PROVENANCE.json` records
the producing release, image digest and file hashes. No host store, signing
key or runtime journal is part of this fixture.

`rerun-report.json` is the unedited public `bundle rerun` 1.1.0 output from
an offline replay using that wheel and a refused PostgreSQL endpoint. It
reports the same output hash and a reproduced total. The 1.0.0 compatibility
unit test explicitly changes the version in memory; it is not a recorded
1.0.0 producer artifact.

Tests copy `project/` into an owned directory and place the bundle at
`.scitex/clew/evidence-bundle.json`. The opt-in live test deletes recorded
outputs during staging, runs the analysis in isolation, and verifies the
new output independently on the host. The bundle's supported state is a
recorded assertion until those checks run; schema validation alone does
not certify its hashes or signature.
