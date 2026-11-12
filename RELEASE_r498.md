# r498: Stress testing, stage 1

Built on GPT r497 (annual state and federal tax). Implements stage 1 of the reviewed stress plan: a deterministic override runner, validation, isolated configs, execution status, reproducible run records and audit export, plus basic Results with attribution and series charts.

## Engine and calculations

Base calculations are unchanged. Every existing result, config hash and run hash is identical with or without stress scenarios saved.

New engine code: `foundry/v2/stress.py` (runner, validation, attribution, run state) and `foundry/v2/stress_export.py` (workbook sheets). `config_hash` now excludes the `stress_scenarios` key, so editing scenarios never changes the base identity.

## Scenario contract

Scenarios live in `cfg.stress_scenarios`, outside assumptions. Each has an id, name, kind, version, funding setting and one or more severities. Each severity is a list of overrides.

An override names a target by stable key (`family:product-id:field`, list hops as `[id=X]`). Keys survive rename and reordering. The first time an input is chosen, the product gets a `stable_id`; this is inert to results. Inputs of switched-off products, linked results, timing settings, schedule points and dated anchors are not targets.

## Operations (phase 1)

- Multiply: relative, for example charge-offs ×2.
- Add: absolute, in pp for rates and $000s for money.
- Replace: a fixed value.

Each applies over a bounded period range (from, to, or to horizon). Single-value inputs take the whole horizon only. Delay, withdrawal and linear recovery are not available in this release and are not offered.

## Funding

Per scenario: inherit the base policy, show unfunded shortfall, or automatic borrowing. Shortfall and replacement borrowing are reported as separate measures.

## Checks before a run

1. Structural: target exists, is active and unambiguous; operation, value and window are valid; no two overrides hit the same input in overlapping windows.
2. Zero shock: each override is applied at no change and the run must reproduce the base exactly. Inputs the engine cannot rewrite yet (for example fee stock multipliers) fail by name rather than being approximated.
3. The base config is confirmed unmodified after every run, success or failure.

## Results

Comparison table grouped Earnings / Funding / Capital, with a horizon selector. Failed runs appear as alerts, never as columns. The capital line is a diagnostic gap to the configured floor, not a modeled raise.

Attribution ("Why it changed"): cumulative net income over the horizon. Each override runs alone against the base; what they do together is the interaction residual. Parts plus interaction equal the total exactly. Peak and minimum measures are not decomposed. Effects through links (for example a deposit balance feeding originations) stay with the override that caused them.

Series chart: base versus stress for net income, cumulative net income, NII, provision, borrowing expense, cash, unfunded shortfall, automatic borrowing, deposits, gross loans, equity and Tier 1 leverage, with every period in a table and CSV download.

## Run records and staleness

Each run is stored server-side per engagement with run ID, engine, base and scenario fingerprints, checks, resolved overrides (base and stressed value at start), metrics, series and attribution. A record is Current, Stale (scenario or base changed since) or Failed. Renaming a scenario does not make it stale.

## Export

Run record → Export selected to workbook adds sheets Stress Runs, Stress Overrides, Stress Metrics, Stress Attribution and Stress Series. The calculation-audit export can include stored runs. Export never re-runs anything; failed runs are exported with their errors.

## Endpoints

POST `/api/v31/stress/targets`, `/probe`, `/check`, `/run`, `/runs`, `/export`.

## Validation

- `foundry/v2/tests_r498_stress.py`: 35 checks pass (identity, structural errors, zero shock, windowed shocks, attribution reconciliation, failures by name, staleness, linked deposits, funding policies, fixed schedules, export, endpoints).
- `web/tests_r498_stress_ui.cjs`: workbench against engine-produced records (builder labels, results table equals record values, waterfall reconciles, failed runs as alerts, series chart and table, stale after edit).
- Browser end to end against a live server: a CRE charge-off ×2 plus a cost-pool ×1.3 for M13 to M24 ran, stored, and showed Current with both checks passed.

Next stages (not in this release): proposal ranking and templates, delay and withdrawal operations.
