# Instructor guide: Data and Fine-Tuning Models (60 minutes)

**Session goal:** students leave able to explain the three ways to bring company data to a model (prompting, RAG, fine-tuning), when each one fits, and why open-weight models plus expert-labeled data can beat frontier models on narrow tasks.

**How it works:** the instructor runs everything, on the projector. Students don't run any code. They label examples, and the model is fine-tuned on their labels in front of them.

**Pre-work for students:** [`PRE-READ.md`](../PRE-READ.md) (~15 min) plus, optionally, the Bridgewater × Thinking Machines post it links to.

---

## Run of show

For a step-by-step view of what the instructor does and what students do, see [`ACTIVITY-WALKTHROUGH.md`](ACTIVITY-WALKTHROUGH.md).

The timings are a suggestion and have not been rehearsed with a class.

| Time | Block | What happens |
|---|---|---|
| **0:00–0:10** | Framing (instructor) | "How do you bring your data to the model?" Prompt vs RAG vs fine-tune (pre-read §2), open vs closed weights (§4), the Bridgewater × Thinking Machines result (§5). |
| **0:10–0:18** | Ask the original model | On the projector, open the chat ([`notebooks/projector_demo.ipynb`](../notebooks/projector_demo.ipynb)). The chat opens with the instruction the model is given. Ask it three to five messages from the case. Before each answer, ask the class what the company's rules say the answer should be. |
| **0:18–0:30** | Students label | Hand out the company's rules and the examples to label (see below). Students fill in the labels and send them back. |
| **0:30–0:42** | Fine-tune on screen | Switch the projector to the Colab notebook. Run the cell that loads the students' file, then the fine-tuning cell. The class sees the code and its progress. It takes about 9 to 13 minutes for 100 examples on a T4, so use the time for debrief questions 2 and 3. |
| **0:42–0:50** | Switch and ask again | Run the notebook's last cell, `chat.serve("fine-tuned")`. Go back to the chat and press **Ask the same questions again**. Compare the new answers with the earlier ones, and with the rules. |
| **0:50–1:00** | Debrief and wrap | The remaining questions below, then the takeaway. |

## How the class labels examples

1. **Pick one company** and set it as `SCENARIO` in the notebook. The dry run below shows that 100 examples are enough for four of the five; `invoice_intake` needs about 300, so avoid it.
2. **Hand out the examples file:** `scenarios/<name>/examples_to_label.csv`. It has 100 messages and one empty column per answer field. The simplest way is to put it in one Google Sheet and divide the rows among students or teams.
3. **Give students the company's rules:** `scenarios/<name>/policy.md`, and the one-page case in `case.md`.
4. **Get it back as CSV.** From a Google Sheet: File → Download → CSV.
5. **Load it in the notebook.** The cell under *Fine-tune on the class's labels* asks for the file and prints how many labelled examples it read and how many rows it skipped.

**About the labelled files**

- Each file needs the `input` column (or the `id` column) and one column per answer field, as in the examples file.
- Several files can be loaded at once. When two students labelled the same message, the more common label is used.
- A row is skipped if a label is missing or is not one of the allowed values. Capitals, spaces and hyphens are forgiven: "Baggage services" counts as `baggage_services`.
- No class file? The same cell has a commented-out line that uses 100 of the lab's own labelled examples instead.

## Setup checklist (do this a few days before class)

- [ ] **Run [`notebooks/projector_demo.ipynb`](../notebooks/projector_demo.ipynb) from start to finish on a GPU.** As of 3 October 2026 the chat has been tested in Colab with simulated answers and with a tiny stand-in model, but not yet on the real model on a GPU, because Colab's free GPU limit had been used up. Do a full run, including a fine-tune, before relying on it in class.
- [ ] **Keep the repository public.** The notebook's first cell runs `git clone` on this repository and branch (set in `scripts/build_notebook.py`).
- [ ] **Prepare the examples file and the rules handout** for the company you picked (see above).
- [ ] **Plan for the GPU.** Free Colab GPUs are not guaranteed, and the free tier cut ours off after about 5.5 hours of use. Avoid heavy GPU use in the day before class, and have a **Colab Pro** or pay-as-you-go account ready.
- [ ] **Rehearse the flow without a GPU:** `python -m lab.demo --simulate` from `nemotron-lab/`. Answers are simulated and the page says so.
- [ ] **Check the model license and access.** `nvidia/Llama-3.1-Nemotron-Nano-4B-v1.1` is published under NVIDIA's open model license. Confirm that it is still downloadable without a login and that classroom use is fine.
- [ ] *(Done once.)* [`notebooks/instructor_dry_run.ipynb`](../notebooks/instructor_dry_run.ipynb) measures, for all five companies, how the original model, the model with the policy pasted in, and fine-tuned models score on 100 held-out test cases. Results are below. `MODE = "quick"` took about 3 hours 20 minutes on a free T4.

