# Funded-flow timing checks for the Foundry UI

Create **Lending → Flow-based lending + fees** in a monthly 36-period model.
Use a test product with **Exposure term = 7 days**, **Day count = 365**,
**Reserve share = 0%**, and **Target retained share = 100%**. Inspect funded
volume in Product Detail or the Calculation Audit. The figures below are
`$000s` in the UI; audit and Product Detail display `$000s` as well.

1. **Source activity, launch and ramp.** Choose **Input represents → Source
   activity**, **Enter flow**, **Flat**, **month**, and enter `1,000` as source
   activity. Set **Starts in model month = 13**, **Take-up share = 20%**, and
   **Months to full size = 6**. Funded volume is `0` for M1–M12; M13–M18
   should be `33.333333, 66.666667, 100, 133.333333, 166.666667, 200`.
   Source activity remains `1,000` throughout. The M13 retained balance is
   `33.333333 × 12 × 7 / 365 = 7.671233` in `$000s` before any shared cap.

2. **Move the launch dial.** Change only **Starts in model month** to `14`.
   Source activity stays `1,000` in every month. Funded volume is now zero
   through M13 and ramps `33.333333` at M14. Return start to `13` afterward.

3. **Final data that agrees.** Switch to **Final funded volume** (confirm the
   reset of take-up/ramp). Choose **Explicit** and paste 36 monthly values:
   twelve zeroes, then the M13–M18 amounts from case 1, then `200` for each
   remaining month. Keep start at `13`. The calculated funded volumes match
   the paste exactly; there is no second application of 20% or the ramp.

4. **Final data that contradicts timing.** Change only the pasted M12 value
   to `1`. Running the model must report a nonzero final funded volume in
   model period 12 before start period 13. The saved input is not overwritten.
   Restore M12 to `0`, then run again. A Flat final funded volume of `1,000`
   with start 13 must likewise fail at period 1.

5. **Linked source activity.** If an upstream Deposit or Fee Product has a
   monetary Transaction quantity Series, select **Link upstream flow** and
   choose it. With the same start, take-up and ramp, the linked Series can be
   nonzero in M1–M12; this lending product's funded volume must still be zero
   there. Switching back to **Enter flow** retains the entered flow schedule.
   A linked **Final funded volume** Series that is nonzero before start must
   fail instead.

6. **Invalid controls.** Start `0` or `2.5`, ramp `0`, and take-up `110%`
   must each be rejected. A final-volume input cannot also retain a ramp
   longer than one period or a take-up below 100%; changing the UI selector
   prompts before resetting those source-activity controls.

7. **Legacy behavior.** An r181 saved funded-flow product without the new
   fields still treats its source as final funded volume starting in period 1,
   with no additional take-up or ramp. Existing loan roll-forward and
   customer-linked products are unchanged.

The engine tests in `foundry/v2/tests_funded_flow_timing.py` cover these
contracts, including native-quarter timing and fee pricing on calculated
funded volume. Run `python -m foundry.v2.tests_funded_flow_timing`.
