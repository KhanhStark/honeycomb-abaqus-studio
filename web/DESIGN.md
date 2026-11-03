---
name: Honeycomb Studio Web Extension
description: Fluent-derived research workbench for public inspection and owner-controlled cloud jobs.
colors:
  action-blue: "#1769aa"
  action-hover: "#12558b"
  link-blue: "#145d99"
  ink: "#202d3d"
  control-ink: "#24364b"
  muted: "#566678"
  canvas: "#f4f6f8"
  surface: "#fff"
  navigation: "#edf1f5"
  selected: "#dce8f3"
  selected-ink: "#145a91"
  line: "#dbe1e8"
  control-border: "#c7d0db"
  input-border: "#bbc7d5"
  hover-surface: "#eef3f8"
  hover-border: "#8fa4bb"
  tag-surface: "#eef3f7"
  focus: "#267fc1"
  warning: "#a67426"
  error-surface: "#fff4f4"
  error-border: "#d9a6a6"
  error-ink: "#8c2727"
typography:
  headline:
    fontFamily: "'Segoe UI', system-ui, sans-serif"
    fontSize: "28px"
    fontWeight: 650
    letterSpacing: "-0.025em"
  title:
    fontFamily: "'Segoe UI', system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 650
  body:
    fontFamily: "'Segoe UI', system-ui, sans-serif"
    fontSize: "13px"
    lineHeight: 1.65
  label:
    fontFamily: "'Segoe UI', system-ui, sans-serif"
    fontSize: "12px"
  diagnostic:
    fontFamily: "Consolas, monospace"
    fontSize: "12px"
rounded:
  field: "4px"
  button: "5px"
  panel: "8px"
spacing:
  compact: "8px"
  related: "12px"
  group: "16px"
  panel: "20px"
  workspace: "24px"
  page: "32px"
components:
  button-primary:
    backgroundColor: "{colors.action-blue}"
    textColor: "{colors.surface}"
    rounded: "{rounded.button}"
    padding: "8px 13px"
    height: "38px"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.control-ink}"
    rounded: "{rounded.button}"
    padding: "8px 13px"
    height: "38px"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.control-ink}"
    rounded: "{rounded.field}"
    padding: "8px 10px"
    height: "38px"
  panel:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.panel}"
    padding: "24px"
  tag:
    backgroundColor: "{colors.tag-surface}"
    rounded: "{rounded.field}"
    padding: "5px 8px"
---

# Design System: Honeycomb Studio Web Extension

## Overview

**Creative North Star: "The Reproducible Research Workbench"**

This document records the separate web surface in Operate mode. The native WinUI 3 application remains governed by [the root design system](../DESIGN.md); this extension carries its restrained Fluent character into browser controls. It does not redefine native theme resources or desktop layout.

Quiet blue actions, system sans typography and dense labeled inputs keep the model readable. Geometry and runtime readiness sit beside the parameter sheet so a researcher can inspect inputs before preparing a job. This implements candidate 5, the workbench direction, from seed `d139dc8f`; the first body comment in `index.html` records the direction contract.

**Key Characteristics:**
- Flat light surfaces, restrained blue actions and clear keyboard focus.
- Vietnamese task language, explicit units and tabular numeric values.
- Adjacent geometry and execution evidence with truthful scope labels.
- Public inspection and owner-controlled writes.

## Colors

The normative frontmatter records the implemented light palette. The browser surface explicitly requests light color scheme; it does not inherit the native application's theme behavior.

### Primary

Action Blue identifies input checking and permitted execution. Link Blue marks navigation to evidence and public artifacts. The selected navigation item uses a pale blue surface and darker blue text; selection also has semibold text and an accessible current-page state.

### Neutral

Canvas gray separates the workspace from white panels. The slightly darker navigation surface anchors the left rail. Ink, control ink and muted text distinguish headings, values and supporting context. Thin cool borders divide parameter groups, tables and facts.

