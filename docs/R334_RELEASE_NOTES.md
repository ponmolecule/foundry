# r334 — tax rule selectors and shared assumptions

Built directly on r333 13dca3070fcd15f8247acda1fd91aa5403bb5fa3.

Derived tax rules now offer selectable Sum, Difference, Multiply, Ratio, Minimum, Maximum, Positive amount, and Prior-period balance operations. Operands are selected by readable source name. The resulting expression is previewed, generated on Apply, and processed by the existing engine expression validator. Units are inferred. Incomplete selections, incompatible units and current dependency cycles do not replace the saved rule. Cancel discards the draft. Ratio explicitly returns zero on a zero denominator. Prior-period balance requires a named input/rule plus a compatible opening input or configured assumption. Forward references require first creating the named rule.

Existing expressions are preserved exactly. They can be rebuilt with selectors, or edited under Advanced expression. Builder drafts are transient and do not change saved configuration or preview results until Apply. New rules begin at zero, as before; they do not post unless selected by the output graph.

Configured NOL utilization limit is reusable as configured_nol_limit: tax_policy overrides tax_detail, otherwise the existing regulatory default applies. The compact control edits tax_policy, the same setting used by calculated tax. Configured opening NOL is optionally available as configured_opening_nol (money, native dollars). The existing configured_tax_rate remains available. These are references, not automatic extra tax calculations.

Entity scope matters: the existing opening NOL is not silently substituted for an analyst-entered group carryforward. No valuation allowance, deferred recognition, loss usage or allocation policy is inferred from these references. Automatic calculated-tax logic remains inactive in external mode. No new recurring expense or double tax provision is introduced.

Source Name, Identifier, Units, Source and Measure now have visible labels. Compact bounded controls wrap in rows, rather than expanding across the panel.

Your entered external tax inputs remain untouched. Deploy with the usual script and return to the intended monthly engagement. Do not duplicate the configured rate or NOL limit. A separate pre-forecast group NOL source remains appropriate when it differs from the bank's existing opening tax policy.
