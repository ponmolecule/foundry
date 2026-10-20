# Foundry r363

Direct parent: r362 / 363eb3a.

Customer Acquisition now puts Create feed above the feeds, visible even when the section is collapsed. Each feed is an independent native disclosure with its name, channel count and Expand/Collapse indication. Initially the first existing feed opens; others close. Creating a feed expands the section, opens the new feed, closes other feeds and focuses the new name field. Feed expansion state survives rerenders and renaming through object-keyed view state, without changing assumptions. Existing nested channels, controls and calculated summary remain inside their feed.

Verification: actual-handler smoke covers independent expansion, new-feed creation, other-feed closure, rename stability and unchanged existing assumptions. Complete inline JavaScript syntax, CAC UI suite (37 checks), and attrition precision/customer capacity checks pass. Existing hierarchy assertion updated for semantic details container. Browser visual verification unavailable. No engine change. Packaged; not deployed.
