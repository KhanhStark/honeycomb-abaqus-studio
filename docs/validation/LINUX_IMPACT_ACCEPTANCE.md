# Real Linux 7 J sphere-impact test — 25 October 2026

The solver completed the requested full 6 ms case on an Ubuntu 22.04 GitHub-hosted runner using Abaqus 2020 / CentOS 7 container userspace. The existing owner's Windows FlexNet server supplied CAE and Explicit tokens through the restricted two-port Tailscale connection. No activation file or installer binary was published. This is a development acceptance test; production web dispatch remains separately gated.

[Solver workflow](https://github.com/xuankhanh24/honeycomb-abaqus-studio/actions/runs/40206764997), source commit `0a3e9a3c0be21dcb38d0e506261e05fdfc250ae8`; [native receipt](../evidence/linux-impact-7j-20261025.json). An earlier preparation-only run was canceled to add bounded publication of small field records; no physical solve was restarted by that change. The later import-order-only cleanup does not change the running solver code.

## Input retained

The baseline is `examples/reentrant-perimeter-7J.json`: re-entrant 0-degree core, 100 x 100 mm panel, 20 mm core, two 0.75 mm skins, 0.0635 mm foil, 13.1 mm sphere, moving mass 2.65 kg, 7 J, gravity 9.81 m/s2 and four-edge perimeter clamp. Original material laws, contact, reference mesh, 120 field intervals and 1200 history intervals were retained. Double precision; no mass scaling. The resolved model was compared with the baseline before dispatch: its only changed model parameter was CPU allocation, from 8 to the runner's 4 CPUs. Four shared-memory threads and four domains were used. The one-run wall-clock budget was raised to 285 minutes; the 6 ms physical duration was unchanged.

Actual mesh: core 105,000 elements, 10,871 per facesheet, impactor 6,635; total 133,377 elements. The native solver confirmed successful completion at 6 ms after about 100,898 increments and about 62 minutes of solving. ODB contains 121 frames. Original model/CAE viewport PNGs and post-solver native figures were generated with a local software-rendered X display.

## Measured results

| Quantity | Result |
|---|---:|
| Initial kinetic energy | 6.999989 J |
| Peak raw contact force | 2257.59 N at 4.1901 ms |
| Maximum impactor travel from initial position | 6.59373 mm |
| Maximum top-centre downward displacement | 6.51550 mm |
| Maximum bottom-centre downward displacement | 0.05288 mm |
| Plastic dissipation, ALLPD | 5.97964 J |
| SEA using plastic dissipation / complete panel mass | 94.7118 J/kg |
| Complete panel mass | 0.0631351 kg |
| End impactor velocity | +0.830537 m/s |
| End contact force at 6 ms | 311.045 N |

The ALLPD figure is plastic dissipation, not every form of transferred/internal energy. The reported SEA denominator is the complete panel, including both skins and core. Missing optional ALLFD/ALLDMD/ALLCD outputs remain recorded as missing, rather than invented values. Field extrema retain their instance, element/node, integration/section-point and frame/time identities.

## Quality: review retained

Energy drift 0.0028669% (limit 1%); artificial energy / maximum internal energy 0.541304% (limit 5%); force cross-check 0.000005337% (limit 2%). These numerical thresholds passed.

The run remains **review** and `ml_eligible=false`: contact force is still above 10 N at the requested 6 ms end. The full contact/rebound episode has not ended within this window. Physical validation remains `not_established`; this result does not establish equivalence to the old circular-clamp Windows references. The physical duration was not extended automatically. The sparse viewer check found zero displacement for four sampled perimeter nodes on each skin at all 13 sampled frames; this is a bounded sample, not an all-node boundary audit ([sample receipt](../evidence/linux-impact-perimeter-sample-20261025.json)).

## Durable data and fresh-runner verification

[Public results release](https://github.com/xuankhanh24/honeycomb-abaqus-studio/releases/tag/linux-impact-7j-40206764997) retains 73 logical files, 2,168,103,598 bytes in total: original CAE/INP/ODB, requested/resolved/actual inputs, history CSV/Parquet, mesh data, reduced field statistics/extrema, a sparse field display, native figures, PDF/Word reports and logs. Native restart files are not certified or enabled. Field reductions are bundled losslessly into `field-reductions.tar` to avoid thousands of Release assets. Large files use at most 1-GiB parts; a final complete manifest records sizes, order and SHA-256. Large source outputs are hard-linked during publication, without duplicating the ODB into a ZIP.

[Fresh Ubuntu verification run](https://github.com/xuankhanh24/honeycomb-abaqus-studio/actions/runs/40213288753) downloaded and restored every Release part, verified sizes/SHA-256, safely unpacked 2,057 original reduction records, and reran export verification for 605 field/frame pairs representing 106,351,135 source field samples, with no mismatches. Research-reduced mode stores statistics/extrema, not all 106 million rows as Parquet; the full original fields remain in the ODB. The fresh verification used no solver/license. The original ODB was opened by native extraction/rendering; exact file identity was then checked after download. [Roundtrip receipt](../evidence/linux-impact-7j-roundtrip-20261025.json).

Main ODB: 2,099,076,684 bytes; SHA-256 `2337be13c5846e7184e0e925300ddf3eec7585070745577fe0d11b940f9c8036`.

Restore with `scripts/restore_cloud_archive.py`, then follow the retained RESTORE-README.txt to unpack the reduction TAR with Python's data extraction filter. Transport completeness is separate from physical quality: the complete archive retains a review case. Original binary CAE/INP/ODB bytes were retained; private license endpoint strings were removed from public text logs and inventories recomputed after redaction. The temporary license-host awake helper was stopped when the solver workflow completed.
