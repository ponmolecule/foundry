# Foundry Engagement Lifecycle — Authoritative Spec

Status: **APPROVED DESIGN — not yet implemented.** This document is the single
source of truth for how engagements are created, loaded, edited, saved, reverted,
and deleted, and how unsaved work is protected. It supersedes the ad-hoc behavior
that accreted across `_uploadedOriginal` / `_pristineJSON` / `changedSinceUpload`
and the multiple save paths. Implement against this; test against the matrix at
the end.

Design rationale for every decision is recorded so we don't relitigate it later.

---

## 1. Why this rewrite exists

The old behavior felt random because there was no single model. Two hidden
baselines (`_uploadedOriginal` drove the "changes since upload" badge;
`_pristineJSON` drove the unsaved-work guard) were updated **inconsistently**
across seven entry points, a badge meant three different things, and the autosave
surfaced as a fake selectable engagement. Every fix was a patch on one symptom.

This spec collapses all of that into **one baseline, four states, one guard**.

---

## 2. Core model: one baseline, four states

There is exactly **one** hidden baseline — *the last clean state* — set at exactly
two moments: when a config **loads** (create / upload / open / example) and when it
**saves**. Everything reads from this one baseline. (This replaces the two
inconsistent baselines.)

A config in the workspace is always in exactly one state:

| State | Meaning | Badge |
|---|---|---|
| **EMPTY** | Nothing loaded — the known-clean starting point. | (none) |
| **CLEAN** | Matches its last saved/loaded state exactly. | (none) |
| **MODIFIED** | Edited since the clean baseline. | "● N changes since save/upload" |
| **NEW-UNSAVED** | Freshly created, never saved. | "Unsaved — not saved yet" (no count) |

**NEW-UNSAVED shows no change count** — a created engagement's setup edits *are*
the creation, not a deviation from anything. (This is the principled fix for the
"18 phantom changes" bug — it becomes a rule, not a patch.)

---

## 3. Landing — when an engagement becomes real

An engagement **lands** — becomes a real, saveable config in the workspace — when
its source fully materializes:

- **Upload** finishes parsing → lands **CLEAN** (baseline = the uploaded file).
- **Creation wizard** completes into Configuration → lands **NEW-UNSAVED**
  (baseline = the just-created config).