**Things to know about the chat**

- One Colab GPU does everything, so the chat cannot answer while the model is fine-tuning. The chat page says so.
- The chat page is only a chat. Fine-tuning and switching model are done in the notebook.
- The fine-tuned model is kept only while the notebook session lasts.
- The chat's address only works in the instructor's own browser, while the notebook is running.

### Dry-run results (free Colab T4, quick mode, 2–3 October 2026)

All fields correct on 100 held-out test cases. Full tables, per-field scores, the raw CSVs and the executed notebook are in [`dry-run-2026-10-03/`](dry-run-2026-10-03/README.md).

| Scenario | Prompt | Prompt + docs | Fine-tuned (100 clean examples) | Fewest examples to clearly beat prompt | Train min / 100 passes | Notes |
|---|---|---|---|---|---|---|
| airline_complaints | 7% | 31% | 73% | 100 | 5.7 | Also clearly beats prompt + docs. Noisy labels: 59% |
| invoice_intake | 1% | 21% | 10% | 100 | 6.4 | **Does not beat prompt + docs at 100.** Needs 300 examples (57%). Noisy labels: 6% |
| claims_triage | 6% | 15% | 72% | 100 | 5.8 | Also clearly beats prompt + docs. Noisy labels: 37% |
| expense_audit | 23% | 22% | 75% | 100 | 4.4 | Also clearly beats prompt + docs. Noisy labels: 59% |
| lead_qualification | 3% | 12% | 54% | 100 | 4.7 | Also clearly beats prompt + docs. Noisy labels: 41% |

Quick mode only tests 100 examples, so "100" means 100 was enough, not that it is the minimum.

**`invoice_intake` needs a different setting.** With 100 examples the model learns to extract the vendor, invoice number and amount, but not the GL code (42%) or the approval path (34%). More examples fix it: 38% all-correct at 200 and 57% at 300, which clearly beats prompt + docs. At 300 examples training takes about 38 minutes on a T4, which is too long for the 60-minute session, so don't assign this scenario at the default settings.

**Giving a fine-tuned model the policy docs as well did not help.** On `invoice_intake`, the model fine-tuned on 200 examples scored 38% with the normal prompt and 37% with the policy pasted in. At 300 examples the policy made it worse: 57% without, 38% with. The model was trained on prompts without the policy, so a prompt with the policy is unfamiliar to it. This is a useful debrief point: fine-tuning and "prompt + docs" do not simply add up.

**Why 100 examples has a good chance of working:** each training sample is drawn so that every answer value appears at least 5 times (at least 3 for 50 examples), so rare rules such as "business class on a short flight" or "enterprise + high intent → enterprise AE" are never missing. Clean and noisy runs use the same messages, so the clean and noisy columns isolate label quality.

**What to expect** (confirm in your dry run). Prompting alone usually gets the "obvious" fields (category, claim type, expense type) partly right but misses the company-specific rules (priority tiers, approval thresholds, SIU red flags, APAC routing), so its *all fields correct* score is low. Pasting the policy in usually helps, at the cost of many more tokens per request. Fine-tuning on 100+ clean examples should give the highest and most consistent scores. Noisy data and 25 examples should visibly underperform. Fields that need arithmetic (expense per-person limits) stay hard for every method, which is a good discussion point.

## Debrief questions and talking points

1. **Which method won, on accuracy and on cost?**
   Look at prompt tokens per request: "prompt + docs" pays for the whole policy on *every* request. At 4,000 complaints a day that adds up, and a 200-page policy may not fit in the prompt at all. Fine-tuning pays once, at training time, and then runs a small, cheap model.

2. **Tacit judgment.** Our policies were written down, which made "prompt + docs" competitive. In real companies the best experts' judgment often isn't written down: *"I just know this claim smells wrong."* Examples can carry what documents can't. This is the Bridgewater/Thinking Machines thesis.

