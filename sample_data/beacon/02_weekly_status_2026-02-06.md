# Project Beacon: Weekly Status Report #1

Week ending: Friday 6 February 2026
Prepared by: Maya Chen, Project Manager
Overall status: Amber

## Milestone Status

- **M1 Requirements sign-off:** Complete. Signed off on 30 January 2026, on time.
- **M2 Scanner data pipeline (target 27 February 2026):** At risk. The team is building against recorded sample event files because live API access is not available yet (see B-1).
- **M3 Dashboard beta (target 13 March 2026):** Not started. Dana Okafor's team is producing design mockups.
- **M4 to M6:** No change this week.

## Blockers

### B-1 ScanPoint API credentials not provisioned
Status: Open. Owner: Priya Raman.
ScanPoint has not provisioned credentials for the Events API v3. They were due on 23 January 2026. Vendor ticket SP-7781 is open with ScanPoint support. Without credentials the pipeline cannot be tested against live scanner events.

### B-2 Staging cluster out of memory headroom
Status: Open. Owner: Tomas Reyes.
The staging Kubernetes cluster is at 92% memory usage, so the pipeline test environment cannot be deployed.

## Other Notes

Grace Lindqvist reported that shift supervisors want live pallet counts during a shift. Next-morning data from the nightly batch sync would not support shift planning. This will be discussed at the architecture review on 11 February 2026.

## Next Week

- Priya to escalate SP-7781 with the ScanPoint account manager.
- Tomas to review which staging workloads can be removed.
