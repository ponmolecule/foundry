# r311 — Guide Me linked migration and missing cadence

Built directly on r310, commit 514758d9696228e8b2e9615157ae9b6a04dd2465. r310 Review & apply, its link review, and its zero-valued stream creation remain in place.

Guide Me distinguishes an existing raw percentage source from an existing migrated monetary-throughput quantity. For descriptions saying both TPV and migration are linked, it asks which shape the migration source contains. A migrated TPV source can directly drive one bank-revenue stream and its throughput-based operating cost. A raw percentage multiplied by a separate linked TPV is not currently representable as two independent links in one fee stream; Guide Me must state that limitation, not invent linked-coefficient support or silently replace the link with an entered schedule.

A translator response with a missing coefficient period now produces a targeted clarification instead of exhausting the automatic correction and returning a parser error. No cadence is guessed; the incomplete streams are not exposed for Apply. Explicitly invalid periods still fail closed. Supplied Month/Quarter/Year values are preserved.

No engine arithmetic or saved configuration changed. The actual rejected upstream response was not available; tests reproduce the reported missing/not_applicable coefficient-period class and the full prompt facts using mocked upstream responses. No live model call was tested.

For the supported migrated-TPV path: select the already migrated monetary flow quantity, enter revenue 0.0004% of throughput ($0.000004/$ TPV), and direct operating cost 0.0003% of throughput ($0.000003/$ TPV). Rates are not dollars per transaction. At $250,000 migrated TPV this is $1 revenue and $0.75 cost. Guide Me Apply still creates financial assumptions at zero until you enter them.
