# Full-field rolling storage

Implemented for the qualified cloud worker's `full` profile. Qualification gates
are unchanged. The desktop engine retains its original local behavior by default.

## Data path and bounds

The Abaqus producer still emits numeric NPZ blocks with an eight-ready-block
backpressure limit. The engine writes one Zstd Parquet block and checks its row
count. A cloud sink groups blocks into volumes bounded by 256 MiB by default,
including TAR overhead; it rejects a single block that cannot fit. It retains the
local Parquet until GitHub confirms the volume's SHA-256 and size. Publication
temporarily holds the pending Parquet plus one volume, not the whole Full export
plus a duplicate ZIP. A failed upload retains local Parquet; a successful upload
writes durable references/receipts before eviction. The ODB is never evicted.

Each receipt retains the original Parquet checksum, bytes, source row count,
field/frame/component statistics, exact extrema locations and contact-force sum.
Summary and export verification can read these lightweight receipts after eviction.
Crash leftovers with both local Parquet and receipts are counted once, after a
checksum comparison. Each successful eviction is removed from the pending set
immediately so retry does not revisit deleted files.

Volumes use immutable `streamed-parquet/<sha256>/<name>.parquet` payload paths.
This avoids ambiguity when an interrupted extraction is moved to postprocess
history and a new extraction uses the same original field path. The final Release
manifest includes every committed volume. Receipt JSON is bundled with reductions
to avoid one Release asset per tiny record. The normal Release asset and job
limits still apply; oversized workloads must not be described as unlimited.

## Restore

```shell
uv run python scripts/restore_cloud_archive.py artifact-manifest.json restored --unpack-fields
```

The restorer verifies volume parts and whole-file hashes. Unpacking rejects unsafe
paths, links, non-file members and conflicting existing files. It checks every
original Parquet checksum, then hard-links immutable payloads to the original
active/historical field paths. Existing original ODB/CAE/INP bytes are unchanged.

## Observed acceptance

[Run 40264518098](https://github.com/xuankhanh24/honeycomb-abaqus-studio/actions/runs/40264518098)
used six existing Parquet blocks from the Windows Abaqus 2017 hexagonal 7 J
circular-clamp ODB export: 85,394 rows sampled from first/last U, S and PEEQ frames.
It wrote five bounded volumes, verified upload before eviction, published the
complete **sample** archive, restored all original bytes and rechecked the source
row count without double counting. [Receipt](../evidence/rolling-native-fields-20261026.json).

No new solver ran. This is storage acceptance with native numeric data, not an
end-to-end Linux Full simulation or a complete field dataset. Software tests also
cover rejected upload digests, failure on the second eviction, historical extraction
renaming, unchanged originals, unsafe TARs and repeated restore.

Independent review found the second-eviction retry and historical-path defects in
the initial implementation. Both were fixed and have regression tests. Native Full
profile/runtime integration remains a separate acceptance step after external
authorization requirements are satisfied.
