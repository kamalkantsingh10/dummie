# schemas/

Frozen JSON Schemas — the machine-readable contracts.

- `shot_log.v1.json` — the training-grade shot-log schema (FR-13), **frozen v1.0.0**,
  LeRobotDataset-aligned. Added in **Story 3.5**. All `shots.jsonl` writes validate
  against it via `dum_e.shotlog`. Bumping the schema requires incrementing the
  version string — never reshape silently.
