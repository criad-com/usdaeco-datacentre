# Historical acceptance records

`artifacts/` keeps the latest receipt for each gate: the current generator,
the native Revit rerun, the live Sync rerun, the exterior study and the
combined family gate. Version 0.4.2 refreshes the native base update/export/import evidence; the
live rollback and exterior receipts retain their original measurements.

Superseded receipts, diagnostics, source hashes and patches are plain,
inspectable files. Version 0.4.8 expands the two former archives, preserving
all 26 member paths and file contents byte-for-byte. The family term sweep
reports **0 findings**; no files or fields were redacted or dropped.

The [records through 0.4.1](acceptance-through-0.4.1/) contain two JSON files:

- [Generator receipt](acceptance-through-0.4.1/artifacts/generator-0.4.1.json)
- [Native rerun receipt](acceptance-through-0.4.1/artifacts/revit-rerun-acceptance.json)

The [records through 0.4.0](acceptance-through-0.4.0/) contain 22 JSON files
and two patches. Original repository-relative member paths remain beneath
each directory. Historical receipts retain their measured versions and
counts; they are not current gate outputs. Read the linked files directly,
without an extraction command.

`check.py` runs the shared publication sweep over Git's tracked files and
non-ignored candidate files, including published data. Archives are rejected
by extension or signature, even when tracked inside an ignored directory.
The ordinary term sweep also reads every expanded history file.

Files through 0.4.0:

- [artifacts/camera-manifest-diff.json](acceptance-through-0.4.0/artifacts/camera-manifest-diff.json)
- [artifacts/camera-study.json](acceptance-through-0.4.0/artifacts/camera-study.json)
- [artifacts/check-0.3.4.json](acceptance-through-0.4.0/artifacts/check-0.3.4.json)
- [artifacts/check-design.json](acceptance-through-0.4.0/artifacts/check-design.json)
- [artifacts/check-exterior.json](acceptance-through-0.4.0/artifacts/check-exterior.json)
- [artifacts/check-revit.json](acceptance-through-0.4.0/artifacts/check-revit.json)
- [artifacts/column-view-exception.json](acceptance-through-0.4.0/artifacts/column-view-exception.json)
- [artifacts/corridor-height-1.6.json](acceptance-through-0.4.0/artifacts/corridor-height-1.6.json)
- [artifacts/dc-live-acceptance.json](acceptance-through-0.4.0/artifacts/dc-live-acceptance.json)
- [artifacts/exterior-camera-change.json](acceptance-through-0.4.0/artifacts/exterior-camera-change.json)
- [artifacts/exterior-gate-provenance.json](acceptance-through-0.4.0/artifacts/exterior-gate-provenance.json)
- [artifacts/exterior-sample-coverage.json](acceptance-through-0.4.0/artifacts/exterior-sample-coverage.json)
- [artifacts/family-gate.json](acceptance-through-0.4.0/artifacts/family-gate.json)
- [artifacts/family-runner-adaptation.patch](acceptance-through-0.4.0/artifacts/family-runner-adaptation.patch)
- [artifacts/family-runner.patch](acceptance-through-0.4.0/artifacts/family-runner.patch)
- [artifacts/family-schedule-hashes.json](acceptance-through-0.4.0/artifacts/family-schedule-hashes.json)
- [artifacts/generator-0.4.0.json](acceptance-through-0.4.0/artifacts/generator-0.4.0.json)
- [artifacts/output-comparison-0.3.4.json](acceptance-through-0.4.0/artifacts/output-comparison-0.3.4.json)
- [artifacts/revit-clipping-probe.json](acceptance-through-0.4.0/artifacts/revit-clipping-probe.json)
- [artifacts/revit-export-acceptance.json](acceptance-through-0.4.0/artifacts/revit-export-acceptance.json)
- [artifacts/revit-provenance.json](acceptance-through-0.4.0/artifacts/revit-provenance.json)
- [artifacts/revit-rerun-provenance.json](acceptance-through-0.4.0/artifacts/revit-rerun-provenance.json)
- [artifacts/sample-obstructions.json](acceptance-through-0.4.0/artifacts/sample-obstructions.json)
- [docs/check-result.json](acceptance-through-0.4.0/docs/check-result.json)
