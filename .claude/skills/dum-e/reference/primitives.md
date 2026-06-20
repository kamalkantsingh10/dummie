# Camera-move primitives

Each primitive is a parameterized, vision-stabilized motion run inside the
calibrated servo loop. All motion routes through `arm.py`.

| Primitive | Status | Story |
|-----------|--------|-------|
| `hold_center(target)` | v1 | 2.4 |
| `push_in(target, amount)` | v1 (after Cartesian spike) | 3.1 → 3.2 |
| `orbit(target, degrees)` | v2 | — |

(Stub — filled out as primitives land.)
