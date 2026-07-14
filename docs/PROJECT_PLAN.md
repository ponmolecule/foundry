# Foundry Pilot Plan — tracking artifact (v1, 2026-07-13)

**Headcount.** Ponmile (P): deploy, infra, data pulls, all Klaros-facing. Claude build
sessions (C): everything gated in the repo. Klaros dependencies (K): Patrick (schedules,
demo audience), Roman (joint session), Ken (Clarify/data access).
**Dates that matter:** interim demo **Fri Jul 24** · checkpoint **Wed Jul 29** ·
unsupervised window Jul 30–Aug 10 · reconvene **Aug 11**.
**Rule:** nothing checks off without a green gate run (C) or a live verification (P).

## A — Deploy & infrastructure (P, this week)
- [ ] Pull bundle through PC-30 → gates → push
- [ ] Live click-through: /v3 twelve tabs; freeze → re-verify once by hand
- [ ] Railway volume at /data + env FOUNDRY_DATA_DIR=/data
- [ ] CharterIQ nav link → foundry.charteriq.app

## B — Demo spine, due Jul 24 (C; starts on P's "go")
- [ ] Patrick-workbook intake translator (CONTROL/ASSM → config; monthly→quarterly dialect documented in-config)
- [ ] Completion flags: missing-liabilities / no-loans gap conversation
- [ ] Schedule output v0: RC + RI populated in Patrick's shapes
- [ ] Prairie translation → prairie_digital_v2.json (beta = two-tranche split; v1 file untouched)
- [ ] Roster v0 on volume: open/switch; residents = Prairie + De Novo template
- [ ] Demo dry run: client-walks-in script end to end on /v3

## C — Checkpoint scope, due Jul 29 (C + P)
- [ ] RWA / standardized stack: CET1, Tier 1, Total, PCA (RC-R shape)
- [ ] Staged capital raises (engine additive; Patrick's 3-round pattern)
- [ ] ABR schedule + CONC diagnostics under REG_PARAMS
- [ ] FDIC/OCC assessment expense lines
- [ ] Retrodiction overlay v0 (P pulls real de novo Call Reports)
- [ ] Hardening for unsupervised Klaros use (auth, error paths, README for partners)

## D — Peer evidence (parallel track)
- [ ] Ratify PEER_GOVERNANCE_RULINGS (P; GPT cross-review optional)
- [ ] Extract spec v1.1: age-aligned trajectories, snapshot vocab, curation reasons, real freeze event
- [ ] CharterIQ extract job (P) → load at peers.py seam → synthetic watermark retires
- [ ] UBPR peer-group baseline as the insufficiency fallback

## E — Post-pilot roadmap (Aug 11+, sequenced then)
- [x] ~~Native monthly time basis~~ DECIDED 2026-07-14: engine stays quarterly; monthly handled at import. Pre-opening phase ships per B-2 (quarterly, no clock change)
- [ ] DTA / valuation-allowance tax layer (the "genuine addition")
- [ ] AOCI / AFS scope decision
- [ ] Lifecycle tracker completion (steps 9–10 surfaces)

## Shipped (reference, all gate-green)
v2 faithful · v2.1 (+JSX 1/3/8) · v3: Overview/flags · Configuration-as-sequence ·
Governance registry (freeze/re-verify) · Peer Cohort (synthetic, watermarked) · Examiner
Book · Capital & Ratios (REG_PARAMS 2026.07.a, derivation, chart, grid, caveats) ·
gated /docs · extract spec v1.0 · governance rulings draft · comparison memo.
