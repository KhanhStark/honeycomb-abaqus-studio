# Angle input and batch execution

The re-entrant model accepts either indentation `d` (legacy default for existing
inputs) or angle `reentrant_delta_deg`, selected by `reentrant_geometry`.
Delta is measured from the inclined wall to the vertical Z direction in the XZ
cell section. It is independent of the whole-cell orientation.

`d = reentrant_cell_height / 2 * tan(delta)`; delta is strictly between 0 and 90
degrees. Geometry validation also requires an open waist with sufficient room for
the specified foil. Resolved input, preview geometry, density, CAE builder and
reports all use the derived indentation. Existing indentation-mode inputs remain
valid. The web template defaults to angle entry at 26.56505117707799 degrees,
equivalent to d=1.25 mm at h=5 mm.

## Batch UI

The web's **Chạy đồng loạt theo khoảng** section supports one or more numeric
parameters, start, stop, positive step and an option to add an unaligned end point.
Grid sampling creates every Cartesian combination, with server validation and
duplicate resolved-input removal. Preview displays each selected parameter's
resolved value and unit, including nested material properties. Invalid or inactive
axes remain visible for correction; they are not silently discarded.

Example: delta 20–30 degrees, step 5, and energy 5–7 J, step 2, produces six runs.
The web retains its 10-run cloud limit; the desktop uses the batch max_runs setting.
Desktop has the same angle/indent input modes and sequential/parallel controls
alongside its existing range editor. LHS/table inputs remain available through
advanced input; switching to range mode explicitly clears those designs.

## Scheduling and runtime

Cloud uses **one design = one GitHub matrix job = one separate four-CPU runner**.
The web defaults to four solver CPUs per run; CPU requests above four are rejected,
and smaller explicit requests remain unchanged. `execution_mode` is `sequential`
by default (matrix max-parallel=1) or `parallel` (user-selected max-parallel 1–8).
Ten runs requesting four CPUs each do not share one four-CPU machine. GitHub
account quotas and license availability may queue runners. Each runner installs
its own runtime, checks network before installation, and has its own 330-minute
budget including preparation and archival. Installation overhead means speedup
still requires measurement.

The prepare job expands and claims the batch once. Each worker claims one shard,
publishes its own Release and updates only its embedded catalog record using CAS;
sibling results remain intact. Parent cancellation reaches every active worker.
The finalizer marks runners that failed during preparation as blocked_environment;
finished runs and their verified archives are retained. The web lists every run's
Release. Qualification gates remain enforced before dispatch/preparation.

Desktop/local execution uses shared-resource admission instead:
`ram_per_run_gb` is an explicit admission budget, not measured solver memory.
Admission takes an ordered prefix whose summed CPUs, RAM budgets and predicted
scratch/output disk fit current resources after reserves. Actual RAM/disk reserves
are monitored while jobs run. The local worker recalculates at each wave.

On a four-CPU runner, two runs requesting two CPUs each can overlap. Two runs
requesting four CPUs each queue. No requested CPU count, mesh, material, duration,
precision or mass scaling is changed automatically to force concurrency.

Independent native solver processes can overlap. Build/cache/datacheck work is
serialized, preserving geometry-cache reuse across energy sweeps. Arrow,
Matplotlib/reporting and rolling publication remain serialized. A completed wave
is archived before admitting the next wave, avoiding snapshots of live ODBs.
Cloud license failures wait for retry within the existing deadline, with at most
three checkout failures before pause; finished runs are not repeated.

Live owned processes are adopted on engine restart even when no free budget remains
for new launches. Shutdown does not start reserved tasks and preserves owned native
process identity for later adoption. Stop requests terminate owned processes and
retain partial outputs. Resource planning is heuristic, and parallel execution is
not a guarantee of lower wall time for every model.

Production entitlement/runtime/platform gates remain unchanged. Native parallel
smoke attempts have not passed: the latest attempt could not reach FlexNet over
the private network (FLEXnet -7,96). A subsequent TCP-only probe also failed both
license ports. Distributed four-CPU native performance has not been benchmarked.

## Verification and review

Tests cover delta equivalence and invalid geometry, multi-axis expansion, actual
preview geometry, heterogeneous CPU admission, two concurrent test tasks, process
adoption under low free resources, shutdown preservation and cloud license retry
without duplicate records. Synthetic orchestration tests are not research results.
Frontend data tests and TypeScript/build pass; WinUI build and nine C# tests pass.

Standards review found process-adoption and shutdown defects; specification review
found heterogeneous-admission and cloud-license-retry defects. All were fixed with
regression checks. Visual review required resolved preview columns for every axis;
that change was made and verified with delta × core-material modulus on desktop
and mobile. The final independent visual verdict could not run because the reviewer
hit its usage limit; the builder verified the specific fix directly and records
that limitation rather than claiming an independent final pass.
