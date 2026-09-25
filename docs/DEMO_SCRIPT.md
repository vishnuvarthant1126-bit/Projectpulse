# ProjectPulse: 3-minute demo script

A walkthrough for a portfolio video or a live interview demo. It works in demo mode (no API key).
If you have a key configured, say so at step 4 and show a live answer instead.

## 0. Setup (before recording)

```bash
docker compose up --build        # or run backend + frontend locally
```

Open http://localhost:3000 in a fresh browser window, at about 1400 px wide.

## 1. The problem (15 s)

> "Project status is spread across the original plan, weekly reports and meeting notes. When
> someone asks *what changed?*, the answer usually means re-reading all of them. ProjectPulse
> answers from those documents only, with citations you can check."

Point at the headline: *Understand what changed. See what needs attention.*

## 2. Load the sample project (15 s)

Click **Try sample project**.

> "This is a fictional project: a 3-page PDF plan, three weekly reports and two sets of
> meeting notes. Each document has a type and a confirmed reporting date. That date is what
> the app uses to decide what's latest; upload time is never used."

Point at the **Demo mode** badge in the header.

## 3. Plan versus progress (45 s)

Click **What changed between the original plan and the latest update?**

- Point at the yellow label: *Precomputed demo answer (not live AI)*. "Without an API key the
  suggested questions use answers written in advance, and they're labelled as such."
- Walk through the **comparison table**: M2 slipped from 27 Feb to 5 Mar, M3 moved two weeks,
  M4 moved a week. Then point at M5: "No update mentions staff training, so it says *No update
  found*. It doesn't assume the milestone is late."
- Click a citation chip in the table. The **source viewer** opens on page 2 of the PDF with the
  passage highlighted. Close it with Esc.

## 4. Conflicting sources (30 s)

Scroll to **Sources disagree**.

> "The 4 March steering committee notes say the pipeline was finished 'last week'. The
> 6 March report says it was completed on 5 March. ProjectPulse shows both claims with their
> dates instead of picking one, and the suggested action is to reconcile the record."

Point out that **Suggested actions** are labelled as recommendations, separate from the facts.

## 5. Blockers: historical vs unresolved (20 s)

Click **What blockers remain unresolved?**

> "B-3 is flagged as unresolved *in the latest update*, and B-1 and B-2 show as resolved,
> each with its resolution date and a citation."

## 6. Hybrid retrieval and evidence (30 s)

Open the **Evidence** panel.

> "Each passage shows its fused rank, BM25 rank and semantic rank. Hybrid merges them with
> reciprocal rank fusion."

Switch the mode to **Keyword**, type `What is ticket BCN-201?`, and press Enter.

> "Outside the precomputed set, demo mode returns only the retrieved evidence. It doesn't make
> up an answer. With an API key this becomes a live, validated answer."

## 7. Honest evaluation (20 s)

Show `eval/results/retrieval_results.md`.

> "I built 30 evaluation questions with supporting passages. Hybrid had the best MRR and
> Recall@5, but the bootstrap confidence intervals include zero, so I don't claim it's
> significantly better on this small set. Answer quality has a separate harness (citation
> validity, abstention, and an LLM judge that's labelled as automated), which runs once a key is
> configured."

## 8. Close (10 s)

> "Everything runs locally with Docker Compose. Retrieval is isolated per project, citations
> are validated on the server, and keys never reach the browser."

### Backup talking points

- *Why RRF?* It needs no score calibration between BM25 and cosine similarity; it only uses
  ranks.
- *Why per-project Chroma collections?* Isolation doesn't depend on remembering a filter, and
  every hit is re-checked against SQLite too.
- *What stops invented citations?* The model only sees S1..Sn. The server drops any other ID,
  removes uncited facts, and flags dates that aren't in the cited passages.
