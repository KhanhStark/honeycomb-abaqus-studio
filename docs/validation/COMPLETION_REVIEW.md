# Completion pass review

Base: `ce025d9`. Two independent reviewers inspected the implementation pass.

## Standards

Two P1 regressions were found in the initial changes:

1. Publication preparation hard-linked existing generated README/tar files and then
   overwrote them, altering the source inode. Fixed by excluding generated destinations
   from linking when regenerating them; source-byte preservation has a regression test.
2. Linux history hashes disagreed with Git EOL normalization and browser BOM decoding.
   Fixed by publishing BOM-free LF CSV, verifying fetched bytes before decoding and
   testing every real published history against its summary peak force.

No additional documented-standard breaches were reported. Both findings are resolved.

## Spec

The independent specification review found the same two defects: retained source
mutation and deployed history checksum failure. Both violated preservation/display
requirements and are resolved by the fixes above.

Review exclusion from training, retention of histories/settings, isolation of secondary
Drive failures and informational technical evidence match the plan. No new scope
violation was reported. Production gates correctly remain closed; broad acceptance
is still incomplete as recorded in [the ledger](PLAN_ACCEPTANCE.md).

Standards: 2 findings, both resolved; worst initial issue: source mutation.
Spec: 2 findings, both resolved; worst initial issue: retained-output preservation.

Later validation includes 118 local Windows Python tests, 117 Ubuntu tests plus one
platform skip, five frontend tests, lint/types/build, real public asset verification,
real Drive backup and cross-runner recovery of the original 2.099 GB ODB. These are
bounded observations, not a claim of full native failure-matrix or physical acceptance.
