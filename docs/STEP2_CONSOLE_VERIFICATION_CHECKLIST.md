# Step 2 console_v2.html wiring — manual verification checklist

**Status: BEHAVIORALLY UNVERIFIED.** The change was written and syntax-checked
(`node --check`, confirmed clean) but never opened in a browser — this
environment has none. Everything below is what a human, or a future
browser-capable session, needs to actually click through before this piece can
be called verified. Do not treat `node --check` passing as behavioral proof;
it only means the file parses, not that any handler does the right thing.

Everything else in Step 0/1/2 (the engine checks, the generic fee_products
mechanic, the FIW workbook round-trip) is fully tested and does not need this
checklist — this covers only the `console_v2.html` addition.

---

## 0. Setup

Open the Foundry console on any engagement (a fresh/empty one is easiest —
avoids confusing this feature's effects with existing fee_modules output).
Navigate to the Configuration tab, "Fee modules" card. Below the five existing
pills (Interchange / Service charges / Trust / BaaS / Payments) there should
now be a second row of four buttons: **+ Custody fee**, **+ Trustee fee**,
**+ Settlement fee**, **+ Conversion (FX) fee**.

If that second row doesn't appear at all: stop here, the wiring didn't render
the section — check the browser console for a JS error before going further.

---

## 1. Adding a product — per catalog button

For **each** of the four buttons:

| Click | Expect in `cfg.assumptions.fee_products` (browser dev console: `cfg.assumptions.fee_products`) | Expect on screen |
|---|---|---|
| **+ Custody fee** | new entry `{key:"custody", basis:"balance", params:{}}` appended | new row appears labeled "custody:" with 3 fields: Balance opening ($000s), Growth (%/q), Fee (bp/yr) |
| **+ Trustee fee** | `{key:"trustee", basis:"balance", params:{}}` | same 3 fields as custody (same basis) |
| **+ Settlement fee** | `{key:"settlement", basis:"transaction", params:{}}` | 7 fields: Volume/qtr (000s tx/q), Growth (%/q), Flat fee/tx ($/tx), Flat cost/tx ($/tx), Avg ticket ($/unit), Ad valorem rate (%), Ad val. cost rate (%) |
| **+ Conversion (FX) fee** | `{key:"conversion", basis:"transaction", params:{}}` | same 7 fields as settlement (same basis) |

**Check:** clicking a button twice should append a *second* entry, not toggle
— unlike the five legacy pills (which are on/off toggles), these are additive,
matching how "+ add rail" already behaves for payments. If a second click
replaces rather than appends, that's a bug.

**Check:** every newly-added row's fields should display as **0** / blank —
"added inert," matching the existing `fmOn` convention. If a field shows `NaN`
or `undefined`, the scale-conversion arithmetic in the row renderer is wrong.

---

## 2. Editing fields — per basis, exact config path

Typing a value into a field must write to
`cfg.assumptions.fee_products[i].params.<key>` — check this directly in the
browser dev console after each edit, don't just trust the screen redraws.

**Balance basis** (custody, trustee) — entry index `i`:

| Field on screen | Type in | Expect `params.<key>` value | Note |
|---|---|---|---|
| Balance opening | `200` (meaning $200,000k) | `200000000` (raw, i.e. `200 * 1000` — wait, check this carefully, see below) | **Known scale concern**: this field uses the `$000s` display convention (matches `fee_modules.trust`'s own AUM field) — typing "200" should mean $200,000 thousand = $200,000,000 raw. Confirm the stored value is `200000000`, not `200000`. |
| Growth | `2` | `0.02` | percent → decimal |
| Fee | `8` | `8` | bp, stored raw (not divided) |

**Transaction basis** (settlement, conversion):

| Field | Type in | Expect `params.<key>` | Note |
|---|---|---|---|
| Volume/qtr | `1500` (000s) | `1500000` | same $000s-style convention as above, applied to counts |
| Growth | `3` | `0.03` | |
| Flat fee/tx | `0.2` | `0.2` | raw, no scaling |
| Flat cost/tx | `0.05` | `0.05` | raw |
| Avg ticket | `5000` | `5000` | raw |
| Ad valorem rate | `1.5` | `0.015` | percent → decimal |
| Ad val. cost rate | `0.5` | `0.005` | percent → decimal |

**Account basis** (not reachable via any of the four catalog buttons today —
only via hand-editing a config's `fee_products` list with `"basis":"account"`,
since no catalog preset uses it yet):

| Field | Type in | Expect `params.<key>` | Note |
|---|---|---|---|
| Accounts | `0.4` (000s) | `400` | **Flag this one specifically** — the `000s` convention makes sense for large account books but is awkward for a small relationship count like 400 (typing "0.4"). Worth a product call on whether account-basis should use raw count instead — this was a judgment call made without being able to see how it looks on screen. |
| Growth | `0` | `0` | |
| Fee/acct | `25` | `25` | raw, $/acct/month |

---

## 3. Deleting

Click the `×` on any fee-product row. Expect: that specific entry removed from
`cfg.assumptions.fee_products` (array `splice`, not the whole array cleared),
row disappears, other fee-product rows (if any) keep their own values
unchanged and don't shift to the wrong index.

---

## 4. The number that actually matters — does it compute right

After adding a Custody fee and setting Balance opening=$200,000k, Growth=2%,
Fee=8bp:

1. Look at the exhibit's fee-income line (or the "Fee module income Q1→Q12"
   hint text already shown under this card). It should be materially
   different from zero/from before you added the product.
2. **Exact hand-check**, if you want to confirm precisely rather than just
   "did it move": Q1 income = avg($200,000,000, $200,000,000×1.02) / 2 ×
   8/10000/4 = **$40,400** (not $000s — forty thousand four hundred dollars).
   This is the identical arithmetic `T71b` in `foundry/tests_protocol.py`
   already proves server-side; this step is confirming the *UI* actually
   produces the config that leads to that number, not re-deriving the math.

---

## 5. Round-trip — the check that closes the loop

1. With the Custody fee configured as above (and optionally a Settlement fee
   too), download the Foundry Input Workbook (the FIW export button).
2. Open the downloaded `.xlsx`, find the `ASSM_FEES` sheet. Confirm rows exist
   for `fee_products.0.key`, `fee_products.0.basis`,
   `fee_products.0.params.balance_open`, etc., with the values you entered.
   (This part — the workbook side — is already server-verified by `T71f`;
   this step confirms the *UI-entered* values reached the same place.)
3. Start a **new, blank** engagement (or use the app's "upload workbook"
   flow) and upload that same `.xlsx` cold — no prior state.
4. Confirm the reconstituted engagement shows the identical Custody fee
   product with the identical parameter values, and the identical fee-income
   number from step 4 above.
5. If you have access to the run's `run_hash` (visible via
   `/api/health`-adjacent diagnostics or the browser network tab on the run
   call), confirm it matches the hash from the original session before
   download. This is the same check `T71f` already proves server-side
   (`diff_import(data, {})` reproducing the identical `run_hash`) — this step
   confirms the *browser's* upload path exercises the same code faithfully.

---

## If anything here fails

This is new, additive code — nothing it touches should affect the five
existing named fee-module pills, which were not modified. If something in
*this* checklist fails, the fix is scoped to the `fee_products` rendering
block and `window.addFeeProduct` in `console_v2.html`, and to
`FEE_CATALOG_JS`/`BASIS_FIELDS_JS` if the field lists themselves are wrong —
it should not require touching `income_modules.py`, `fee_catalog.py`, or
`fiw.py`, all of which are already server-verified independently of this UI.
