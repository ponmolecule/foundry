# Reusable weighted assumptions for customer-linked lending

Customer-linked lending supports an entered amount or a stable reference to a reusable shared amount, followed by any number of independent dimensionless factors. The customer-count source and its attrition remain owned by Customer Acquisition.

The shared registry remains `assumptions.balance_components_model.inputs`. A registry-only model is disabled and has no accounting components. Adding inputs does not enable balance accounting or create another asset. The existing balance-component engine can consume these same shared inputs. Legacy balance adoption preserves registry-only assumptions and their references.

A weighted amount has a user-defined name, stable ID, typed unit, amount time-basis description, and an arbitrary number of named components. Each component has its own stable ID, amount Series and share Series. Each Series uses existing Flat, Growth and Explicit authoring. Amounts in this lending editor are plain dollars per customer. Shares and factors are entered as ordinary percentages in the UI and stored as fractions.

The closed equation is `sum(component amount × component weight)`. Shares must be finite, nonnegative, at most 100%, and total 100% in every canonical month. Amounts must be finite and nonnegative. References resolve by stable ID and reject missing sources, duplicates, incompatible dimensions and cycles. There is no arbitrary formula execution or engagement-specific component count.

Amount time basis describes what the supplied amount represents (for example annual sales per customer). It does not divide that amount into monthly flows. Schedule cadence describes when the assumption changes. Weighted calculations and factors resolve on the monthly grid; quarterly ending targets sample the monthly closing values. This is a per-customer level, not an origination flow.

Lending applies its own independent factors after resolving the shared amount. Product factors never alter the shared object. Editing the shared object affects all its consumers. The UI exposes this explicitly and blocks deleting an input referenced by lending or other shared inputs/components.

Engine product detail publishes component amounts, weights, weighted contributions, shared outputs, factors and the final resolved amount. Public detail retains native dollar/fraction precision. Calculation Audit includes a Lending Assumptions sheet with stable IDs and period observations.

A weighted per-customer amount can preserve a segmented source when active population shares are known and acquisition/attrition assumptions are common across segments. Changing a weighted assumption does not track population cohorts or reclassify existing customers. Distinct segment retention or acquisition requires distinct population paths; do not use a new-customer mix as though it were the surviving-book mix.

Existing entered lending amounts and legacy balance calculations retain their contracts. The entered lending editor now labels plain dollars explicitly; stored values are not rescaled or inferred.
