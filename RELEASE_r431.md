# r431 — Label participation removal beside its heading

Built on r430 (8894384). Replaces the detached × below the explicit participation schedule with “Remove participation share” in the shared Series heading row. The action stays distinct from Close and Clear. Its tooltip explains that removal deletes the multiplier/schedule and uses the full source count. Compact alignment wraps naturally on narrow screens.

No financial, save or removal-semantics changes. Existing ramp schedules remain unchanged. Explicit monthly participation is the correct location for a schedule representing final participation percentages applied to the source count.

Validation: inline/generated JavaScript syntax checks and r430 precision/Clear regression pass. No real-browser visual check was available. ZIP contains delivery/foundry-full.bundle.
