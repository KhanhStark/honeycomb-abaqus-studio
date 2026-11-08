# Continuous campaign refill and encrypted installer distribution

Campaign: `core-damage-v2-20261107-v6p5` (exactly 500 configurations).

## Refill

The canonical controller retains its single workflow concurrency group and CAS
ticket reservations. It reconciles all eight owners, recovers completed ODBs,
then fills available owner slots. The owner ceiling remains 20 concurrent jobs,
including preparation, postprocessing and the controller; the overall ceiling
remains 160. All unfinished configurations were already claimed at deployment.

The relay now runs after an unsuccessful tick when dependency setup succeeded,
unless the workflow was cancelled. Its deliberate delay is five seconds.
Controller startup, reconciliation, API calls and GitHub runner scheduling add
to that delay. The five-minute schedule remains a backup trigger. The existing
relay checks for a newer successor before dispatch and reconciles uncertain POSTs.

## Installer transport

Tool source: `637bbd60d83e05b7a1db39ac8d6d5dc3814baa41`.

The preparation workflow retrieves the existing ISO and verifies its original
10,066,642,944-byte size and SHA-256:

`d0b227290b5f62ea826b08c18bde222417817fc0d04b91abb0072cb52ebe43ad`.

It uploads only AES-256-GCM ciphertext to a GitHub Release, in parts no larger
than 1 GiB. Each part has an independent 96-bit nonce, authentication tag and
ciphertext SHA-256. The 256-bit key is provisioned as an Actions secret on all
eight repositories. A local recovery copy is protected by Windows DPAPI; it is
excluded from Git. The key and plaintext ISO are absent from release assets.

Workers download four parts concurrently through the release asset API and CDN,
decrypt into separate fixed offsets of a temporary ISO, authenticate every part,
then verify the original full ISO SHA-256 before publishing the local file.
API credentials are never forwarded to CDN hosts. Transport failures have
bounded retries; final digest/authentication errors cannot publish an installer.
Drive and the original pinned mirror remain transport fallbacks.

`CORE_DAMAGE_TRANSPORT_SOURCE_SHA` selects these tools independently of the
frozen scientific worker. The existing installation script, native solver,
license checks, model parameters, mesh and numerical gates are unchanged.

## Activation evidence

The primary preparation run
[42511586782](https://github.com/xuankhanh24/honeycomb-abaqus-studio/actions/runs/42511586782)
completed successfully. A fresh full ISO download, GCM authentication and original
SHA-256 verification took **132.410 seconds**, averaging **72.50 MiB/s** with four
parallel downloads. All eight repositories now pin the transport source above,
have the shared encrypted-release tag and a separately provisioned Actions secret.
All 500 models, assigned owners and original physics/input hashes were compared
before activation and are unchanged.

The release is
[`abaqus2020-encrypted-d0b227290b5f62ea-ad0a5aaf`](https://github.com/xuankhanh24/honeycomb-abaqus-studio/releases/tag/abaqus2020-encrypted-d0b227290b5f62ea-ad0a5aaf).
Its ten encrypted media assets sum to the original ISO size; the eleventh asset
contains public authentication/layout metadata and no key.

The cross-owner run
[42512989734](https://github.com/luukhank574-design/honeycomb-abaqus-studio/actions/runs/42512989734)
also completed successfully using the worker media entry point, that owner's
Actions secret and a `contents: read` repository token. It downloaded and verified
the complete ISO in **104.641 seconds**, averaging **91.75 MiB/s**. The inspection
artifact confirms `encrypted_github_release` and the same original full digest.

Seven unfinished Windows CI runs automatically triggered by workflow metadata
commits were cancelled to free campaign queue capacity. Completed checks were
preserved. Subsequent metadata deployment commits use the CI skip marker; the
focused transport tests and the two complete hosted runner transfers are retained.

Activation waits for a full fresh download on a hosted Linux runner and an
exact ISO digest match. The runner writes download seconds and average MiB/s to
`output/media-release-probe.json`; the deployment records this evidence in
`output/fast-media-deployment.json`. An additional workflow exercises the worker
download entry point using another owner's repository token and secret.

Focused tests: 40 passed (media transport, GCM authentication, corrupted parts,
ordered reconstruction, interrupted transfers, credential isolation, publisher
roundtrip and existing relay/quota checks).

These checks establish identity with the previously inventoried ISO. They do
not establish a publisher signature or new physical validation of the models.
