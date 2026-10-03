# Instructor guide: Data and Fine-Tuning Models (60 minutes)

**Session goal:** students leave able to explain the three ways to bring company data to a model (prompting, RAG, fine-tuning), when each one fits, and why open-weight models plus expert-labeled data can beat frontier models on narrow tasks. They do this by fine-tuning NVIDIA Nemotron themselves.

**Pre-work for students:** [`PRE-READ.md`](../PRE-READ.md) (~15 min) plus, optionally, the Bridgewater × Thinking Machines post it links to.

---

## Run of show

| Time | Block | What happens |
|---|---|---|
| **0:00–0:05** | Boot up | Students open the notebook, switch the runtime to a **T4 GPU**, and run the two **Step 0** cells. The model loads in the background (~4 min) while you talk. |
| **0:05–0:15** | Framing (instructor) | "How do you bring your data to the model?" Prompt vs RAG vs fine-tune (pre-read §2), open vs closed weights (§4), the Bridgewater × Thinking Machines result (§5). Close with: *"In the next 25 minutes you'll test whether that holds for your business process."* |
| **0:15–0:19** | Case | Teams read their 1-page case (Step 1 prints it) and predict which fields the model will get wrong. |
| **0:19–0:25** | Methods 1 & 2 | Steps 2–3: prompt only, then prompt + policy doc. Ask: what got better, and what did it cost in prompt tokens? |
| **0:25–0:27** | Decisions | Step 4: each student enters the settings on their card (below). |
| **0:27–0:33** | Fine-tune | Step 5 trains (~3–5 min). Meanwhile each team drafts a tricky test case for Step 7 and discusses Q2 and Q4. |
| **0:33–0:40** | Results | Steps 6–8: evaluate, try to break the model, paste the scorecard into the leaderboard. |
| **0:40–0:55** | Debrief | Put the leaderboard on screen. Work through the five questions below, calling on teams from different scenarios. |
| **0:55–1:00** | Wrap | The takeaway (below), then the bridge to the afternoon speaker: *Thinking Machines builds the tooling (Tinker) for exactly what you just did, at frontier scale.* |

**If you are short on time:** skip Step 3 (prompt + docs) and Step 7. That saves ~5 minutes.

## Teams and settings cards

Every student runs **their own notebook** (free Colab gives each Google account its own GPU). Teams of 4–5 work on one scenario, and each team member takes a different settings card, so every team produces a mini-experiment.

| Card | `N_EXAMPLES` | `DATA` | `EPOCHS` | What it tests |
|---|---|---|---|---|
| **A** | 25 | clean | 2 | How far do a handful of examples go? |
| **B** | 100 | clean | 2 | The default |
| **C** | 300 | clean | 1 | Does more data help? |
| **D** | 100 | noisy | 2 | Same size as B, worse labels |
| **E** | 300 | noisy | 1 | Can more data make up for bad labels? |

**Scenario assignment:** with 18 teams, give each of the 5 scenarios to 3–4 teams. To keep the debrief tight, you can concentrate on the two finance scenarios (`invoice_intake`, `expense_audit`), which connect most directly to the Bridgewater case.

## Leaderboard

Create a Google Sheet (or Form) with one column. Students paste the line printed by Step 8, for example:

```
team=team-3 | scenario=claims_triage | examples=100 | data=clean | epochs=2 | prompt=..% | prompt+docs=..% | fine-tuned=..%
```

Use *Data → Split text to columns* on `|` to chart it live.

## Setup checklist (do this a few days before class)

- [ ] **Make the notebook reachable.** The notebook's first cell runs `git clone` on this repository and branch (set in `scripts/build_notebook.py`). The repo must be **public** for students to clone it without logging in, or you can copy the `nemotron-lab/` folder into a public course repo and update `REPO`/`BRANCH`, then run `python scripts/build_notebook.py`.
- [ ] **Share the notebook link:** `https://colab.research.google.com/github/<owner>/<repo>/blob/<branch>/nemotron-lab/notebooks/finetune_lab.ipynb`. If the branch name contains a `/`, merge to `main` first and use `main` in the link.
- [ ] **Run [`notebooks/instructor_dry_run.ipynb`](../notebooks/instructor_dry_run.ipynb) in Colab.** For all five scenarios it runs both baselines, fine-tunes at each settings card, and reports the **fewest training examples that give a clear improvement**, meaning the fine-tuned 95% range lies entirely above the baseline's. `MODE = "quick"` (cards B and D, ~1 hour on a free T4) tells you whether the default of 100 examples is enough. `MODE = "full"` (~3 hours on a T4, ~1 hour on an L4 or A100 with Colab Pro) gives the whole learning curve. Results save to Google Drive after every run, so a disconnect loses nothing. Copy the results into the table below.
- [ ] **Check the model license and access.** `nvidia/Llama-3.1-Nemotron-Nano-4B-v1.1` is published under NVIDIA's open model license. Confirm that it is still downloadable without a login and that classroom use is fine.
- [ ] **Have a backup.** Free Colab GPUs are usually available but not guaranteed for 90 people at once. Have a **Colab Pro** account ready to project a full run, and tell students without a GPU to pair up with a teammate.
- [ ] *(Optional)* Ask students to run Step 0 before class. Colab sessions time out after ~90 minutes idle, so only do this right before class.

