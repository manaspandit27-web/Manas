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
| [`instructor/INSTRUCTOR-GUIDE.md`](instructor/INSTRUCTOR-GUIDE.md) | Instructors | 60-minute run of show, settings cards, setup checklist, debrief questions, troubleshooting |
| `scenarios/<name>/` | Both | `case.md` (1-page case), `policy.md` (the expert rules), `train.csv` (600 expert-labeled), `train_noisy.csv` (same, 30% mislabeled), `test.csv` (100 held out) |
| `lab/core.py` | Under the hood | Loading, prompting, LoRA training and scoring, kept out of the notebook so cells stay short |
| `scripts/` | Maintainers | `generate_data.py` rebuilds the datasets; `build_notebook.py` rebuilds the notebook |
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
- Evaluation uses greedy (deterministic) decoding on the first 40 test examples. A field counts as correct on an exact match after normalization; the headline metric is *all fields correct*.
- Larger Nemotron models, such as Nemotron 3.5 Lightning 30B-A3B, need far more GPU memory than free Colab offers. To try one, change `DEFAULT_MODEL` in `lab/core.py` and use a bigger runtime.
