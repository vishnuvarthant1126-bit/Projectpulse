# Meeting Notes: Beacon Architecture Review

Meeting date: 11 February 2026
Attendees: Maya Chen, Priya Raman, Dana Okafor, Tomas Reyes, Grace Lindqvist
Notes taken by: Maya Chen

## Discussion: Data Sync Approach

Grace explained that shift supervisors need pallet counts that are current during the shift. The nightly batch sync in plan decision D1 would only show the previous night's data, which is too stale for shift planning.

Priya proposed replacing the nightly batch with near-real-time streaming. ScanPoint webhook events would be sent to a RabbitMQ message queue and written to PostgreSQL, with a target latency of under 60 seconds from scan to dashboard.

## Decisions

- **Decision D1 revised:** Beacon will use near-real-time streaming (ScanPoint webhooks to RabbitMQ to PostgreSQL) instead of the nightly batch sync. Decided by Grace Lindqvist as sponsor, on Priya Raman's recommendation. Reason: operations needs live counts during shifts.
- The dashboard beta stays limited to the Reno site.

## Schedule Impact

- Priya estimates the streaming redesign adds one week to the pipeline. M2 moves from 27 February 2026 to 6 March 2026.
- Dana said the dashboard now needs live-update components and depends on M2, so the M3 dashboard beta moves from 13 March 2026 to 27 March 2026.
- These date changes will go to the steering committee for approval.

## Action Items

- A1: Priya Raman to publish the revised pipeline design by 16 February 2026.
- A2: Tomas Reyes to provision RabbitMQ in staging by 18 February 2026. This depends on freeing staging capacity (B-2).
- A3: Maya Chen to update the plan dates and brief the steering committee.
- A4: Maya Chen to ask Sam Whitfield (IT Security) when the SSO review can start. Sam did not attend.
