# r458 — Stream charts follow the selected tab

Activity shows the engine-resolved stream quantity with its native count or monetary units, even when the stream also posts revenue or costs. Costs shows the stream expense in $000s. Switching tabs refreshes the chart, summary and Numbers payload immediately. Account count snapshots are not summed. Pricing and Timing retain the existing financial result view; stream grid and linked result previews retain their existing posting semantics.

Presentation only: no engine, input defaults, saved-data schema or migration changes. Confidential engagement inputs were not available for deployment persistence validation.

Validation: Chromium regression checks a cost-bearing account stream with a 60-month count series, switching Activity → Costs → Activity, count versus $000s labels, last-period values, suppression of summed account snapshots, unchanged inputs and unchanged posting view. Existing r457 acquisition-source browser regression also passes.