Amber marks runtime gates, accompanied by their message. Error feedback has its own pale red background, red border and dark red text; it is an alert with a dismiss action. Scientific chart and geometry colors remain evidence-specific: the blue force curve has a legend; darker and thicker geometry walls indicate double foil.

**The Evidence Color Rule.** Pair status color with text and scientific color with labels, legends or stroke differences.

## Typography

All interface controls use Segoe UI with system-ui and sans-serif fallbacks. There is no downloaded font or display face. Consolas with monospace fallback identifies JSON, hashes and diagnostics. Numeric inputs, facts and table values use tabular numerals.

Page headings use the headline role, reducing to 25px at widths at or below 800px. Section headings use the title role; parameter group headings are 14px semibold. Body paragraphs are 13px with generous line height for Vietnamese copy. Field labels and tables are 12px; units, timestamps, workspace labels and footer context are 11px. Button labels are 13px semibold, with smaller mobile navigation and account actions.

**The Unit Adjacency Rule.** Keep field units alongside their labels and result units alongside values. JSON is supplementary detail rather than the primary model editor.

## Layout

The desktop shell is a flex row with a sticky, full-height 210px navigation rail and a flexible body. The white top bar is 65px high. The centered main content has a maximum width of 1580px and padding of 30px 32px 48px. The page heading is sticky at the viewport top, backed by the canvas color, and keeps input checking and refresh available while scrolling.

The model workbench uses a flexible parameter sheet and a 310px inspector, separated by 24px. Fields use two equal columns with 17px vertical and 20px horizontal gaps. Sheets have 24px padding, inspector panels 20px, and parameter groups use top borders and 24px separation. The geometry preview uses actual returned geometry and is followed by dimensions, depth, wall count and a scope disclaimer. Tables scroll horizontally; JSON blocks scroll and have a 480px maximum height. Actions wrap.

Responsive behavior is implemented as follows:

- At 1450px and above, the inspector grows to 355px, sheets use 28px padding and field gaps become 20px by 28px.
- At 1100px and below, the rail narrows to 180px, the inspector to 270px, workbench gap to 16px and sheets to 20px padding. Fields become one column; main padding becomes 25px 20px.
- At 800px and below, navigation becomes a static horizontal scroll row above the page. Rail footer and workspace label disappear. The top bar becomes 57px high. The workbench stacks; the inspector and fields each use two columns. Result facts and setup rows become one column. The inspector note spans both columns.
- At 520px and below, fields and inspector become one column. Main padding is 24px 14px 35px and sheets use 18px 15px. Heading actions move to their own row with the primary action expanding. The unit tag wraps, geometry height is capped at 250px, and long fact values wrap within a 55% maximum width.

Batch range groups remain inside the parameter sheet, using bordered fieldsets rather than a new panel hierarchy. Each desktop row places the parameter selector, start, stop, step and remove action together; the endpoint checkbox spans the row. At 1100px and below, the selector spans three numeric columns; at 520px and below, each field stacks into one column. The resolved preview keeps every selected sweep axis in a horizontally scrollable table, including nested material parameters with their units.

Mobile retains all parameter and evidence content through vertical scrolling. The inspected reference captures are `output/cloud-web/mobile-final.png` and `output/cloud-web/desktop-final.png`; they show scrolled content, so the source establishes the complete page structure.

## Elevation & Depth

There are no box shadows, gradients or ornamental elevation layers. White surfaces, pale navigation, thin borders and spacing establish structure. The sticky heading uses a solid canvas background and z-index 2. Focus uses an explicit 3px blue outline with 3px offset. Source defines no interface transition or animation vocabulary; the data curve disables line animation.

## Shapes

Panels have gently rounded corners using the panel radius; buttons use the button radius and fields/tags the field radius. Inputs and panels use 1px borders. Status dots are circular and 7px across. Geometry is a genuine SVG plan view, not a decorative honeycomb texture. Lucide outline icons support visible labels; refresh has a dedicated accessible name.

