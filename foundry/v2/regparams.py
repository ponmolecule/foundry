"""Versioned regulatory parameters — resolved from this set, never from memory.

Doctrine adopted 2026-07-11 after a stale-memory incident: Foundry carried the
pre-2026 CBLR calibration (9%) after the interagency final rule lowered it.
Every regulatory threshold used by the engine or surface resolves from this
module; each version block carries its citations and a verified date. Updating
a parameter means adding a new version block with new citations, never editing
history.
"""

REG_PARAMS = {
    "version": "2026.07.a",
    "effective": "2026-07-01",
    "verified": "2026-07-11",
    "citations": [
        "Regulatory Capital Rule: Community Bank Leverage Ratio Framework, "
        "91 FR 22973 (Apr. 29, 2026), FR Doc. 2026-08298",
        "OCC Bulletin 2026-15 (rescinds OCC Bulletin 2021-66)",
        "GAO major-rule report B-338364",
    ],
    "cblr": {
        "requirement": 0.08,            # lowered from 0.09, eff. 2026-07-01
        "grace_floor": 0.07,            # must stay above this during grace
        "grace_max_consecutive_q": 4,   # extended from 2 quarters
        "grace_limit_q": 8,             # max grace quarters...
        "grace_window_q": 20,           # ...within the prior 20 quarters
        "assets_ceiling_usd": 10_000_000_000,
        "obs_share_max": 0.25,
        "trading_share_max": 0.05,
    },
}
