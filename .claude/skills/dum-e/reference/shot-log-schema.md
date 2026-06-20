# Shot-log schema (FR-13) — human-readable

Frozen **v1.0.0**, LeRobotDataset-aligned. One JSONL line per servo tick in
`runs/<ts>/shots.jsonl`, written ONLY via `dum_e.shotlog` (validated or quarantined).

Captures the full `(state -> action -> reward)` superset so v2 training needs no
extra data collection:

- `state`: pre-move frame ref + arm `joint_pos` (deg)
- `action`: primitive + params + `joint_target`
- `target`: phrase + box + backend
- `reward`: critic score/verdict (backfilled at shot end)
- plus `episode_id`, `step`, timestamps, `schema_version`

Authoritative machine schema: `schemas/shot_log.v1.json` (added in Story 3.5).
