# r337 — Active source control width

Direct continuation of r336 a15518e7efa5576854fa669ad4c950c97402a68e.

Widens only Rates & Curves → Active source to 330px (previously 200px), capped to available width. Its select fills that width. Other entry boxes retain their compact sizing. No configuration or engine change.

Validation: existing Rates & Curves UI handler test and full inline-script compilation pass; git diff --check passes. This bounded CSS adjustment does not warrant repeating the full engine suite. Browser rendering remains unavailable as documented for r336; no visual verification claim.