## Components

### Buttons

Primary actions use Action Blue with white text, darkening on hover. Secondary actions use white with a cool border; hover changes both surface and border. Both have a minimum height of 38px, 8px by 13px padding and semibold labels. Disabled actions have half opacity and a not-allowed cursor. Preserve their real permission and state constraints. Text actions in the inspector are borderless blue, with a 30px minimum height.

### Inputs / Fields

Text, numeric and select controls use a white surface, cool input border, 4px corners and 8px by 10px padding. Labels sit above controls; units sit beside labels. Conditional model fields follow topology, ball-size, loading and clamp choices. The advanced JSON area is expandable, uses monospace, resizes vertically and applies changes through a named action. All interactive elements share the explicit focus-visible outline. A skip link appears on keyboard focus.

### Angle input and batch ranges

The re-entrant geometry selector switches between indentation and δ measured from vertical, showing only the active input. The geometry inspector pairs δ in degrees with resolved indentation in mm. The parameter metadata states the relationship `d = h/2 × tan(δ)`; input checking returns the resolved values rather than treating the entered angle as a solved result.

A labeled fieldset holds each sweep axis, with a unit-bearing parameter selector, start, stop and step inputs, a remove action and an optional endpoint checkbox. Duplicate parameters are disabled in the selector. The live status distinguishes an invalid range from the estimated Cartesian combination count and explicitly flags counts above the cloud limit of 10 runs per batch. JSON-backed value lists and LHS/design tables retain a named route back to range editing.

Execution defaults to sequential. Concurrent mode reveals a maximum-run input, alongside declared RAM per run in GiB; CPU per run stays in the model parameters. Supporting copy explains resource admission with the four-CPU reference runner and identifies estimates as estimates. The checked preview distinguishes requested from effective concurrency; the worker rechecks CPU, RAM, disk and license availability before execution. These controls preserve runtime gates and owner permissions.

Preview columns include every selected sweep axis, then resolved δ/indentation for re-entrant geometry, energy, velocity, CPUs and input identity, with duplicate columns removed. Nested face/core material names carry their context and units; resolved values remain traceable through the input hash. Keep the preview inspectable before saving a study.

### Navigation

Four icon-and-text tasks cover configuration, jobs, data and connections. Desktop navigation is a quiet rail with a pale blue selected item; mobile keeps the same tasks in a horizontally scrollable row. Avoid substituting an icon-only mobile menu. Public source and evidence links remain real links.

### Cards / Containers

The central parameter sheet is the largest white bordered container. Geometry and readiness are separate inspector panels. Tags provide compact unit or provenance context. The interface uses borders to organize groups inside panels rather than a card for each field.

### Geometry and readiness inspector

The SVG preview reports the selected plane and actual wall segments, with stronger double-foil strokes. Dimension facts carry units. The disclaimer explicitly distinguishes geometry from mesh or solver output. Readiness lists actual gate messages and links to connection evidence. Linux acceptance, license and platform-policy gates remain visible and execution remains blocked until their evidence allows it.

### Tables, results and feedback

Preview tables preserve resolved energy, velocity and input identity. Job tables lead to retained detail and downloadable history. Reference curves identify Windows provenance and old circular-clamp scope; results do not claim Ubuntu or four-edge-clamp equivalence or experimental validation. Metrics retain N, J and mm units. Loading, empty and error messages describe the actual state and available next action.

## Do's and Don'ts

### Do:
- Do preserve the native application's root design authority while extending this browser surface.
- Do keep units, model choices, provenance and runtime gates visible near the affected action.
- Do preserve keyboard focus, skip navigation, text status and horizontal access to wide tables.
- Do use actual geometry, measured status and recorded scientific data with their scope labels.

