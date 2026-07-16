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
