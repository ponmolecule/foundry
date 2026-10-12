# r319 validation

Baseline: r318 (38af1ea). Full suite: 107 modules, 91 pass, the same 16 baseline modules fail; every module exit status matches r318. No new failures. Full suite is not entirely green.

26 engagement-setup tests pass, including the rendering-created shell, old r318 baseline digest, legacy empty shell, and rejection of substantive asset models. Node executes the actual read-only fixed-assets rendering expression and the setup draft/apply/lock helpers. Pinned result identities pass (3/3). Complete output comparisons pass without field removal (5/5). Inline JavaScript syntax and git whitespace checks pass.

The exact API function test uses an AST-extracted body and response stand-in, because FastAPI is absent locally. No live HTTP or visual browser test is claimed; no browser executable is available. Engine code and economics are unchanged.
