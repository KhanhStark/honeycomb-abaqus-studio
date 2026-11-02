# Original cloud plan: acceptance ledger

Updated 26 October 2026. This ledger separates delivered software, observed tests,
scientific validation and external authorization. The overall plan is **not yet
accepted for production**. A successful solver checkout does not establish entitlement.

| Requirement | Status | Evidence / remaining work |
|---|---|---|
| Same repository, public source/results | Accepted | `xuankhanh24/honeycomb-abaqus-studio`; retained Releases |
| Measure actual Ubuntu resources | Accepted | [Observed runner](../evidence/cloud-ubuntu-20261025/environment.json), 145.19 GiB total; free space measured per job |
| Real Linux install, CAE, Explicit, datacheck, ODB | Technically accepted | [Native smoke](../evidence/linux-native-smoke-20261025.json), [full impact](LINUX_IMPACT_ACCEPTANCE.md) |
| Private two-port license connection | Technically accepted | [Network acceptance](../evidence/cloud-web-20261025/owner-and-network-acceptance.json); activation stays on STARK |
| Publisher media authenticity and cloud license entitlement | Blocked externally | No publisher verification or authorization supplied; current activation contains a SolidSQUAD marker |
| Intended full-workload Actions eligibility | Blocked externally | No applicable confirmation supplied; no production dispatch enabled |
| Production runtime lock and integrated web-to-solver run | Not accepted | Requires authorized media/runtime plus policy qualification, image digest, and end-to-end catalog dispatch/cancellation acceptance; manual development trial is separate |
| Vercel web, owner-only administration | Accepted within tested scope | [Deployment](../evidence/cloud-web-20261025/git-deployment-acceptance.json), owner/CSRF/idempotency tests; real owner login/draft creation |
| Display real results, histories, fields, reports and comparison | Delivered | Linux perimeter 7 J plus three legacy Windows circular-clamp references. Every history is verified before decoding; missing optional values remain null. Comparison table labels differing clamps. Sparse field display is not the full ODB mesh |
| Sequential worker, batch limit, deadline | Implemented; native failure matrix pending | 10 runs, 4 CPUs, 285-minute local execution budget within 330-minute workflow. Local deadline works during GitHub outage; cancellation requests graceful stop before archival |
| Original CAE/INP/ODB and exports retained | Accepted for measured trial | [2.17 GB complete archive](https://github.com/xuankhanh24/honeycomb-abaqus-studio/releases/tag/linux-impact-7j-40206764997), fresh-runner restore/export verification |
| Bounded publication without duplicate ODB ZIP | Accepted for measured trial | One <=1 GiB upload part, same-filesystem hard links, tiny reduction records bundled losslessly; source-preservation regression test |
| Interrupted upload recovery across fresh runners | Accepted for real ODB | [Run 40257805866](https://github.com/xuankhanh24/honeycomb-abaqus-studio/actions/runs/40257805866): interrupted after first acknowledged 1 GiB asset, reused identical asset ID, restored original 2,099,076,684-byte ODB with matching SHA-256 |
| Secondary Drive tables, reports, histories and settings | Accepted for measured trial | [Run 40257023914](https://github.com/xuankhanh24/honeycomb-abaqus-studio/actions/runs/40257023914), 39 source files checksum-verified before preparing backup, readable backup verified; review sample excluded from training. Credential encrypted in repo secret, never archived |
| Numerical quality thresholds | Passed for measured trial | Drift 0.00287%, artificial energy 0.541%, force cross-check 0.00000534%; thresholds remain 1% / 5% / 2% |
| Physical acceptance / matched old reference | Review / pending | Contact still 311 N at 6 ms. Old Windows reference uses a different clamp; no matched-condition equivalence claimed. Original physical duration remains unchanged |
| Native loss-of-license/resource/timeout/cancel matrix | Partial | Software failure-injection tests exist. Full native cloud matrix remains unaccepted |
| Full-profile rolling export/upload with eviction | Implemented; storage accepted on native sample | [Rolling fields](../research/ROLLING_FIELDS.md): bounded NPZ/Parquet/volume path, upload verified before eviction, exact original-path restore. Real GitHub acceptance used 85,394 existing native rows; complete Linux Full simulation acceptance remains pending |
| Native restart across runners | Disabled | Optional feature; no unsupported restart or physical-time splitting |

## Review of this completion pass

See [the two-axis review](COMPLETION_REVIEW.md).

Standards review found two regressions: publication could modify linked source
README/tar files, and Linux history verification disagreed with Git EOL/BOM handling.
Both were repaired with regression checks. Spec review independently found the same
two issues; no additional new scope violation was reported. Review was against
pre-pass revision `ce025d9`; subsequent fixes include exact-byte history parsing,
source preservation and the real large-ODB recovery test.

Software checks before the rolling extension: 118 Python tests passed on Windows; Ubuntu passed the matching
suite with the platform-specific skip. Frontend has 5 passing data tests, TypeScript
and production build. The final CI run links and production observation receipt
are retained alongside this ledger. These checks do not certify physical or
license acceptance.

No purchase, substitute solver, fabricated result, arbitrary shell input, license
activation upload or production-gate override was introduced.
