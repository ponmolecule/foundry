# Lending levels, flows, and shared capacity

Existing lending products retain their roll-forward behavior unless `balance_mode`
is explicitly changed. `linked_customer_level` retains its existing contract.
The optional `explicit_level` mode accepts an entered ending-balance Series. The
optional `funded_flow_level` mode derives a target level from monetary funded
volume. Both use the ordinary lending accounting and regulatory pathways.

## Funded-flow level

`funded_flow_driver` is either an entered monetary `flow_path` (Flat, Growth,
or Explicit; each has a stated month/quarter/year period) or a link to a stable
`quantity_series_id` of an upstream monetary Transaction fee stream on a
Deposit or Fee Product. A linked source must already exist and resolve to the
complete model horizon. Entered Explicit schedules must cover every source
period in the horizon. A loan's own fee streams cannot be its upstream driver.

The optional driver fields `input_stage`, `start_period`, `ramp_periods`, and
`take_up_share` distinguish upstream activity from final funded volume.
Start and ramp are positive whole numbers in the model's native cadence; take-up
is a share in `[0, 1]`. The new UI template starts with `source_activity`.
Absent fields on saved older models mean `funded_volume`, start 1, ramp 1,
and take-up 100%, preserving r178/r181 behavior.

For `source_activity`, an entered or linked monetary flow remains intact as
input. Its downstream funded amount in native model period `t` is:

```
factor[t] = 0                                    if t < start_period
          = min(1, (t-start_period+1)/ramp_periods) otherwise
funded_volume[t] = source_activity[t] * take_up_share * factor[t]
```

Thus a six-period ramp has factors 1/6 through 6/6. For `funded_volume`, the
values are already post take-up/ramp; neither is applied twice. Nonzero final
funded volume before `start_period` fails with the conflicting model period.
Invalid timing or shares also fail. A linked flow stays available to other
products regardless of this product's launch. Switching stages does not
silently erase a saved explicit schedule.

Timing operates at the model cadence. An entered monthly source in a quarterly
model first aggregates to quarterly volume, then takes the quarter's ramp
factor; monthly intra-quarter activation requires a monthly model.

For engine period `t`, the closed equation is:

```
outstanding[t] = funded_volume[t] * periods_per_year * term_days / day_count
                 * (1 - reserve_share)
target_retained[t] = outstanding[t] * target_retention_share
```

These are monetary levels. `reserve_share` reduces the modeled outstanding
exposure; it is distinct from the allowance. The period-end retained target
becomes the on-book loan balance. Signed balancing production/(paydown) makes
the level reconcile with the existing roll-forward, including runoff and
charge-offs. `interest_balance_measure` explicitly selects period beginning,
period average, or period end. The annual loan yield is divided by the engine's
periods per year; a fee percentage on funded volume is applied to the native
period flow without annual periodization.

`charge_off_balance_measure=period_end` supports losses on current retained
exposure. `allowance_mode=loss_rate_term` computes retained balance × annual
charge-off rate × credit loss factor × term days / day count. The optional
entered `credit_loss_factor_spec` defaults to one and supports Flat, Growth,
or Explicit values. Legacy charge-off and reserve-rate rules remain defaults.

## Shared allocation

An optional `loan_allocation_groups` assumption names a group and its cap.
Each member loan carries `allocation_group_id` and a stable
`allocation_target_id`. The group supports an entered capacity Series or the
pre-credit ending deposit book multiplied by a cap ratio. For every period:

```
factor = 1 if total_target == 0 else min(1, cap / total_target)
retained[member] = target[member] * factor
distributed[member] = target[member] - retained[member]
```

The pre-credit deposit source is resolved before loan balances and avoids a
funding feedback cycle. If a separate post-sweep deposit Series is required,
enter an explicit cap path until a typed upstream source exists;
Foundry will not silently substitute total deposits for post-sweep deposits.

Existing fee streams on the same lending object can price `product_funded_flow`
as a monetary Transaction source or `distributed_balance` as an annual Balance
source. They post to fee income and retain the lending product's identity.
Product Detail and Calculation Audit expose funded volume, pre-retention
outstanding, target and final retained balance, distributed amount, allocation
factor, interest basis, charges, allowance, and fee-stream pricing lineage.

## Example

```json
{
  "loan_allocation_groups": [{"id": "shared-cap", "cap_source": "deposit_book_end", "cap_ratio": 0.4}],
  "lending_products": [{
    "name": "Facility A", "allocation_group_id": "shared-cap",
    "allocation_target_id": "facility-a-retained-target",
    "balance_mode": "funded_flow_level", "structure": "revolving",
    "funded_flow_driver": {"source": "entered", "input_stage": "source_activity",
      "start_period": 1, "ramp_periods": 6, "take_up_share": 0.2,
      "flow_path": {
      "unit_kind": "money_flow", "trajectory": "flat", "period": "month", "value": 1000000}},
    "term_days": 30, "day_count": 365, "reserve_share": 0.01,
    "target_retention_share": 1, "interest_balance_measure": "period_end",
    "charge_off_balance_measure": "period_end", "allowance_mode": "loss_rate_term"
  }]
}
```

The lending product also needs its ordinary required fields, such as opening
balance, rate type and yield, charge-off rate, runoff, and measurement.
