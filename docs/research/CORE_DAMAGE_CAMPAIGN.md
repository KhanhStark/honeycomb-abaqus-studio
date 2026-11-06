# Core damage campaign v2

Approved 2026-11-06. Source baseline: 38d1e9c. This campaign is separate from the running 7 J/no-damage campaign.

## Contract

- Fixed panel 100 mm, core height 15 mm, skins .75 mm, perimeter Encastre, perfect Tie, friction .2, gap .1 mm, no gravity.
- AA6061-T6 reference on both skins and core: E=70000 MPa, nu=.33, rho=2700 kg/m3; JC A324 B114 n.42 C.002 m1.34 reference rate1/s; Abaqus damage d1=-.77 d2=1.45 d3=+.47 d4=0 d5=1.6; T20/650 Celsius. Cp900 J/kg/K, heat fraction .9, adiabatic. Linear displacement evolution .1 mm is uncalibrated, sensitivity .05/.2 mm. No claims about real foil manufacture or experimental fracture validation.
- Rigid analytical flat-nosed frustum d20/D40/h10 plus D40/h30 shank; guided translation; .77 kg prescribed mass.
- Pilot 3 velocities (10/15/20 m/s) x 3 foils (.035/.0635/.115 mm), 4 ms. Choose baseline intact rear, 1-3 mm rear response closest to 2 mm and distinct foil responses. If necessary add 5/7.5/12.5/17.5/22.5/25 m/s. No suitable load means stop before production.
- Common duration 4/8/12 ms: verify against T+4 ms, both objectives within 2%, contact ended and energy stable. Mesh factors 1/.75/.5, objective differences <=5%, same failure label. Verify 40 maximin development designs before releasing remainder.
- Domain delta25-45deg, foil .035-.115mm, cell_size4.5-8.2mm, reentrant_cell_height3-7mm; throat >max(8*foil,.5mm). Derived indent is not independent. Seed20261106.
- Initial 320 development (baseline1, OFAT40, conditional LHS279) plus independent locked test80. 40 dev+10 test per owner. Max adaptive80 (uncertainty40/Pareto24/sparse16), FE confirmations20. Numerical retries and mesh/time pilots are not independent training configurations.
- Core SEA=(ALLPD_core+ALLDMD_core)/initial_core_mass. Minimize whole-rear peak corrected by frame0. Ignore disconnected/deleted nodes for displacement and retain explicit rear failure labels. Core mass <= new reference, rear intact. No universal safety limit asserted.
- Ridge, quadratic, GPR, ExtraTrees; nested CV5/3 on development only. Target >=250 intact development, R2>=.9 and NRMSE<=.1 normalized P95-P5. NSGA-II, final untouched test and 20 new FE confirmations. Keep physical failure separate from numerical failure.

## Automation acceptance

Eight independent authorized owners: luukhanh24, KhanhStark, xuankhanh24, dzdeptrai390, khanhstarkpubg-ux, xuankhanh054-eng, starkdzdz-eng, luukhank574-design.

One configuration per solver job; independent cross-workflow continuation (240-minute wall budget, timeout330, max4 segments). Verified state preserves physics, damage and clock. Restore/hash tests mandatory. At most2 numerical retries; never rerun a solver for upload failure. Owner20 slots shared across workflows. Ramp8/20/40/80/160 bounded by actual license checkout and transfer throughput. Durable GitHub App controller on canonical repo, no local-machine scheduling dependency. Runtime license host availability remains an infrastructure dependency.

Archive INP/ODB/log/checkpoint with checksums, consolidated CSV and per-design impact history. Admission fails closed until material, mesh, time, damage-sensitivity and archive/restore gates are evidenced; production also requires the 40-design time audit. Source/runtime/protocol hashes must be pinned.

## Implementation record

### Deployment qualification, 2026-11-06

- Frozen solver source `da92733765fa95f7604516b4087d324f921ab098` passed native material validation, clean Explicit stop, damage-state continuity and checksummed restore on a different runner in Actions run `42151438827`.
- GitHub App access is verified on all eight repositories. The five new OIDC subjects include immutable owner/repository IDs required by their GitHub tokens; their configuration is restricted to the approved repository and `main` branch.
- `CORE_DAMAGE_SOURCE_SHA` pins worker physics and runtime qualification. `CORE_DAMAGE_CONTROLLER_SOURCE_SHA`, when set, independently pins orchestration fixes; it falls back to the worker source. A controller update does not relabel solver evidence or change dispatched worker source.
- Solver-stage budgets are independent of the shared owner20 runner quota. Controllers and other workflows consume runner quota but do not consume the campaign solver budget. Missing workflow metadata is counted conservatively against both.
- The earlier setup notes below are historical. Actual numerical qualification and production progress are recorded in the durable campaign catalog.

2026-11-06: schema, material deck adapter, analytic cone, per-part energy and connected rear-face metrics implemented. Reproducible 400-design draft generated at C:/UET/DO_AN/output/core-damage-v2-20261106/campaign.json. Local CAE exits before build starts; Linux validation is required. All eight CLI identities authenticated by the human. Five new repository/Actions/OIDC/App setups remain to be verified. Production is not dispatched.

### Review and verification, 2026-11-06

- Standards review: no documented standard violations; one judgment call concerning identity dictionaries. Reliability findings addressed: repository-specific App token refresh, lost analysis dispatch reconciliation, bounded numerical retries, missing execution tickets, and actual solver status in progress receipts.
- Spec review: corrected whole-model energy selection for the real `Assembly ASSEMBLY` region, rejected optional global energies available only on part regions, bounded failed qualification retries, selected-model Pareto drift across development updates, and FE dominance against all accepted known designs including the reference.
- Pareto stability uses normalized symmetric front distance <=0.05 (development P95-P5). The first fit supplies no stability evidence; the bounded adaptive batch measures the change after adding data.
- Artificial energy is checked at every recorded instant with ALLIE >=1% of initial kinetic energy; maximum |ALLAE|/|ALLIE| must be <=5%. This explicit developed-impact window avoids the initial zero denominator. The legacy ratio of separate maxima remains an exported diagnostic.
- ODB damage completeness requires U, STATUS, PEEQ, SDEG, JCCRT and temperature, with clamp connectivity. DMICRT is the requested field group; it produces JCCRT in the ODB.
- `physics_hash` pins the complete resolved solver contract, including numerics, for exact continuation compatibility. `physical_inputs_hash` and `numerical_inputs_hash` additionally separate physical design identity from mesh/time/output/solver choices. Retry identity remains in ticket, attempt and segment fields.
- Three real local Abaqus2017 material coupons passed. Cross-runner damage/thermal/motion preservation must still pass on the pinned Linux2020 runtime before pilot admission.
- Python suite: 308 passed; frontend: 12 passed and production build passed. Subsequent identity changes receive focused verification before publication.
- GitHub App installed on six owners; two installation confirmations and a usable App private key remain pending. Drive/media and local license-port preflight passed; five new repository OIDC identities remain pending human confirmation.
