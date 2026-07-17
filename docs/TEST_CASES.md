# TEST CASES — decisions made on your behalf, in plain language
*Standing practice (adopted 2026-07-16): when a design decision comes up, I make the
call based on the Klaros charter use case, build it, and log it here so you can check
the built thing after deployment and overrule anything you don't like. Each entry:
what I decided, why, and how to check it. Newest at the bottom.*

---

## 1. Products start empty; you add what you need
**Decided:** The Products tab opens with zero products under four standing category
sections. Adding a product pre-fills it with Patrick's baseline numbers for that type.
**Why:** A charter engagement builds a specific bank; deleting nine irrelevant
products to keep two is backwards.
**Check:** Open v3.1 fresh → Products tab shows Loans / Deposits / Securities & Cash /
Other sections with no product cards, and one gold "+ Add Product" button that never
disappears.

## 2. A bank with no products still has a balance sheet
**Decided:** With zero products, initial capital sits in securities and cash and the
statements stay alive (matching Roman's model).
**Check:** Fresh v3.1, no products added → Balance Sheet tab shows Securities ≈
$58,000k and Equity $60,000k in Q1. Delete every product from a populated bank — the
balance sheet must survive.

## 3. Products you define are editable; products you import are pinned
**Decided:** Typing a product by hand gives you plain numbers that respond to every
edit. Importing a client's series pins their exact path (you can still edit via the
per-quarter overrides panel).
**Why:** A client's forecast is evidence and should survive verbatim; your own
sketch is a working hypothesis and should move when you push it.
**Check:** Add "Retail Demand" by hand, change Growth to 50% → deposit numbers jump.
Bring a forecast through the upload door → the imported path holds unless you edit
the overrides.

## 4. The Add Product menu shows only real bank products, grouped the banker's way
**Decided:** Four categories (Loans / Deposits / Securities & Cash / Other), each
with its regulatory reporting line shown as a fact underneath — no free-form "custom
product" inventing unclassifiable things.
**Why:** Everything in a charter application ultimately files on a Call Report line;
a product that can't be classified can't be filed.
**Check:** + Add Product → tiles grouped under category labels; every tile names its
Call Report line; there is no "Custom Product" section.

## 5. The wizard never asks what it can figure out
**Decided:** Choosing a charter type resolves the federal regulator automatically
(national → OCC, state nonmember → FDIC + state, etc.); capital thresholds come from
the versioned regulatory parameter set, never typed.
**Check:** Start → New engagement → flip Charter type and watch the regulator line
change by itself. Nowhere in the app can you type a capital threshold.

## 6. Impossible inputs are stopped at the door; suspicious ones are questioned
**Decided:** Organizational costs exceeding the raise (negative Day-1 equity),
negative runoff, out-of-range rates — refused with a plain-language reason.
Assumptions merely far from the engagement baseline (savings paid 1.25% when the
baseline says 2.5%; card losses at half the norm) go through **with a named warning**.
**Why:** Regulators will not accept an application that self-destructs on page one;
but consultants legitimately model bad banks on purpose.
**Check:** Wizard, capital $2M / org costs $2.5M → creation refused. Import a
workbook with a savings rate of 1.25% → it imports, with a warning naming the number
and the baseline.

## 7. Uploaded workbooks change only what a human actually edited
**Decided:** The generated Excel remembers its birth state; on re-upload, untouched
cells apply nothing (so edits made in the app meanwhile survive), fact rows can't be
vandalized, and a workbook this workspace never generated is refused.
**Check:** Download the input workbook, change ONE gold cell, upload → summary says
"Imported 1 edit" and names it. Upload it unchanged → "No edits detected."

