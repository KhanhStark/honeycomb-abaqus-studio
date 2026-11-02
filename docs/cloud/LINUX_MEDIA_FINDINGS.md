# Linux installation sources checked — 25 October 2026

A complete third-party 2020 Linux64 media candidate has now been downloaded and inventoried on a real Ubuntu runner. This replaces the earlier finding that no accessible media had been obtained. Publisher authenticity and license entitlement remain unverified; media discovery is not runtime qualification.

## Measured media test

[Inspection run 40198361622](https://github.com/xuankhanh24/honeycomb-abaqus-studio/actions/runs/40198361622) succeeded. Its permanent [metadata receipt](../evidence/linux-media-inspection-20261025.json) records each volume SHA-256 and exact byte count. The [mirror listing](https://www.softgozar.com/ds-simulia-abaqus_/) supplied five RAR volumes totaling 9801107603 bytes. Only the ISO was extracted: 10,066,642,944 bytes, SHA-256 `d0b227290b5f62ea826b08c18bde222417817fc0d04b91abb0072cb52ebe43ad`.

The ISO contains `4/SIMULIA_EstablishedProducts/Linux64/1/StartTUI.sh`, alongside separate CAE CAA, license-server and Isight installers. The archive's separate activation-tool directory was listed but never extracted or executed. No installation media or activation file was uploaded to GitHub artifacts/cache/releases.

The runner filesystem measured 155,897,610,240 bytes total and 91,939,274,752 bytes free initially; 72,071,540,736 bytes remained after download and ISO extraction. This is measured capacity, not a promised free-space allocation for every runner.

## Repeatable offline installation test

Dispatch `.github/workflows/linux-install-probe.yml`. The initial Ubuntu 22.04 image test reached the real installer, which exited 6 with `Ubuntu is not an authorized OS.` ([run 40200190584](https://github.com/xuankhanh24/honeycomb-abaqus-studio/actions/runs/40200190584), [receipt](../evidence/linux-ubuntu22-install-probe-20261025.json)). This failed before CAE or solver execution. `Dockerfile.ubuntu22` preserves that recipe.

The next candidate uses the official CentOS 7 container and signed CentOS Vault packages, with Ubuntu 22.04 remaining the GitHub runner host. CentOS 7 is archived/EOL; this userspace is a bounded compatibility test, not a production server commitment. No vendor installer file or OS-check binary is changed. The first CentOS attempt ([40200874592](https://github.com/xuankhanh24/honeycomb-abaqus-studio/actions/runs/40200874592)) passed OS detection and copied CAE/solver files, but stopped at Multi Territorial Account configuration. Its [failure receipt](../evidence/linux-centos7-initial-install-probe-20261025.json) is retained. The regular-user diagnostic attempt ([40201614502](https://github.com/xuankhanh24/honeycomb-abaqus-studio/actions/runs/40201614502)) captured the actual failure: the installer could not spawn `perl` for its `compLocation.pl` configuration step ([receipt](../evidence/linux-centos7-perl-diagnostic-20261025.json)). Perl is now an explicit image prerequisite, verified during image build. File copying alone is not accepted as successful installation. The workflow downloads the same media again, verifies the previously observed ISO hash, mounts the ISO read-only and runs the unmodified Established Products installer inside a container with no network, all Linux capabilities dropped and no license or repository credentials passed in. The first-observed hash pins repeatability; it does not establish publisher authenticity.

The driver selects Standard, Explicit, co-simulation, ODB API and CAE, skips installer license configuration and stops on unknown prompts. It then attempts `abaqus information=release` and `abaqus python` importing `odbAccess`. These checks do not consume solver tokens or prove a licensed simulation. Only JSON receipts and installation/command logs are uploaded. A failed test must preserve its actual error; it must not populate an accepted `runtime-lock.json`.

To repeat from the repository with GitHub CLI:

```sh
# Offline installation, version and ODB-library checks only:
gh workflow run linux-install-probe.yml -f license_smoke=false
# Add the owner's restricted private-server smoke test after offline success:
gh workflow run linux-install-probe.yml -f license_smoke=true
```

The optional smoke stage joins Tailscale only after offline checks succeed. A separate container network permits outbound TCP solely to the configured manager/vendor ports, blocks connections from that subnet into runner-host services, and disables external DNS for the container. The existing activation file remains on the owner's computer. A temporary FlexNet client configuration is removed before artifact upload; private endpoint strings are redacted from text logs. A tiny 8-element mesh supports the four-CPU Explicit test; the research model is unchanged.

Inspect `install-probe.json`, `release.log`, `odb_import.log`, then (when requested) `qualification.json` and CAE/datacheck/solver/ODB logs. Read stage exit codes and real solver completion/ODB-reopen evidence; a successful archive inventory alone is insufficient.

The [original 2020 TUI installation transcript](https://gist.github.com/branfosj/f0bfa2410f7279e5c2d0dfb58bc3c2e6) documents `DSY_Force_OS=linux_a64` and the observed installer menu vocabulary. This selects the installer's existing Linux target; Ubuntu support and runtime library compatibility still require the real tests below.

| Primary source | Observation | Current project consequence |
|---|---|---|
| [Dassault software downloads](https://www.3ds.com/support/software-downloads) | Portal covers software licensed to the account; the opened portal requires login. The user has no entitled download account. | No media obtained. |
| [IIT Kanpur Linux instructions](https://linux.cc.iitk.ac.in/lininfo/Abaqus_2026.html) and [access description](https://linux.cc.iitk.ac.in/lininfo/Abaqus.html) | Instructions link an FTP/HTTP media host; the access description specifies IITK LAN. The host did not resolve from this device. | Cannot use that source from this runner. No institutional license was used. |
| [UC Irvine installation instructions](https://laptops.eng.uci.edu/engineering-software/abaqus-fea-software) | AllOS media includes Linux. Its linked Drive folder was opened in the existing browser account and displayed “Bạn cần có quyền truy cập”. | No installer obtained; no access request was sent and no university activation files were downloaded. |
| [Abaqus 2020/2022 Ubuntu guide](https://github.com/franaudo/abaqus-ubuntu) | Original author documents Ubuntu 20.04 prerequisites and installer detection adjustments. Repository contains instructions, not media. | Candidate compatibility reference; not a recipe validated on our runner/version. |
| [Abaqus 2025 / Ubuntu 24.04 author guide](https://github.com/simfinite-engineering/Abaqus-Installation-Instructions-for-Ubuntu) and [author's explanation](https://www.simfinite.be/blog/simfinite-notes-1/installing-abaqus-2025-on-linux-2) | Author reports newer installer checks and a different OS-detection setting than older CentOS guides. Requires already-present installation folders. | Do not reuse 2017/2022 workarounds blindly for 2025. Native headless installation and library compatibility still require actual media and tests. |

Next technical acceptance remains unchanged: checksum the complete original media, inspect its Linux components and version-specific silent-install mechanism, measure disk use, select compatible runtime libraries, connect to the owner's private FlexNet server, perform real CAE/Explicit checkout, datacheck, solver smoke and ODB reopen. A reachable TCP server does not establish license/version compatibility. Never generate a successful runtime lock from documentation alone.

## Successful installation and first real CAE checkout

[Run 40202327962](https://github.com/xuankhanh24/honeycomb-abaqus-studio/actions/runs/40202327962) completed the unmodified installer with exit code 0, reported Abaqus 2020 build `2019_09_13-17.49.31 163176`, and imported `odbAccess` using Abaqus Python 2.7.15. These ran in CentOS 7 userspace on an Ubuntu 22.04 Actions host. The offline receipt continues to report no license checkout because that stage deliberately had no network.

The subsequent restricted-network stage observed a real `cae` checkout from the owner's existing FlexNet server. Model/job creation then failed because the probe's default domain count was 1 while its CPU count was 4. The next probe explicitly sets four domains. [Permanent receipt](../evidence/linux-installed-cae-checkout-20261025.json) distinguishes this partial success from a completed Explicit analysis. No runtime lock is certified from it, and functional checkout does not establish publisher license entitlement.

[Run 40203102544](https://github.com/xuankhanh24/honeycomb-abaqus-studio/actions/runs/40203102544) built the CAE model, observed real Explicit checkout of eight tokens, and completed packaging with four domains of two elements each. The MPI launcher then failed with `ssh: Command not found`; no complete analysis or ODB reopening is claimed ([receipt](../evidence/linux-explicit-checkout-20261025.json)). The next probe uses four shared-memory threads with the same four domains and double precision. [The vendor's Explicit parallel-execution guide](https://abaqus.uclouvain.be/English/SIMACAEEXCRefMap/simaexc-c-parallelexecution.htm) documents thread-based domain decomposition on one shared-memory machine. No SSH service or extra private-network port is enabled.

## Completed native smoke — 14:57 UTC

**[Run 40203978647](https://github.com/xuankhanh24/honeycomb-abaqus-studio/actions/runs/40203978647) passed every stage.** The unmodified 2020 installer completed, CAE built the eight-element model, datacheck completed at increment zero, Explicit completed the 1e-6 s step in double precision with four threads/four domains, and Abaqus Python reopened its ODB with 20 frames. Both CAE and Explicit checked out from the owner's existing Windows FlexNet server. No activation utility was run or activation file transferred. [Native receipt](../evidence/linux-native-smoke-20261025.json).

Original CAE/INP/ODB, redacted logs, receipts and a SHA-256 manifest are retained in the [public smoke release](https://github.com/xuankhanh24/honeycomb-abaqus-studio/releases/tag/linux-runtime-smoke-20261025). All 13 data files and the manifest were downloaded from a draft release and verified byte-for-byte before publication ([roundtrip receipt](../evidence/linux-smoke-release-roundtrip-20261025.json)). Thus the evidence does not rely solely on expiring Actions artifacts.

This qualifies the observed **technical smoke only**. The model is an unloaded cube, not the 7 J sphere-impact case, an absorption benchmark, or research training data. The existing license carries the previously recorded SolidSQUAD marker; successful checkout does not establish publisher entitlement. Publisher media authenticity, the production runtime lock, the full Linux 7 J comparison and full-workload Actions policy remain unverified. The production dispatch gate is not bypassed.