3. **Data is the asset.** Compare the clean and noisy columns in the dry-run results above, and look at where the class's own labels disagreed. Label quality often matters as much as label quantity. This is why expert-data companies like Mercor exist, and why a firm's historical decisions, if they are clean, can be a moat. Ask: who in your company owns this data today, and is it clean?

4. **Open vs closed weights.** This model runs on a free GPU, on hardware you control, with weights you own. When does that matter? Privacy (claims, expenses), regulation, cost at volume, avoiding vendor lock-in. When wouldn't you bother? Low volume, broad tasks, or no labeled data.

5. **Risk and governance.** Look at the remaining errors: are they cheap (a P2 marked P3) or expensive (an injury claim fast-tracked, a fake vendor auto-approved)? Where does a human stay in the loop? What happens when the policy changes next quarter? The model has to be retrained and re-tested, so who owns that process?

**Takeaway:** *Prompting tells the model what you want. RAG gives it what you know. Fine-tuning teaches it how your best people decide. The scarce input isn't the model, it's clean, expert-labeled data.*

## Troubleshooting

| Symptom | Fix |
|---|---|
| `No GPU found` | Runtime → Change runtime type → T4 GPU, then re-run the cells |
| "Cannot connect to GPU backend" | Colab's free GPU limit is used up. Wait for it to reset, or use Colab Pro or pay-as-you-go. Rehearsal mode still works without a GPU |
| `git clone` fails | Repo isn't public, or the `REPO`/`BRANCH` in the first cell is wrong |
| The notebook says it could not use a file | It needs the `input` (or `id`) column and one column per answer field, with the column names from the examples file |
| Rows are skipped | A label is missing, or is not one of the allowed values listed in the chat's first message |
| Fine-tuning takes too long | Time grows with the number of examples. Interrupt the cell (the stop button next to it); the original model is unchanged. Use about 100 examples |
| The chat page stops responding | The notebook session ended. Re-run the notebook's cells. The fine-tuned model is lost and has to be trained again |

---

## Earlier version: every student runs the notebook (not the plan for this session)

[`notebooks/finetune_lab.ipynb`](../notebooks/finetune_lab.ipynb) is an earlier design in which each student fine-tunes the model in their own Colab session. It is kept for reference. Everything below this line describes that version only.

### Run of show (student-run version)

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

### Teams and settings cards

Every student runs **their own notebook** (free Colab gives each Google account its own GPU). Teams of 4–5 work on one scenario, and each team member takes a different settings card, so every team produces a mini-experiment.

| Card | `N_EXAMPLES` | `DATA` | `EPOCHS` | What it tests |
|---|---|---|---|---|
| **A** | 25 | clean | 2 | How far do a handful of examples go? |
| **B** | 100 | clean | 2 | The default |
| **C** | 300 | clean | 1 | Does more data help? |
| **D** | 100 | noisy | 2 | Same size as B, worse labels |
| **E** | 300 | noisy | 1 | Can more data make up for bad labels? |

**Scenario assignment:** with 18 teams, give each of the 5 scenarios to 3–4 teams. To keep the debrief tight, you can concentrate on the two finance scenarios (`invoice_intake`, `expense_audit`), which connect most directly to the Bridgewater case.

### Leaderboard

Create a Google Sheet (or Form) with one column. Students paste the line printed by Step 8, for example:

```
team=team-3 | scenario=claims_triage | examples=100 | data=clean | epochs=2 | prompt=..% | prompt+docs=..% | fine-tuned=..%
```

Use *Data → Split text to columns* on `|` to chart it live.

### Setup and troubleshooting (student-run version)

- Share the notebook link: `https://colab.research.google.com/github/<owner>/<repo>/blob/<branch>/nemotron-lab/notebooks/finetune_lab.ipynb`. If the branch name contains a `/`, merge to `main` first and use `main` in the link.
- Free Colab GPUs are not guaranteed for 90 people at once. Tell students without a GPU to pair up with a teammate.
- Colab sessions time out after about 90 minutes idle, so only ask students to run Step 0 right before class.
- If the dry run reports "not reached" for 100 examples: raise `N_EXAMPLES` in the notebook's Step 4 default (and on cards B and D) to the number the dry run reports, or drop that scenario. Training time grows roughly in proportion to `N_EXAMPLES × EPOCHS`.
- Out of memory during training: Runtime → Restart session, re-run Step 0, use fewer examples.
- Training is slow (over 8 minutes): choose `N_EXAMPLES × EPOCHS ≤ 300`.
- To retrain, change Step 4 and re-run Steps 5–6. Each run starts from the original model.