## 8. A client's own forecast is read honestly: nothing guessed, gaps become questions
**Decided:** Upload any spreadsheet → the app inventories it (calling out hidden
sheets by name), lists candidate series, and makes YOU declare units and cadence
before anything maps. Whatever the file never specified comes back as a question
("For Digital Deposits, the materials do not specify rate paid on balances — what
should the model assume, and on whose authority?") — never a silent default.
**Why:** The 85/15 answer must be auditable: every number in the model traces to the
client's file, a named conversion, or a recorded human answer.
**Check:** Start → "Upload a forecast…" with any client file. Hidden sheets are named
in the summary. Try to confirm a mapping without picking units — refused. Finish with
something missing → the question appears on screen, phrased as above.

## 9. Where settings live: build actions on the canvas, analytics in the sidebar
**Decided:** The funds-transfer-pricing switch lives in the sidebar's Treasury
cluster (and also on Product Detail, where its columns actually appear) — not next
to the Add Product button. Sidebar globals are grouped: Capital & tax / Treasury /
Operating expenses / Other balance sheet.
**Check:** Products tab header has only the Add button. Sidebar shows the four
labeled groups; FTP checkbox sits at the foot of Treasury.

## 10. Defaults we did NOT get from the client are labeled, cited, and listed in one place
**Decided (the provenance ruling you delegated):** Values the client never supplied —
the SOFR forward path (sourced to the June 2026 FOMC projections), the beyond-Q12
rate glide, stress-test multipliers, the funds-transfer-pricing methodology, the tax
sequencing election, and the inverter's fitted reserve rate — remain in force as
**labeled engine defaults**, each carrying its source and where to change it, listed
together on the Assumptions & Notes tab under "Defaults in effect (not from the
client)." They are NOT blockers: a charter engagement needs a runnable model on day
one, and a visible, citable defaults ledger beats a wall of mandatory questions. If
you'd rather any of these require explicit confirmation before results ship, say
which — the ledger makes them individually addressable.
**Check:** Assumptions & Notes tab → the defaults card lists each item with value,
source, and "change it in …" pointer. Nothing in that list appears anywhere in the
app without its label.

## 11. Two T-vocabularies, kept apart
**Decided:** "Stage T-1…T-6" (hyphen) = the forecast-translation build stages.
"Gate T21a" (no hyphen) = automated checks, all catalogued in plain English in
docs/GATE_LEDGER.md.
**Check:** Read GATE_LEDGER.md — every check has a sentence you can understand.

## 12. Call Report schedules: assembled honestly, omissions named, ties recomputed
**Decided:** The Examiner Book tab now shows four pro forma schedules (RC balance
sheet, RI income statement, RC-E deposits, RC-R capital), built from engine output
with regulatory item numbers and codes. Three sub-decisions, all in the charter
use case's favor: (a) lines the model does not compute are **omitted and listed**
at the foot of each schedule, never zero-filled — a zero asserts a fact the model
never computed; (b) held-for-sale loan balances appear as a **memoranda row** because
the engine's own total-assets convention carries the warehouse outside the total
(disclosed in a note, tie-checked to the dollar); (c) RC-R shows Tier 1 as equity
less intangibles and leverage on quarter-end assets, each **labeled as a pro forma
proxy** rather than passed off as the regulatory definition.
**Why:** An examiner reading this exhibit must never be misled about what was and
wasn't modeled; disclosed simplification beats silent precision-theater.
**Check:** Add a couple of products → Examiner Book → four schedules render with
item numbers, RCON/RIAD codes, and Q1–Q12 columns; every schedule ends with a
"Not modeled (omitted, not zeroed)" line; RC-R names its proxies. Totals tie:
RC 12 equals the Balance Sheet tab; RI 12 equals the Income Statement's net income.

