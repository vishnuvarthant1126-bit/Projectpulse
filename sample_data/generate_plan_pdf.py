"""Generate the fictional Project Beacon original plan as a 3-page PDF.

Run from the repo root:  python sample_data/generate_plan_pdf.py
The output (sample_data/beacon/01_beacon_project_plan_v1.pdf) is committed so the
demo works without running this script. Everything in it is fictional.
"""

from pathlib import Path

import pymupdf

OUT = Path(__file__).parent / "beacon" / "01_beacon_project_plan_v1.pdf"

CSS = """
* { font-family: sans-serif; }
h1 { font-size: 18px; margin-bottom: 4px; }
h2 { font-size: 14px; margin-top: 12px; margin-bottom: 4px; }
p, li, td, th { font-size: 10px; line-height: 1.35; }
table { border-collapse: collapse; }
td, th { border: 1px solid #999; padding: 3px; text-align: left; }
"""

PAGES = [
    """
<h1>Project Beacon: Project Plan v1.0</h1>
<p>Kestrel Freight (fictional company). Document owner: Maya Chen, Project Manager.<br/>
Plan date: 12 January 2026. Status: Approved baseline.</p>

<h2>1. Purpose and Scope</h2>
<p>Project Beacon will give warehouse supervisors a web dashboard that shows where every
pallet is located across the Reno, Tacoma and Boise warehouses. Pallet locations come from
ScanPoint handheld scanners through the ScanPoint Events API v3. The dashboard beta will be
limited to the Reno site; Tacoma and Boise join at go-live.</p>
<p>Out of scope for this phase: forklift telemetry, customer-facing tracking, and billing
integration.</p>

<h2>2. Team and Roles</h2>
<ul>
<li>Grace Lindqvist, Operations Director: project sponsor, accountable for go-live.</li>
<li>Maya Chen: project manager.</li>
<li>Priya Raman: integration lead, owns the scanner data pipeline.</li>
<li>Dana Okafor: frontend lead, owns the dashboard.</li>
<li>Luis Ortega: QA lead, owns user acceptance testing.</li>
<li>Tomas Reyes: infrastructure lead, owns the staging and production clusters.</li>
<li>Sam Whitfield: IT Security reviewer.</li>
</ul>

<h2>3. Budget</h2>
<p>The project budget is tracked separately by Finance and is not included in this plan.</p>
""",
    """
<h2>4. Milestones</h2>
<table>
<tr><th>ID</th><th>Milestone</th><th>Target date</th><th>Owner</th></tr>
<tr><td>M1</td><td>Requirements sign-off</td><td>30 January 2026</td><td>Maya Chen</td></tr>
<tr><td>M2</td><td>Scanner data pipeline: ScanPoint events loaded into PostgreSQL</td><td>27 February 2026</td><td>Priya Raman</td></tr>
<tr><td>M3</td><td>Dashboard beta at the Reno site</td><td>13 March 2026</td><td>Dana Okafor</td></tr>
<tr><td>M4</td><td>User acceptance testing (UAT) complete</td><td>3 April 2026</td><td>Luis Ortega</td></tr>
<tr><td>M5</td><td>Staff training at all three sites</td><td>17 April 2026</td><td>Maya Chen</td></tr>
<tr><td>M6</td><td>Go-live at all sites</td><td>24 April 2026</td><td>Grace Lindqvist</td></tr>
</table>

<h2>5. Architecture Decisions</h2>
<p><b>D1 Data sync:</b> Scanner events will be copied into PostgreSQL by a nightly batch
sync that runs at 02:00 local time. Real-time streaming was considered and deferred to
phase 2 to limit scope.</p>
<p><b>D2 Authentication:</b> Users sign in through the corporate single sign-on (SSO)
provider. The SSO integration must pass an IT Security review before UAT begins.</p>
<p><b>D3 Hosting:</b> Beacon runs on the existing on-premises Kubernetes cluster, with
separate staging and production namespaces.</p>

<h2>6. Dependencies</h2>
<ul>
<li>ScanPoint must provision API credentials for the Events API v3 by 23 January 2026.</li>
<li>A staging environment with capacity for the pipeline test deployment.</li>
<li>IT Security review slot for the SSO integration.</li>
</ul>
""",
    """
<h2>7. Risks</h2>
<table>
<tr><th>ID</th><th>Risk</th><th>Mitigation</th></tr>
<tr><td>R1</td><td>Vendor delay in provisioning ScanPoint API credentials.</td><td>Build against recorded sample event files until credentials arrive.</td></tr>
<tr><td>R2</td><td>Staging cluster capacity is limited.</td><td>Tomas Reyes to review cluster usage in February.</td></tr>
<tr><td>R3</td><td>IT Security review queue for SSO typically takes about three weeks.</td><td>Submit the review request early.</td></tr>
<tr><td>R4</td><td>Label printer firmware at the Boise site may be incompatible with new pallet labels.</td><td>Test labels at Boise before training.</td></tr>
</table>

<h2>8. Communication</h2>
<p>Weekly status reports are published every Friday by the project manager. The steering
committee, chaired by Grace Lindqvist, meets monthly to approve changes to milestone
dates.</p>

<h2>9. Change Control</h2>
<p>Any change to a milestone target date must be recorded in the weekly status report
and approved by the steering committee.</p>
""",
]


def main() -> None:
    doc = pymupdf.open()
    rect = pymupdf.paper_rect("letter")
    where = rect + (54, 54, -54, -54)
    for html in PAGES:
        page = doc.new_page(width=rect.width, height=rect.height)
        page.insert_htmlbox(where, html, css=CSS)
    doc.set_metadata({"title": "Project Beacon: Project Plan v1.0", "author": "Maya Chen (fictional)"})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(OUT), deflate=True)
    print(f"wrote {OUT} ({doc.page_count} pages)")


if __name__ == "__main__":
    main()