### Dry-run results (fill in from `instructor_dry_run.ipynb`)

| Scenario | Prompt | Prompt + docs | Fine-tuned (card B) | Fewest examples to clearly beat prompt | Train min / 100 passes | Notes |
|---|---|---|---|---|---|---|
| airline_complaints | | | | | | |
| invoice_intake | | | | | | |
| claims_triage | | | | | | |
| expense_audit | | | | | | |
| lead_qualification | | | | | | |

**If a scenario reports "not reached" for 100 examples:** raise `N_EXAMPLES` in the notebook's Step 4 default (and on cards B and D) to the number the dry run reports, or drop that scenario. Training time grows roughly in proportion to `N_EXAMPLES × EPOCHS`.

**Why 100 examples has a good chance of working:** each training sample is drawn so that every answer value appears at least 5 times (at least 3 for 50 examples), so rare rules such as "business class on a short flight" or "enterprise + high intent → enterprise AE" are never missing. Clean and noisy runs use the same messages, so card B vs card D isolates label quality.

**What to expect** (confirm in your dry run). Prompting alone usually gets the "obvious" fields (category, claim type, expense type) partly right but misses the company-specific rules (priority tiers, approval thresholds, SIU red flags, APAC routing), so its *all fields correct* score is low. Pasting the policy in usually helps, at the cost of many more tokens per request. Fine-tuning on 100+ clean examples should give the highest and most consistent scores. Noisy data and 25 examples should visibly underperform. Fields that need arithmetic (expense per-person limits) stay hard for every method, which is a good discussion point.

## Debrief questions and talking points

1. **Which method won, on accuracy and on cost?**
   Look at prompt tokens per request: "prompt + docs" pays for the whole policy on *every* request. At 4,000 complaints a day that adds up, and a 200-page policy may not fit in the prompt at all. Fine-tuning pays once, at training time, and then runs a small, cheap model.

2. **Tacit judgment.** Our policies were written down, which made "prompt + docs" competitive. In real companies the best experts' judgment often isn't written down: *"I just know this claim smells wrong."* Examples can carry what documents can't. This is the Bridgewater/Thinking Machines thesis.

3. **Data is the asset.** Compare cards B vs D and C vs E across teams. Label quality often matters as much as label quantity. This is why expert-data companies like Mercor exist, and why a firm's historical decisions, if they are clean, can be a moat. Ask: who in your company owns this data today, and is it clean?

4. **Open vs closed weights.** The students' model runs on a free GPU, on hardware they control, with weights they own. When does that matter? Privacy (claims, expenses), regulation, cost at volume, avoiding vendor lock-in. When wouldn't they bother? Low volume, broad tasks, or no labeled data.

5. **Risk and governance.** Look at the remaining errors: are they cheap (a P2 marked P3) or expensive (an injury claim fast-tracked, a fake vendor auto-approved)? Where does a human stay in the loop? What happens when the policy changes next quarter? The model has to be retrained and re-tested, so who owns that process?

**Takeaway:** *Prompting tells the model what you want. RAG gives it what you know. Fine-tuning teaches it how your best people decide. The scarce input isn't the model, it's clean, expert-labeled data.*

## Troubleshooting

| Symptom | Fix |
|---|---|
| `No GPU found` | Runtime → Change runtime type → T4 GPU, then re-run Step 0 |
| "Cannot connect to GPU backend" | Colab is out of free GPUs: pair up with a teammate, or use the instructor's projected run |
| `git clone` fails | Repo isn't public, or the `REPO`/`BRANCH` in the first cell is wrong |
| Out of memory during training | Runtime → Restart session, re-run Step 0, use fewer examples |
| Training is slow (> 8 min) | Choose `N_EXAMPLES × EPOCHS ≤ 300` |
| Want to retrain | Just change Step 4 and re-run Steps 5–6. Each run starts from the original model |