## 13. Retrodiction: the harness ships now; real-bank data is a drop-in
**Decided:** The Peer Cohort tab gains a "Retrodiction — projection vs filed
history" section: upload a bank's actual quarterly history (CSV rows: deposits /
loans / assets / equity / net_income, in $000s) and the current configuration's
projection is scored against it — projected vs actual vs error % per quarter,
MAPE per series, and the terminal-quarter miss. The summary reads it against a
15% terminal-error line, labeled explicitly as "a conversation anchor, not a
verdict." Because this build environment has no route to FDIC data, the shipped
demonstration uses a synthetic history (a golden case's own output with a known,
labeled drift), and the CSV format is documented so a real de novo's history from
the CharterIQ substrate is a data drop, not a code change. Unrecognized series
labels are refused — exact labels by design.
**Why:** The 85/15 answer needs a measuring instrument before it needs data; and
the instrument must be provably honest (its gates verify it recovers a known,
planted drift to the decimal) before any real bank's history touches it.
**Check:** Peer Cohort tab → Retrodiction section with the upload button (it must
appear even when the peer benchmark itself errors). Upload the synthetic CSV from
foundry/fixtures/retro/ → overlay tables render with red error cells past 15%, a
summary line counting series within 15%, and a report hash.

## 14. The CharterIQ substrate connection: one file, read-only, honest about its own accuracy
**Decided (Path 3, per your integration spec):** Foundry consumes your curated
database through a single client file exposing exactly the four semantic
operations you specified — institution lookup, quarterly series, peer cohort by
asset band, peer percentiles — over CHARTERIQ_DATABASE_URL, opened read-only
(the client refuses anything but SELECT before a query ever leaves the file).
Sub-decisions, all in the charter use case's favor: (a) **your accuracy caveats
ride with the data** — every capital-family payload is labeled "item-level FFIEC
CDR" and every legacy-family payload "migration pending," and capital percentiles
carry the "approximate until refreshed" caveat, so nobody can quote a legacy
number as item-level; (b) **the retrodiction series map is never guessed** —
pulling a bank's history fails closed until CHARTERIQ_RETRO_MAP (one JSON env
var) names which substrate metrics mean deposits/loans/assets/equity/net_income,
and the refusal message lists the bank's actual available metric names to choose
from; (c) **absence degrades honestly** — an unconfigured or unreachable
substrate shows exactly that on the Peer Cohort panel ("no substrate, no
numbers: nothing on this panel is ever simulated"), never fabricated figures;
(d) terminal-status reads carry your "detection-only, attribution pending
Deliverable A" note verbatim.
**Deployment steps (yours):** set CHARTERIQ_DATABASE_URL (read-only credentials,
out-of-band) and CHARTERIQ_RETRO_MAP on Foundry's Railway instance; redeploy
(requirements now include the Postgres driver).
**Check:** Peer Cohort tab → "CharterIQ substrate" panel → "Check now" shows
Connected with the metric count. "Pull from CharterIQ substrate…" with a cert
number either runs a real retrodiction or refuses with the metric-name list
(until the map is set). Every substrate number on screen carries its accuracy
label.

## 15. Staged capital raises: modeled, exact, and provably harmless when unused
**Decided:** Follow-on raises are now a first-class input — the sidebar's Capital
& tax cluster has a "Staged raises" editor (quarter + amount rows). A raise lands
at the start of its stated quarter: paid-in capital steps by exactly the raise,
the funding waterfall absorbs the cash into securities automatically, and the new
money starts earning immediately (so total equity rises by slightly MORE than the
raise — that's the earnings on it, landing in retained earnings where they
belong). The feature is default-off and provably inert when unused: the gates
re-ran every frozen reference bank with the engine change in place and every
result came out identical to the decimal.
**Why:** De novo charters routinely raise in tranches; a model that can't show a
committed Q4 follow-on can't have the capital-plan conversation.
**Check:** Sidebar → Capital & tax → "+ add a raise" → set Q and amount → Balance
Sheet equity steps at that quarter by the amount (plus a small earnings kicker in
later quarters); Capital & Ratios leverage jumps the same quarter; delete the row
and everything returns exactly. Impossible raises (quarter 13, negative amounts)
are refused with plain messages.

## 16. Modeled capital placed against real peers — capital family only, coarse on purpose
**Decided:** Once the substrate is connected, the Peer Cohort panel gains a "Place
modeled capital vs real peers" button: the modeled bank's Q12 leverage ratio is
placed against your database's real percentile rows (tier 1 and CET1), in the
asset band derived from the MODELED Q12 total assets, at the latest covered
quarter (2025 Q4). Placement is deliberately coarse — six buckets from "below
p10" to "above p90," no invented decimal percentiles. Each row carries three
honesty labels verbatim: that modeled leverage vs peer tier-1 are related-but-
not-identical measures (an anchor, not a filing figure); your item-level-vs-
legacy accuracy label; and your "approximate until refreshed" percentile caveat.
Capital family only, per your preferential-use instruction — no other metric
family renders here until its migration lands.
**Check (after deployment + substrate variable):** run any bank → Peer Cohort →
substrate panel → the button → a percentile table with placement tags and the
caveats under each row. Without the substrate configured, the button doesn't
exist and the endpoint refuses.

## 17. The Excel workbook now carries staged raises, both directions
**Decided:** Generated input workbooks include a "Staged raise N — quarter/amount"
row pair per raise on the CONTROL sheet; editing one in Excel and re-uploading
applies exactly that edit (gate-proven: one edit reported, the amount lands, the
untouched quarter survives).
**Check:** Add a raise in the sidebar → download the workbook → the raise rows
appear; change the amount in Excel → upload → summary reports exactly one edit.

## 18. Vintage corridor: real de novos, re-clocked to their own birthdays
**Decided:** The Peer Cohort page's third instrument. All banks chartered in a
pre-registered window (2018-2023: 55 institutions) have their filed histories
re-clocked so each bank's first post-charter quarter is its "age quarter 1";
the corridor is the p25/p50/p75 band of what those banks actually posted at
each age, and the modeled bank's trajectory overlays on the same age axis with
an inside/above/below verdict per quarter. Sub-decisions: (a) age quarters with
fewer than 8 contributing banks are SUPPRESSED, never estimated; (b) survivorship
is stated in the header (failures and exits counted, with the note that later
quarters contain only survivors, making the corridor flattering); (c) pre-charter
data rows are excluded as noise; (d) capital metrics carry a two-quality label
(history = legacy computation, item-level from 2025Q4) because the survey showed
full tier1/cet1 history exists at legacy quality; (e) leverage_ratio sits out
(2025-only coverage); (f) the corridor is fingerprinted and deterministic, and
the modeled overlay recomputes at render time, so it can never go stale.
**Why:** Comparing a two-year-old bank to mature banks is a category error; the
persuasive exhibit is "the model walks inside the corridor real de novos walked."
**Check (with substrate):** Peer Cohort → "Build corridor — 2018–2023 charters"
→ per-metric age tables with p75/p50/p25 rows, the modeled row in amber where it
leaves the band, verdicts, per-quarter n, the survivorship line, and suppressed
quarters showing dashes. Edit the model → verdicts update instantly.

## 19. Capital-history provenance: proxy named as proxy, and Foundry stays off the raw items
**Decided (on the substrate owner's provenance brief, 2026-07-16):** (a) cet1_ratio
is removed from the vintage corridor — pre-2025Q4 history carries the identical
proxy value under both cet1 and tier1 names, so two bands would be one proxy in
two costumes; tier1 remains, labeled: "history through 2025Q3 is a regulatory-
capital PROXY … item-derived from 2025Q4 … replaced in place by the Milestone 2
backfill." The corridor inherits the corrected history automatically when the
backfill lands — no Foundry change needed. (b) Foundry deliberately does NOT read
call_report_items: recomputing metrics from raw items would duplicate computation
logic that belongs on CharterIQ's ledger (the IP seam) and create a second writer
of truth; foundry_ro's grants stay at the three curated tables. Open question for
the owner: overrule (b) if Foundry should ever consume items directly.
**Check:** Vintage corridor shows tier1_ratio (not cet1) with the PROXY label;
placement still shows both capital rows for 2025Q4 (item-derived quarter) with
the existing percentile caveats.

## 20. Pre-opening phase (FLOOR F-010/020/021/022)
**Decided:** A pre_opening config block: expense categories with totals (monthly
schedules convert to quarterly/total at import, per the quarterly-permanent
ruling), plus a minimum Day-1 capital figure. The burn is EXPENSED into the
opening retained-earnings deficit (Patrick's I.9 convention), in both engines;
the funding waterfall seeds the asset side automatically. Results carry a
pre_open block with the cushion (raise − burn) vs the minimum and a
SUFFICIENT / INSUFFICIENT — REVIEW CAPITAL PLAN flag. Sidebar: Capital & tax
cluster → PRE-OPENING editor. Display: Examiner Book, above the schedules.
Default-off and gate-proven inert when absent.
**Check:** Add a pre-open expense in the sidebar → opening equity and retained
drop by the total; Examiner Book shows the category table, burn, cushion, and
the flag; blank categories and negative totals are refused.

## 21. Securities layer: AOCI on AFS, equity in components (FLOOR F-052/081)
**Decided:** Designated AFS/HTM books (already engine citizens) gain the AOCI
mechanism: quarterly AOCI = AFS book x annual sensitivity / 4, accumulating into
equity — retained earnings untouched, HTM immune by design (that is what HTM
means; a prior gate already proves rate shocks skip the HTM coupon). Equity now
reports in components — paid-in, retained, AOCI — with a gate proving they sum
to total equity to the penny in both engines. The white Balance Sheet gains the
designated-book and AOCI rows (zero-suppressed); Schedule RC gains 2.a HTM,
23/24 paid-in, and 26.b AOCI with both ties gate-checked. Sidebar Treasury
cluster: + AFS / + HTM book editors and the AOCI sensitivity input. AOCI's
capital treatment (opt-out election) is DISCLOSED as pending the standardized
RWA build (F-090/091, Wave 2) — leverage currently includes AOCI in equity.
**Check:** Treasury cluster → + AFS book, set AOCI sensitivity −2% → Balance
Sheet shows the designated books and a growing AOCI loss; equity components sum;
Examiner Book RC shows 2.a/23-24/26.b; zero sensitivity → AOCI identically zero.

## 22. Wave 1 close: depreciation + scheduled borrowings (F-053/061)
**Decided:** (a) Premises depreciate straight-line from an annual dollar input,
floored at zero; the expense lands in operating expense (reducing NI) — note
Patrick's own workbook declines premises WITHOUT expensing, which we fix rather
than replicate; RC row 6 and the white BS premises row read the live series.
(b) Scheduled borrowings are instruments — name, draw quarter, amount, annual
rate, term — amortizing straight-line, bearing interest on average balances,
adding funding in the waterfall; RC row 16 combines residual (overnight) and
scheduled draws; the D-P12 static-FHLB defect is fixed. Sidebar: Capital & tax
cluster gains Scheduled borrowings and Premises depreciation on the design
system. Both features default-off, additive, gate-proven inert when absent.
**Check:** Add an $8M Q2 draw at 4% for 8 quarters → BS shows the amortizing
row; borrowing interest rises ~$40k in the draw quarter; RC 16 = residual +
scheduled. Set premises depreciation 400 → premises fall $100k/q and NI drops.

## 23. Wave 2 core: standardized capital, CBLR tiering, concentrations (F-003/033/090/091/100)
**Decided:** (a) REG_PARAMS gains the PCA well-capitalized set, the standardized
risk-weight map, CCFs, and the Tier-2 ALLL cap — all with 12 CFR citations; the
floor document's 9%/8% CBLR calibration is RECONCILED to the April 2026 final
rule (8% requirement / 7% grace floor, 91 FR 22973), which governs per the
registry doctrine — the reconciliation is stated in the artifact, not silently
chosen. (b) The standardized approach computes every run regardless of CBLR
election — the election decides which framework GOVERNS, not which is visible.
(c) RWA: cash at banks share weighted 20% (the D-P6 fix, via cash_at_banks_pct),
securities as agency 20% (disclosed assumption), mortgage 50%, other loans 100%,
non-deducted MSAs 250%, OBS at the 50% default CCF. CET1 = equity − intangibles
− AOCI (opt-out default) − MSA excess; Tier 2 = min(ALLL, 1.25% RWA). (d) RC-R
gains a real Part II. (e) Concentrations: nine ratios with cited criteria;
missing inputs (C&D, largest borrower) are STATED as not provided — never a
silent zero (D-P16b); severe breaches raise Overview flags. Unit lesson logged:
product balances arrive in $000s — a double-conversion briefly understated the
loan RWA term 1000x and was caught by the crafted-breach gate before commit.
**Check:** Capital & Ratios tab → Standardized Capital table (four ratios vs
thresholds, breaches in red) and Concentrations table (C&D row reads "NOT
PROVIDED" until you supply construction_land_total). Examiner Book → RC-R
Part II. Load a CRE-heavy config → severe CRE flag on Overview.

## 24. Wave 3: income granularity + the configuration surface (F-002/036/070/071/072/141/142/143)
**Decided:** (a) A shared income_modules helper both engines consume. NIE detail:
FTE-step comp (Y1/Y2/Y3 headcount × loaded comp), category lines, Patrick's
sub×r/(1−r) other-opex gross-up kept verbatim, and FDIC/OCC assessments accrued
IN-ENGINE on the correct base — avg consolidated assets − avg tangible equity
per 12 USC 1817(b)(2)(A) (the D-P14 fix), rates in REG_PARAMS. (b) Fee modules,
every one growth-capable (D-P10 fix): trust (AUM rollforward × bp), interchange
(count × ticket × rate − network fees), payment rails (real volumes; fee income
AND rail costs booked — D-P11 fix), service charges, BaaS. (c) Per the user's
sidebar ruling: the Configuration tab is now the master surface — 13 module
activation lamps DERIVED from config presence (the honest version of Patrick's
lamp that lied, D-P13), with the structural editors (pre-opening, raises,
scheduled borrowings, securities books, NIE detail, fee modules) living there;
the sidebar keeps only iteration knobs (rates, overhead, capital, SOFR, stress).
**Check:** Configuration tab → lamps row + six structural sections; activate
Trust ($100M AUM, 50bp) → fee income rises $125k/q; sidebar no longer carries
Pre-opening / Staged raises / Securities books.

## 25. Wave 4: surfaces (F-011/012/013/112/120/122/132/133)
**Decided:** (a) An in-app CHECKS panel on the Overview: nine named assertions
computed on every run, each labeled to test exactly what it claims (D-P16 fix),
split into INTEGRITY (the arithmetic holds together) and VIABILITY (the plan
clears its commitments) — separate classes, both shown, with a gate proving an
undercapitalized plan fails viability while integrity passes: the D-P18 lesson
that Patrick's "All Pass" over a money-losing bank taught. (b) Patrick's COVER
quick-stats: 8 metrics × three years, CBLR-aware capital row. (c) Annual rollup:
stocks at Q4/Q8/Q12, flows summed (gate-checked to the penny), ratios averaged
and labeled as such — rendered on the IS and BS tabs. (d) SENS: one variable,
three full engine runs, distinct from scenario stress. (e) The results workbook
exports the five Call Report schedules with per-line codes, tie-checked.
**Check:** Overview → Model checks panel + Quick stats; IS tab bottom → Annual
Rollup; BS tab bottom → Year-End Balances; Stress tab bottom → SENS (run it);
download the results workbook → five Schedule sheets.
