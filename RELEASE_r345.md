# Foundry r345

Parent: r344 customer-source correction / 206f294. This release assigns a distinct release identity to that correction; no further application behavior changes. Supersedes the correction package labeled foundry-r344-customer-source-picker. Original r344 acquisition-channel-links remains distinct.

## Customer-count source picker correction

Account streams now select a specific Customer acquisition › feed › Customers directly in Driver source. Removed the duplicate Ending bank customers source dropdown. A compact Count measure retains all existing choices (month end, beginning/end average, year-end held through year); long ownership and cadence explanations use the existing collapsed About these settings treatment. Stable source IDs, stored measures, engine economics and reserved manual schedules remain unchanged. Missing saved references stay visible; no source is silently substituted by rendering. Selecting a new feed applies its ID before the single refresh.

Validation: focused executable renderer/controller regression passes for multiple feeds, legacy saved links, measure retention, missing references, and entered-schedule restoration. CAC UI 37/0, acquisition channel links and fee quantity links pass. Broad legacy growth UI suite is 63/21 on both original r344 and this correction; existing harness failures include missing renderer globals. No engine changes or deployment.