The wizard already enforces name + capital + ≥1 product before it can finish, so
"landed" always means substantive — there is no separate "done configuring"
moment to detect (that's a state of mind, not an event).

**Landing never saves.** Saving is always the explicit chevron action.

### The asymmetry (correct, not a gap)
- Upload lands **CLEAN** because the file is an external, immutable source of truth
  — reverting means "back to the file," and nothing is at risk if unsaved (the file
  is the safety net).
- Creation lands **NEW-UNSAVED** because there is no external artifact behind it —
  its only source of truth is the store, and it isn't in the store yet.

---

## 4. The landing nudge

Once, at the top of the Configuration tab on the first render after landing
(applies to **both** upload and creation — symmetric, so the user never has to
know the source to understand the prompt):

> **"[Bank name] is ready. Save it as an engagement now? [Save] [Not now]"**

- Fires **once** at landing; never returns (editing fields / switching tabs does
  not bring it back).
- Inline banner at the top of Configuration — not a modal; does not block work.
- **[Save]** → the explicit chevron save (prompts for name) → CLEAN.
- **[Not now]** → dismiss; the quiet state badge carries the reminder afterward
  (upload stays CLEAN; creation stays NEW-UNSAVED).

---

## 5. Saving is explicit (no autosave to named engagements)

Only the **chevron save** (one save path; prompts for a name) writes to the store.
A named engagement never changes except when you deliberately save it. On save,
the current state becomes the new clean baseline → CLEAN.

Rationale: autosave-over-the-file is dangerous here because the app has **no
version history**. A user running a destructive what-if on a good saved engagement
would silently overwrite it with no undo. Explicit save + the leave-unsaved bar +
the invisible draft net gives "never lose work, never nagged" *without* the
overwrite risk. (This is the deliberate "Option A" choice.)

---

## 6. The state badge (by the chevron)

A quiet **status label**, not a clickable change-list:
- CLEAN / EMPTY → nothing.
- NEW-UNSAVED → "Unsaved — not saved yet".
- MODIFIED → "● N changes since save" (or "since upload").

The old `changedSinceUpload` light-up badge and its itemized click-dialog are
**deleted** (not hidden). The itemized diff survives only inside the leave-unsaved
bar's "See changes" (§7), on demand.

---

## 7. The leave-unsaved bar

Appears **only** when leaving a MODIFIED or NEW-UNSAVED config via an action that
would discard it (create / upload / open / example / reset / switch). One inline
bar:

> **"Unsaved changes — [Save] [Discard] [See changes] [Cancel]"**

- **[Save]** → chevron save, then proceed with the action.
- **[Discard]** → drop edits, proceed.
- **[See changes]** → expands the itemized diff **inline, on demand** (reuses the
  existing `_diffCfgAgainst` against the one baseline). Default path shows no list.
- **[Cancel]** → stay put.
- From CLEAN or EMPTY the bar **never appears** (nothing to lose) — so the user is
  never nagged when they haven't changed anything.

---

## 8. Revert vs. Reset-to-uploaded-file

Two distinct escape hatches, different targets, different availability:

- **Revert to last save** — one step back to the last clean baseline (the last
  save). Discards edits since then. Available on any MODIFIED engagement. (Step 7
  → last save, not → 0.)
- **Reset to uploaded file** — all the way back to the uploaded file; discards
  every edit **and** every save since upload. **Upload-sourced engagements only.**
  Reloads the parsed original the app already holds; hides (not greys) if that
  original isn't retained.

Both route through the leave-unsaved bar first if there are unsaved edits — neither
can silently discard work.

**No equivalent for created engagements.** "Reset to creation" would only return
the *skeleton* the wizard produced (the least-developed version), which nobody
wants — there is no external artifact to reset to. The asymmetry is correct: the
action simply doesn't appear on created/example engagements. Revert + New/Clear
cover the real needs.

---

## 9. Delete

- **Delete the currently-open engagement** → confirm → workspace goes **EMPTY**
  (bank name + products cleared; no residue).
- **Delete a different engagement** → removed from the list **immediately**; the
  open workspace is untouched.

---

## 10. New / Clear workspace (Reset button)

A visible action → workspace **EMPTY**. Routes through the leave-unsaved bar first
if there is unsaved work. This is the guaranteed known-clean starting point that
was missing — every other action can reason from a predictable state.

---

## 11. Draft net (crash recovery) — invisible

A single rolling snapshot writes underneath **while there is unsaved work**. It
**never appears in the engagement list** and is never a selectable engagement.

On boot, **only if** a prior session ended with unsaved work:

> **"Recover unsaved work from your last session? [Recover] [Discard]"**

That one boot prompt is the only time it is ever visible. A saved, clean
engagement open at crash time produces **no** prompt (nothing was unsaved).

Rationale: the crash-recovery *concept* is sound (don't lose unsaved work); the old
*implementation* was the whack-a-mole because it surfaced as a fake engagement.
Making it invisible keeps the benefit and removes the clutter.

---

## 12. Engagement identity is fully editable in Configuration

Everything the wizard collects is editable in Configuration afterward — the wizard
is a convenience for first entry, not the only place these can be set:

- **Bank name, location, charter type** — currently captured once and then have no
  editing surface. This is an oversight. Charter type especially drives the
  **regulator** (OCC / Fed / FDIC); picking the wrong one today is unfixable short
  of recreating the engagement.
- **Starting capital, pre-opening cost** — already editable; keep.

Add a small **"Engagement identity"** block in Configuration exposing all of them,
charter type as a dropdown that **re-derives the regulator** when changed. Rule:
*nothing the wizard collects is captured-once-then-frozen.*

(Scoped as its own build step + its own tests; it rides the same Configuration
surface the lifecycle work touches.)

---

## 13. The demo script (four sentences)

1. Loading anything makes it the workspace — uploads/opens start **clean**, a new
   creation starts **unsaved**; either way you're nudged once to save it as an
   engagement.
2. Editing shows the change count; **Save** (you name it) sets the new clean
   baseline; **Revert** drops edits back to it; **Reset to uploaded file** goes all
   the way back to an uploaded original.
3. Leaving unsaved work pops a one-tap **Save / Discard / See changes / Cancel**
   bar; nothing auto-writes to your named engagements.
4. **New/Clear** empties the workspace, deleting the open engagement clears it, and
   a browser crash offers your unsaved work back once.

---

## 14. Implementation order (one coherent pass; each step gated + tested)

1. **State engine** — collapse the two baselines into one; compute the four states;
   the badge reads from it. *(Foundational.)*
2. **Landing** — wizard → NEW-UNSAVED; upload/open/example → CLEAN; uniformly.
3. **Leave-unsaved bar** — the one inline bar + "See changes" expansion; **retire**
   the old light-up badge + auto-dialog.
4. **Save** — single explicit chevron save re-baselines to CLEAN. *(Mostly done —
   `ccbf708`.)*
5. **Revert + Reset-to-uploaded-file** — one-step vs. all-the-way-back; upload-only
   for the latter.
6. **Delete** — open → EMPTY; other → list-only. *(Mostly done — `dea26f1`.)*
7. **New / Clear (Reset)** button.
8. **Landing nudge** banner.
9. **Draft net** — make it invisible (never in list) + boot recovery prompt.
10. **Engagement identity editor** in Configuration (name/location/charter/capital/
    pre-opening; charter re-derives regulator).

Steps 1–3 are the real cleanup — they replace the tangle rather than patch it.
Everything after builds on the state engine.

---

## 15. Test matrix

**A — each entry → correct landing state, no bar**
- A1 Create, touch nothing → NEW-UNSAVED; badge "Unsaved"; **no count**; nudge shows once.
- A2 Upload file → CLEAN; nudge once. A3 Upload workbook → CLEAN. A4 Open saved → CLEAN.
- A5 Load example → CLEAN. A6 New/Clear → EMPTY.

**B — edit detection**
- B1 Create + fill products → still NEW-UNSAVED, **no count**.
- B2 Upload + change 1 field → "1 change since upload".
- B3 Edit then change back → CLEAN (net zero). B4 Click tabs only → CLEAN.

**C — orderings (the whack-a-mole cases)**
- C1 Upload → Create → new is NEW-UNSAVED, 0 changes.
- C2 Create A → Create B → B clean of A (bar first if A unsaved).
- C3 Upload → Example → Example CLEAN, no stale badge (bar first).
- C4 Edit → Open other → bar fires. C5 Edit → New/Clear → bar fires.

**D — save / revert / delete**
- D1 Create → fill → Save → CLEAN, in list immediately, nudge gone.
- D2 Save → edit → "changes since save".
- D3 Revert from step-7 → back to last save (one shot).
- D4 Reset to uploaded file → back to the uploaded original (edits + saves gone); routes through bar.
- D5 Delete open engagement → EMPTY (name + products gone).
- D6 Delete other engagement → gone from list immediately, workspace untouched.

**E — reset & crash net**
- E1 New/Clear from any state → EMPTY (bar first if unsaved).
- E2 Crash with unsaved work → boot offers Recover once.
- E3 Crash with a saved, clean engagement open → **no** recovery prompt.
- E4 Recovery draft never appears in the engagement list.

**F — engagement identity editing**
- F1 Change charter type in Configuration → regulator re-derives (OCC/Fed/FDIC).
- F2 Change bank name in Configuration → propagates to chrome + outputs.
- F3 Change location → persists; state-supervisor framing follows where applicable.
- F4 Identity edits count as changes (MODIFIED) like any other field.

---

## 16. What gets deleted (be explicit)

- The `changedSinceUpload` light-up badge + its click-through itemized dialog.
- The multiple/inconsistent baseline updates — collapsed to one.
- Any tests pinning the old badge strings — updated to the new behavior (never
  resurrect a removed feature to satisfy a stale test).

The autosave machinery is **not** deleted — it is repurposed as the invisible draft
net (§11). Crash recovery stays; it just stops being a visible fake engagement.