### Don't:
- Don't present public inspection as permission to save or control jobs.
- Don't imply Linux, license or platform-policy acceptance from a successful input preview.
- Don't call solver completion physical validation or geometry preview a solver result.
- Don't add decorative shadows, display fonts or imagery that obscures the dense research workflow.

<!-- Scan evidence: web/src/style.css, web/src/App.tsx, web/index.html; direction seed d139dc8f / candidate 5. Documents implemented web behavior; no independent browser verification was performed by the documenter. -->

## Reduced field display extension

The existing Data task now includes a lazy-loaded canvas viewer below the reference history. This is an Operate feature within the same visual system. Four labeled controls select the field, instance, orthographic projection and displacement scale. A fixed range across all displayed frames prevents color changes caused solely by legend rescaling. A sequential scientific palette interpolates navy `(36,55,111)`, blue `(40,116,166)`, cyan `(67,174,189)`, amber `(234,201,99)` and ochre `(194,103,33)`; gray `#e1e5ea` means an unrecorded value, accompanied by text. These are scientific encodings, separate from action/status colors.

The canvas preserves its fitted viewport over time and exposes a textual field/time description. A labeled slider and explicit play/pause button control frames; animation starts paused. The adjacent scale states units, missing-data behavior and deformation exaggeration. A disclosure table gives sampled element/node identities and values. Copy explicitly identifies sparse sampling, original Windows/circular-clamp provenance and the difference between sampled and whole-ODB extremes.

Controls use four columns on desktop, two below 800px and one below 520px. Timeline controls wrap on narrow screens. A file-open control remains keyboard focusable with the shared visible focus treatment. Loading, malformed-file, checksum-failure and missing-field states have readable feedback. Desktop and 390px mobile were inspected in the actual browser; mobile document width did not exceed the viewport. See `output/cloud-web/field-desktop.png` and `field-mobile.png`. The mechanical detector found advisory mismatches in pre-existing stylesheet colors/type ramp; these were recorded without altering the established surface outside this extension.

<!-- Angle/batch extension evidence: web/src/App.tsx, web/src/BatchSweep.tsx, web/src/style.css and web/service/models.py. Preserves the incumbent Fluent workbench; no new visual world or approved comp. Root agent performed DOM interaction and overflow checks and captured output/angle-batch-ui/desktop-detail.png, mobile.png, desktop-final.png and mobile-final.png; the documenter did not independently run a browser. A finish review identified missing arbitrary sweep-axis preview columns; implementation now includes them. A final reviewer verdict was unavailable, so no final reviewer pass is claimed. -->

## Per-run solver download extension

The job data folder includes a labeled selector for one archived run and attempt, carrying its sweep parameters and source identity. A bordered fieldset offers CAE, ODB and INP checkboxes; unavailable types are disabled and marked as not yet archived. The selected-file table shows filenames and binary sizes, followed by a total in MiB or GiB. These controls reuse the existing Fluent fields, table and wrapping action row within a top-divided section.

The primary action downloads a Python 3.11+ helper for only the selected files; the secondary action downloads their checksum manifest. Supporting copy explains verified resume, SHA-256 checks, the local output subfolder and preservation of the original Abaqus file version. Downloading does not convert CAE/ODB to Abaqus 2017. Empty archives show a refresh instruction, no selection disables both actions, preparation disables controls, failures use an alert, and helper handoff uses a status message with its command. The message confirms browser handoff rather than completed solver-data transfer.

The selector stays within the available width, file-type choices and actions wrap, and wide tables remain scrollable. Long filenames and commands have wrapping rules. The root agent verified the desktop and 390px mobile presentation with no mobile overflow; reference captures are `output/solver-download/desktop.png` and `output/solver-download/mobile.png`. The independent finish reviewer approved all five material areas without findings. The documenter inspected source and did not independently run a browser.

<!-- Per-run download evidence: web/src/SolverDownload.tsx, web/src/JobDataFolder.tsx and web/src/style.css. Local Operate extension; incumbent frontmatter and visual identity preserved. -->
