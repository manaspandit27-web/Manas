# Nemotron fine-tuning lab: bringing your data to the model

An in-class activity for an MBA session on **Data and Fine-Tuning Models**. Students fine-tune an open-weight model (NVIDIA **Llama-3.1-Nemotron-Nano-4B**) on one of five business processes in Google Colab. They compare three ways of bringing company knowledge to a model on the same held-out test cases:

1. **Prompt only:** the task and allowed answers.
2. **Prompt + docs:** the company policy pasted into every request (what RAG automates).
3. **Fine-tuned:** LoRA training on expert-labeled examples. Students choose how many examples and how clean they are.

The session follows the idea in Bridgewater × Thinking Machines, *[Learning to Replicate Expert Judgment in Financial Tasks](https://thinkingmachines.ai/news/learning-to-replicate-expert-judgment-in-financial-tasks/)* (June 2026): expert judgment that is hard to put in a prompt can be taught through labeled examples.

## What's here

| Path | For | What it is |
|---|---|---|
| [`PRE-READ.md`](PRE-READ.md) | Students, before class | 15-minute interactive note: prompting vs RAG vs fine-tuning, determinism, open vs closed weights, the Bridgewater case |
| [`notebooks/finetune_lab.ipynb`](notebooks/finetune_lab.ipynb) | Students, in class | The Colab notebook. Students run it top to bottom and edit only the ✏️ cells |
| [`notebooks/instructor_dry_run.ipynb`](notebooks/instructor_dry_run.ipynb) | Instructors, before class | Runs baselines and fine-tuning sweeps on all 5 scenarios (100 test cases each) and reports the fewest examples that give a clear improvement |
| [`notebooks/projector_demo.ipynb`](notebooks/projector_demo.ipynb) | Instructors, in class | A plain chat page for the projector: ask the model, fine-tune it on examples the class labelled, ask again |
| [`instructor/INSTRUCTOR-GUIDE.md`](instructor/INSTRUCTOR-GUIDE.md) | Instructors | 60-minute run of show, settings cards, setup checklist, debrief questions, troubleshooting |
| [`instructor/dry-run-2026-10-03/`](instructor/dry-run-2026-10-03/README.md) | Instructors | Results of a full dry run on a free Colab T4: tables, raw CSVs, executed notebook |
| `scenarios/<name>/` | Both | `case.md` (1-page case), `policy.md` (the expert rules), `train.csv` (600 expert-labeled), `train_noisy.csv` (same, 30% mislabeled), `test.csv` (100 held out) |
| `lab/demo.py`, `lab/demo_ui.html` | Under the hood | The projector chat: a small web server and its page |
| `lab/core.py` | Under the hood | Loading, prompting, LoRA training and scoring, kept out of the notebook so cells stay short |
| `scripts/` | Maintainers | `generate_data.py` rebuilds the datasets; `build_notebook.py` rebuilds both notebooks |
| `tests/` | Maintainers | Data checks and a CPU smoke test of the full train → evaluate loop on a tiny stand-in model |

## The five business processes

| Scenario | Company (fictional) | Function | The model decides |
|---|---|---|---|
| `airline_complaints` | Skyward Airways | Operations / service | category, priority, routing, compensation |
| `invoice_intake` | Harvest Table Restaurant Group | Finance / AP | vendor, invoice #, amount, GL code, approval path |
| `claims_triage` | Granite Shield Insurance | Risk / insurance ops | claim type, injury, damage band, routing (incl. fraud review) |
| `expense_audit` | Meridian Advisory | Finance / compliance | expense type, decision, reason code |
| `lead_qualification` | Lumen Analytics | Marketing / sales | segment, intent, sales routing |

All companies, people and data are synthetic. Labels come from applying each `policy.md` to the facts in each message, so they are always consistent with the policy.

## Running it

**In Colab:** open `notebooks/finetune_lab.ipynb` in Colab, choose a **T4 GPU** runtime, and run the cells in order. The first cell clones this repo, so the repo has to be public (see the instructor setup checklist).

**Locally (maintainers):**

```bash
cd nemotron-lab
pip install torch transformers peft pandas matplotlib tokenizers pytest
python scripts/generate_data.py   # regenerate scenarios/*/*.csv (deterministic)
python scripts/build_notebook.py  # regenerate the notebook after editing its cells
python -m pytest -q tests         # data checks + CPU smoke test (no GPU or model download)
```

## Technical notes

- Model: `nvidia/Llama-3.1-Nemotron-Nano-4B-v1.1`, loaded in 4-bit (bitsandbytes NF4), with reasoning turned off via the `detailed thinking off` system prompt.
- Fine-tuning: LoRA rank 16 on all attention and MLP projections (well under 1% of parameters are trained). The loss covers only the answer tokens. It uses fp16 mixed precision on a T4, or bf16 where supported.
- Training samples are drawn so that every answer value appears at least 5 times (`pick_training_rows`); clean and noisy runs use the same messages.
- Evaluation uses greedy (deterministic) decoding on the first 60 test examples (100 in the instructor dry run). A field counts as correct on an exact match after normalization; the headline metric is *all fields correct*, shown with a 95% (Wilson) range.
- Larger Nemotron models, such as Nemotron 3.5 Lightning 30B-A3B, need far more GPU memory than free Colab offers. To try one, change `DEFAULT_MODEL` in `lab/core.py` and use a bigger runtime.
