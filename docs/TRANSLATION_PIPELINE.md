# Mode T — Translation Pipeline v0.1 (prescriptive)
**Companion to INPUT_SPEC §2 Mode T. Governs conversion of freeform client forecasts
into the canonical config. Doctrine: the target is closed, so translation is extraction
against a bounded requirement list with human-confirmed mapping — never freeform parsing.**

## The four arrival shapes and their treatment
| Shape | What it is | Treatment | Test case in hand |
|---|---|---|---|
| S1 Structured model | assumption tabs + statements (Patrick-like) | series detection -> mapping session -> converters | Patrick's workbook |
| S2 Statements-only | P&L/BS by period, drivers hidden | **inversion**: derive growth/yields/losses arithmetically under a stated convention sheet; residuals disclosed | synthesized from any golden's own output |
| S3 Deck/narrative | prose + a few numbers | sparse extraction -> pre-seeded wizard (Mode T degrades to Mode W) | (as encountered) |
| S4 Data dump | unit-economics / cohort CSVs | direct driver mapping w/ documented conversions | Prairie Digital |

## The five stages (all deterministic; no ML in the loop)
0. **Ingest** — read xlsx/csv (openpyxl/csv); normalize to a cell/table inventory with
   sheet, coordinates, dtype, and detected time axes. Hidden sheets included (Patrick lesson).
1. **Recon report** — machine-produced, human-read: what the file contains — candidate
   series (label-lexicon matched: deposits, loans, NIM, originations, headcount...),
   detected cadence (monthly/quarterly/annual), units guess flagged never assumed.
2. **Mapping session** — the human assigns candidate series -> requirement slots
   (archetype x field). Converters apply on assignment: cadence (monthly x3 / annual /4,
   per the standing quarterly rule), units (declared, never inferred from magnitude —
   the CET1 lesson), $-adds -> growth via per-quarter overrides. Confirmed mapping =>
   `provenance: user`.
3. **Inversion** (S2 and any statements-shaped remainder) — derive drivers from outputs:
   growth_q from balance paths; blended yield/cost from income over average balances;
   NCO from charge-off or provision lines where present. Every derived value carries the
   convention that produced it. Self-gate: golden -> its own statements -> invert ->
   re-run -> statement-series hash equality (the metamorphic test made precise:
   the hash is over the compared series, not configs — an aggregate inversion
   legitimately produces a different, smaller config). Achieved: T27, exact to
   the dollar on balances, interest lines, and charge-offs.
4. **Completion** — requirement slots still empty after 2-3 become **gap questions**
   (the conversational thesis: "no funding structure is specified for $XXXM of assets"),
   answered by the practitioner or accepted as peer defaults with provenance + citation.
5. **Emit** — canonical config + `translation_log` (source row -> slot -> conversion
   applied) + field-level provenance report. The log is a first-class artifact
   (Examiner Book appendix candidate).

## Refusals (character-setting)
- No silent auto-import: every mapping is human-confirmed.
- No invention: absent information is a gap question, never an interpolation.
- No unit guessing from magnitude; units are declared at ingest or asked.

## Build order (gates only; no calendar)
T-1 Ingest + recon report engine, proven on Patrick's workbook (S1) and Prairie (S4).
T-2 Requirement-slot model + mapping-session data structures (headless; UI later).
T-3 Converter library (cadence/units/$-adds) as pure functions with unit tests.
T-4 Inverter + its golden round-trip gate (S2 capability).
T-5 Gap engine wiring (open-questions machinery already exists) + translation_log emit.
T-6 Mapping-session UI on /v3.1 behind the "Bring your plan" door.
