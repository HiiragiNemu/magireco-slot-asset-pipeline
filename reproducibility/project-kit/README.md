# Project handoff kit

This directory is the repository-side index for rebuilding the current MagiaReco
analysis and render pipeline from a clean checkout of
`codex/corrected-runtime-pipeline`.

It does not duplicate the Python source tree. Instead, it lists the non-Python
files, manifests, runtime probe assets, release evidence, and large local inputs
that a collaborator must have or verify before continuing the work.

## What belongs in Git

Commit these small, reviewable files:

- Frida JavaScript probes and gadget configuration;
- PowerShell reproducibility/release scripts;
- JSON composition plans, subtitle overrides, audience exclusions, and tool locks;
- CSV/JSON/Markdown manifests, QA reports, release metadata, and research notes;
- hashes, sizes, relative paths, and reconstruction instructions for proprietary
  game inputs.

The curated list is `repo-required-nonpython-files.csv`.

## What belongs in public GitHub Releases

Public releases can contain large derived evidence bundles when they are text
or metadata artifacts:

- production manifests;
- runtime-resolved event manifests;
- GDB/Z2D/DGM/CRI mapping CSV/JSON;
- QA CSV/JSON/SRT evidence;
- research logs and bundle manifests with SHA-256 hashes.

The public release bundle script is
`../scripts/New-AnalysisEvidenceBundle.ps1`.

## What stays out of public Git and public Releases

Do not upload APKs, split APKs, OBBs, native libraries, original binary tables,
SMZ/OGG/PCM, DGM/CRI/MP4, screenshots, or extracted game media. For those files,
the reproducible handoff is fingerprint plus acquisition/rebuild method. The
large-input policy is `large-input-release-plan.csv`; the full fingerprint list
is `../reference-inputs.sha256.csv`.

## Minimum collaborator workflow

1. Check out `codex/corrected-runtime-pipeline`.
2. Install the toolchain pinned in `../toolchain.lock.json`.
3. Recreate or provide the input roots described by `../input-layout.json`.
4. Verify those inputs with `../scripts/Test-ReferenceInputs.ps1`.
5. Download the latest `analysis-evidence-*` release ZIP and unpack it beside the
   research roots when continuing from published derived evidence.
6. Use the production manifests and composition plans in this repo as the source
   of truth; do not infer CRI indexes from `ac` suffix numbers.

Latest derived evidence release recorded in this checkout:

- `analysis-evidence-v18.27-20260628`
- asset: `magireco-analysis-evidence-v18-20260628-100858.zip`
- scope: text-only derived evidence, including runtime evidence package QA,
  promotion/isolation queue, and strategy report package gates.

This kit is intentionally conservative: it is designed to make the work
auditable without turning the repository or release page into a mirror of the
game package.
