# Development Plan

## Phase 1 — Vertical Slice Prototype

| Status | ID | Task | Notes |
|---|---|---|---|
| ✅ | P1-001 | Battle engine (deterministic, seed-based) | `src/photo_mecha_battle/battle.py` |
| ✅ | P1-002 | Tactics DSL + 5 presets | `src/photo_mecha_battle/tactics.py` |
| ✅ | P1-003 | Reproducibility tests | `tests/test_battle.py` |
| ✅ | P1-004 | Mech stats from feature vector | `src/photo_mecha_battle/mech_stats.py` |
| ✅ | P1-005 | FastAPI stub endpoints | `src/photo_mecha_battle/api/app.py` |
| ✅ | P1-006 | CLI vertical slice demo | `scripts/vertical_slice.py` |

## Phase 2 — MVP

| Status | ID | Task | Notes |
|---|---|---|---|
| ✅ | P2-001 | User auth | `POST /auth/register`, `X-User-Token` |
| ✅ | P2-002 | Mech persistence | SQLite via `api/database.py` |
| ✅ | P2-003 | Tactic slot editor | `POST/PUT /tactics`, catalog |
| ✅ | P2-004 | Async PvP matchmaking | `POST /battles/match`, ranked queue |
| ✅ | P2-005 | Ranking | ELO-like delta, `GET /ranking` |
| ⚠️ | P2-006 | RevenueCat integration | billing stub only; SDK/store TBD |
