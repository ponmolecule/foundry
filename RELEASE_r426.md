# r426 — Customer Acquisition chart Numbers link

Built on r425 (a814e6d). Adds a discreet Numbers link immediately below the selected feed or channel chart. Reuses the existing closable period-values dialog, with per-row Copy values and Copy table for Excel, full stored precision, unit labels, clipboard fallback, Escape/close cleanup and last-complete-run warnings. No table occupies the page while closed.

Feed view includes monthly beginning customers, additions, attrition, ending customers, each channel’s additions, AUC movements and acquisition spend. Channel edit view includes that channel’s new customers, acquisition spend and new AUC. Numbers match the chart’s canonical monthly observations at all engagement cadences, explicitly labeled M1…Mn. Stock snapshots are not summed. Money is already in public $000s and is not rescaled. Interpolated feeds label modeled movements rather than claiming publishable gross flows.

Reads existing customer_acquisition results only. No calculation, configuration, save, acquisition publication or source-link changes. Opening the view does not create an engagement change.

Validation: new acquisition harness passes feed/channel scoping, exact M1 .28/M2 .56/M3 .56 additions, quarterly-engagement monthly labels, money units, copy export, missing/stale/interpolated states, read-only snapshots and placement. Existing result-number and workforce/expense-number dialog harnesses and all inline/generated JavaScript syntax checks pass. No real browser visual check was available.

Delivery ZIP uses delivery/foundry-full.bundle, matching the deployment-script path shown in this conversation. Verify BUILD_STAMP = foundry-r426-acquisition-numbers after import.
