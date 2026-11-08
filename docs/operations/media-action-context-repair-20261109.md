# Composite action context repair — 2026-11-09

Campaign: `core-damage-v2-20261107-v6p5`, exactly 500 configurations.

## Observed failure

`development-0239` / run `42518054849` and `test-0079` / run `42517958129`
failed before Abaqus started. Both runners reported:

`Unrecognized named-value: 'vars'` in the runtime composite action manifest.

The encrypted installer transport integration at
`637bbd60d83e05b7a1db39ac8d6d5dc3814baa41` had read the repository release tag
through `vars` inside `action.yml`. That expression context is unavailable in
the composite manifest. Earlier hosted runner download probes exercised the
Python media entry point, so they did not validate this composite integration.

The two original native outputs had failed the strict contact force numerical
gate and remained archived as failed-quality evidence. Their subsequent FE
retries then exhausted preparation retries on the manifest error, taking the
campaign to `needs_investigation`. No failed-quality output was accepted.

## Repair and deployment

Repair source: `ec804565b3efa3afb04eaf51405e81fc53ffbff5`.

The calling worker and postprocessing workflows now pass repository configuration
as the declared `media_release_tag` input. The composite reads only
`inputs.media_release_tag`. The repaired source and both callers were verified
on all eight owners before resuming dispatch.

The controller was disabled during owner row updates. A stale controller run
`42515774619` had no jobs and could not be cancelled by GitHub; there were no
running controller jobs during the updates. Only the two diagnosed rows were
released to `preparation_retry`. Their old preparation counts were retained in
the repair record, then the preparation counter was reset after this specific
cause was fixed. The numerical attempt remained 1; the numerical gate was
unchanged. All 500 models, owners and recorded physics/input hashes were compared
before and after and are unchanged.

Controller phase was restored to `fixed_collection` and self-relay resumed.
The live count subsequently advanced from 362 to 363 completed samples.

## Verification

The new composite input contract regression first failed on the original action
manifest, then passed with the repair. All 41 focused media and controller tests
passed. `actionlint` passed for both caller workflows.

Replacement actual campaign jobs:

- [development-0239 / 42519001703](https://github.com/starkdzdz-eng/honeycomb-abaqus-studio/actions/runs/42519001703)
- [test-0079 / 42519008866](https://github.com/starkdzdz-eng/honeycomb-abaqus-studio/actions/runs/42519008866)

Both replacement jobs completed the actual runtime composite successfully and
entered `Solve or restore the exact predecessor state`. Both tickets have an
execution start timestamp. The latest manifest contains 363 completed,
134 dispatched/running and 3 publication-pending configurations, with no current
row errors or recovery holds. The controller has resumed successive successful
ticks. Final numerical acceptance of these running simulations remains governed
by the unchanged quality gates.

Deployment details: `output/media-action-context-repair.json`.
Live verification: `output/media-action-context-repair-live.json`.
