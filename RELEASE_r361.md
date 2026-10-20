# Foundry r361

Direct parent: r360 / 57e24018d1141115126480101a0292bd65591504.

Adds Expand all and Collapse all controls near the top of each lending Setup page. Funded-flow lending controls all seven sections: Funded volume, Exposure & retention, Credit & allowance, Pricing, Fee streams, Costs & accounting, and Reporting. Standard lending layouts receive the same controls for their available Setup sections.

The actions apply only to the selected loan. Funded-flow layouts reuse the existing per-product section state; standard loan layouts reuse existing section-toggle handlers and update mounted controls in place. Individual section toggles still work. The buttons remain available when all sections are collapsed. This is UI state only, with no assumption or engine changes.

Verification: actual-handler smoke checks cover all seven sections, isolation from another loan, standard lending sections, repeated actions, aria-expanded and hidden state, and unchanged model inputs. Existing industrial flow-lending renderer (18 checks), full inline-script syntax and precision/capacity renderer checks pass. Whitespace checks pass. Browser pixel/layout verification remains unavailable.

Packaged for user deployment; not deployed.
