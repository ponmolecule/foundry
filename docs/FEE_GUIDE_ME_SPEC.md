# Fee Product Guide Me — grounded translator contract

## Purpose
Guide Me translates a user's plain-language description of fee mechanics into the existing Foundry Fee Product dials. It is advisory only: it never edits the model and never chooses assumptions.

## Grounding boundary
The backend sends Claude only:
1. the user's text entered in the Guide Me window; and
2. a machine-readable manifest generated from Foundry's current fee-engine vocabulary.

The request supplies no engagement configuration, files, URLs, retrieval, web-search tools, or other external tools. The returned plan is validated against the same fee-stream evaluator used by Foundry. Unsupported basis/source/trajectory/rate/cost combinations fail closed.

An LLM necessarily retains pretrained knowledge in its model weights; Foundry therefore does not claim that knowledge is erased. Instead, it enforces that every *actionable recommendation* is expressible in, and validated against, the current Foundry fee schema.

## Runtime
- API: Anthropic Messages API, server-side only.
- Secret resolution (server-side only): `ANTHROPIC_API_KEY`, then `FOUNDRY_ANTHROPIC_API_KEY`, then the Foundry persistent secret file under `FOUNDRY_DATA_DIR/secrets/anthropic_api_key`, with `config.settings.ANTHROPIC_API_KEY` retained only as a co-located/legacy compatibility fallback.
- If no deployment secret is present, a Foundry server operator, admin, or deputy may configure the persistent secret once from the Guide Me window. The credential is submitted only to the authenticated configuration endpoint, stored with owner-only file permissions, never returned by status/configuration APIs, never written to an engagement, and never packaged in a release bundle.
- Model: `FOUNDRY_GUIDE_MODEL`, default `claude-sonnet-5`.
- Without an API key, Guide Me fails closed; privileged users are offered the one-time server setup control while ordinary users are told to contact a server operator. The rest of Foundry is unaffected.

## Output contract
Claude returns a constrained plan containing only current Foundry IDs (basis, source, trajectory, coefficient semantics, rate behavior, cost kind). Foundry validates that plan, then *locally* renders the exact click-by-click field instructions. Claude's prose is not used to mutate configuration.
## Flat recurring-amount trajectories

The Flat fee basis represents a recurring fixed-dollar fee. Its recurring **Amount** is trajectory-capable without changing the economic basis:

- `Flat` — one recurring amount held constant;
- `Growth` — a starting recurring amount grown by a standard Foundry growth specification;
- `Explicit schedule` — a pasted Month / Quarter / Year amount path, with each entry stated in `$000s` and the last loaded amount carried forward.

The amount path is distinct from **Rate behavior**. Flat-basis Rate behavior remains `flat`; changing the recurring dollar amount is authored through **Amount path**, not by inventing a rate schedule. Guide Me exposes this mechanic through `flat_amount_trajectory` and may map an escalating escrow/retainer schedule to one Flat stream.

Example: an annual escrow schedule of `150, 200, 250, 300, 350, 400, 450` means `$150,000` through `$450,000` per year. The same natural-year economics must reconcile in quarterly and monthly engine cadence.
## Proxy-safe execution

Guide Me must never hold a browser-to-Foundry request open while Anthropic generates a plan.
The UI submits a short authenticated job request, receives a job ID immediately, and polls a
short status endpoint. The Anthropic call runs server-side outside the browser request window.
Job status is persisted under `FOUNDRY_DATA_DIR`, bound to the authenticated user, and expires
after a short retention window. The submitted description is not persisted in the job file.

This separation is required because reverse proxies may terminate long synchronous requests even
when Anthropic is healthy. Proxy timeouts therefore cannot be treated as model failures.

## Transaction-stream causal contract

A transaction / throughput stream represents one revenue equation, not one stream per assumption.
For coefficient-driven transaction economics, Foundry's native equation is:

`source quantity × flow coefficient = throughput`

`throughput × fee/spread = revenue`

Accordingly, a source-model volume/AUC percentage (or turns/multiple) and the fee/spread earned on
that throughput belong in the **same transaction stream** when they are factors in the same revenue
equation. Guide Me must not split those factors into separate revenue streams. If a required
fee/spread or revenue-start assumption is missing, Guide Me asks a clarification question rather
than inventing a value or creating a second stream.

Guide Me instructions must also mirror the active authoring control:
- `Flat` coefficient trajectory — use the single Flow % / Turns field;
- `Growth` — use the starting Flow % / Turns field plus growth controls;
- `Explicit schedule` — use the schedule pastebox and do not instruct the user to populate the
  inactive single-value field.

The displayed trajectory noun should follow the economics: `Volume % trajectory` for `% of source`
and `Turns trajectory` for a multiple/turns coefficient.

For a `Flat — periodic amount` basis, the amount path is the economic input. Guide Me therefore
omits schema-placeholder instructions for driver source, driver trajectory, and rate behavior and
focuses on Amount path, natural period, amount/schedule, cost side, and timing.
