# Hardening R2: GrayPond §6 Ingestion Pipeline + §7 Dedupe/Delta Review

**Reviewer**: RainyBasin
**Date**: 2026-03-01
**Scope**: All 16 GrayPond beads against spec §6 (lines 784-880) and §7 (lines 881-968)

## Spec-to-Bead Alignment Matrix

### §6 Ingestion Pipeline (10 beads)
| Spec Requirement | Bead ID | Status |
|---|---|---|
| PIPE-001 seven-stage pipeline | bd-3dh | Covered |
| Capture stage | bd-2b0 | Covered (fixed: added milestone:MVP1) |
| Normalize stage | bd-1xn | Covered |
| Fingerprint stage | bd-kyc | Covered |
| EXT-001 extract stage | bd-fd9 | Covered |
| Compare/Dedupe stage | bd-1gj | Covered |
| DEL-001 Delta stage | bd-1ag | Covered |
| Propose+Queue stage | bd-1y4 | Covered |
| PIPE-002 atomicity | bd-1ob | Covered |
| IDM-001 idempotency | bd-2fm | Covered |

### §7 Dedupe/Delta Engine (6 beads)
| Spec Requirement | Bead ID | Status |
|---|---|---|
| DED-001 match classes | bd-1vr | Covered |
| DED-002 near-dup merge | bd-17s | Covered (fixed: removed AC bleed) |
| DED-003 conflict detection | bd-1q3 | Covered |
| DEL-002 novelty scoring | bd-3h3 | Covered (fixed: dep direction + added dep) |
| CONF-001 conflict resolution | bd-1si | Covered |
| CONF-001 MVP2 interactive | bd-j46 | Covered |

**Coverage: 16/16 beads map to spec requirements. All 11 MUST requirements and 22 ACs verified.**

## Fixes Applied (4)

### Fix 1: bd-2b0 (Capture) — Missing milestone label
- Added `milestone:MVP1` label (capture is foundational stage, required in MVP1)

### Fix 2: bd-3h3 (DEL-002 novelty) — Reversed dependency direction
- **Was**: bd-3h3 depended on bd-1ag (Delta stage)
- **Should be**: bd-1ag depends on bd-3h3 (Delta stage needs novelty formula)
- Removed bd-3h3→bd-1ag, added bd-1ag→bd-3h3

### Fix 3: bd-17s (DED-002) — AC bleed from DED-003
- AC-5 contained DED-003-4 content ("log warning when match_score in [0.70, 0.85)")
- Removed since bd-1q3 (DED-003) already covers this requirement

### Fix 4: bd-3h3 (DEL-002) — Missing dependency on DED-002
- Added bd-3h3→bd-17s dependency (novelty scoring needs near-dup merge results)

## BV Insights Summary
- **Total nodes**: 135 (includes tombstones from consolidation)
- **Edges**: 115
- **Cycles**: 0
- **Critical path through §6**: bd-2b0 → bd-1xn → bd-fd9 → bd-1gj → bd-1ag → bd-1y4 → bd-3dh → bd-1ob (length 8)
- **Top bottleneck**: bd-3dh (PIPE-001 orchestrator) — highest in-degree in §6 subgraph

## Quality Assessment
- **Titles**: All action-oriented
- **Scope**: Each bead is single-responsibility
- **ACs**: Specific and testable (after AC bleed fix)
- **Dependencies**: Correct direction and completeness (after dep fixes)
- **Milestones**: Properly assigned (after MVP1 fix)
- **No missing beads**: All MUST requirements have corresponding beads

RainyBasin signing off Hardening R2.
