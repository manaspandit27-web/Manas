"""Builds notebooks/finetune_lab.ipynb, notebooks/instructor_dry_run.ipynb and notebooks/projector_demo.ipynb from the
cells below (edit here, then re-run).

Usage:  python scripts/build_notebook.py
"""

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "notebooks" / "finetune_lab.ipynb"
REPO = "https://github.com/manaspandit27-web/manas.git"
BRANCH = "claude/nemotron-finetune-lab"

CELLS = [
    ("md", """# Bringing your data to the model: fine-tuning NVIDIA Nemotron

**In this lab you will teach an open-weight AI model your company's expert judgment, then measure whether it worked.**

You will try the three ways to bring company knowledge to a model, on the same 60 test cases:

| | Method | What the model gets |
|---|---|---|
| 1 | **Prompt** | The task and the allowed answers. Nothing about *your* company's rules. |
| 2 | **Prompt + docs** | The company's policy document pasted into every request (what RAG automates). |
| 3 | **Fine-tuned** | Hundreds of examples labeled by your experts, *trained into the model's weights*. |

The model is **NVIDIA Llama-3.1-Nemotron-Nano-4B**: an *open-weight* model you can download, change, and run on your own hardware. Today it runs on a free Google Colab GPU.

**How to use this notebook:** run the cells from top to bottom (click a cell, press **Shift + Enter**). You only edit cells marked ✏️. You don't need to know how to code."""),

    ("md", """## Step 0: Setup (start this first; it takes ~4 minutes)

1. In the menu, choose **Runtime → Change runtime type → T4 GPU → Save**.
2. Run the two cells below. The first one installs the tools; the second downloads Nemotron (~8 GB) and loads it in compressed 4-bit form.

While it loads, read your team's case (Step 1 prints it, or open `scenarios/<your scenario>/case.md`)."""),

    ("code", f"""# Downloads the lab materials and installs two libraries (~1 minute)
REPO = "{REPO}"
BRANCH = "{BRANCH}"
import os, sys
if not os.path.exists("/content/lab-repo"):
    !git clone -q --depth 1 -b {{BRANCH}} {{REPO}} /content/lab-repo
os.chdir("/content/lab-repo/nemotron-lab")
!pip install -q bitsandbytes peft
sys.path.insert(0, ".")
from lab import core
from IPython.display import Markdown, display
import pandas as pd
print("Ready. Scenarios:")
display(pd.DataFrame(core.list_scenarios()))"""),

    ("code", """# Loads NVIDIA Nemotron onto the GPU (~3 minutes the first time)
model, tok = core.load_model()
print("Model loaded:", core.DEFAULT_MODEL)"""),

    ("md", """## Step 1: Pick your business process ✏️

Your instructor will assign your team one of these:

| `SCENARIO` | Company | Function |
|---|---|---|
| `airline_complaints` | Skyward Airways | Operations / Customer service |
| `invoice_intake` | Harvest Table Restaurant Group | Finance / Accounts payable |
| `claims_triage` | Granite Shield Insurance | Risk / Insurance operations |
| `expense_audit` | Meridian Advisory | Finance / Compliance |
| `lead_qualification` | Lumen Analytics | Marketing / Sales |"""),

    ("code", """# ✏️ EDIT THESE TWO LINES
TEAM_NAME = "team-1"
SCENARIO = "airline_complaints"

scn = core.load_scenario(SCENARIO)
display(Markdown(scn.case))
print(f"\\n{len(scn.train)} expert-labeled training examples, {len(scn.test)} held-out test examples. A few of them:")
core.show_examples(scn.train, 5)"""),

    ("md", """## Step 2: Method 1, prompt only

We ask Nemotron to do the task with only a description and the list of allowed answers. This is roughly what you get from any general-purpose chatbot.

**Before you run it:** which fields do you expect it to get right, and which wrong? Why?"""),

    ("code", """print("This is the full instruction the model receives:\\n")
print(core.system_prompt(scn))
base = core.evaluate(model, tok, scn, "prompt")
core.compare(base)"""),

    ("code", """# Where did it go wrong? (expert answer vs model answer)
core.mistakes(base, 5)"""),

    ("md", """## Step 3: Method 2, prompt + company docs

Now we paste the company's written policy into every request. This is "bring the data to the model at question time", which is what a RAG system does automatically by retrieving the right documents.

**Watch two numbers:** accuracy, and *prompt tokens per request*. With a hosted model you pay for every token, on every request, forever."""),

    ("code", """display(Markdown(scn.policy))
docs = core.evaluate(model, tok, scn, "prompt+docs")
core.compare(base, docs)"""),

    ("md", """## Step 4: Your fine-tuning decisions ✏️

You are the data owner. Choose:

* **`N_EXAMPLES`**: how many expert-labeled examples to train on: `25`, `100` or `300`. More data costs more expert time (think of the experts Mercor and others pay to label data for AI labs).
* **`DATA`**: `"clean"` (labeled by your best experts) or `"noisy"` (what years of inconsistent human tagging really looks like: 30% of rows have a wrong label).
* **`EPOCHS`**: how many times the model reads the training data: `1`, `2` or `3`.

Your instructor may hand you a settings card so that your team covers different combinations.

**Write down your prediction before you train:** what accuracy will you get?"""),

    ("code", """# ✏️ EDIT THESE THREE LINES
N_EXAMPLES = 100     # 25, 100 or 300
DATA = "clean"       # "clean" or "noisy"
EPOCHS = 2           # 1, 2 or 3

passes = N_EXAMPLES * EPOCHS
print(f"The model will study {passes} examples in total.",
      "Expect ~3-4 minutes on a free T4." if passes <= 300 else "This could take 8+ minutes on a free T4; consider fewer.")"""),

    ("md", """## Step 5: Fine-tune ⏳

Training uses **LoRA**: instead of changing all 4 billion numbers in the model, it trains small "adapter" layers (under 1% of the size) on top of a frozen, compressed model. That is why this fits on a free GPU in minutes rather than on a data-center cluster for weeks.

The **loss** is how surprised the model is by your experts' answers. Watch it fall.

*While it trains:* one person on your team writes a tricky test case for Step 7, and everyone else discusses the questions at the end."""),

    ("code", """model, losses = core.train(model, tok, scn, n_examples=N_EXAMPLES, data=DATA, epochs=EPOCHS)
core.plot_loss(losses)"""),

    ("md", """## Step 6: Method 3, the fine-tuned model

Same 60 test cases. None of them were in the training data.

**Is the change real?** Look at the *95% range* column. If the fine-tuned range does not overlap the prompt-only range, the improvement is almost certainly not luck."""),

    ("code", """tuned = core.evaluate(model, tok, scn, "fine-tuned")
display(core.compare(base, docs, tuned))
core.plot_compare(base, docs, tuned, title=f"{scn.company}: all fields correct")"""),

    ("code", """# What is it still getting wrong? Are these mistakes cheap or expensive for the business?
core.mistakes(tuned, 5)"""),

    ("md", """## Step 7: Try to break it ✏️

Write your own test case: an edge case, an ambiguous message, or something the policy doesn't cover. Compare the fine-tuned model with the original one.

Then run the cell a few times. Do you get the same answer every time? (We use *greedy* decoding, so it is deterministic. Ask yourself whether the answer is *consistently right*.)"""),

    ("code", """# ✏️ REPLACE THE TEXT WITH YOUR OWN TEST CASE (this starter example matches your scenario)
MY_TEST = core.SAMPLE_TESTS[SCENARIO] if SCENARIO in core.SAMPLE_TESTS else "write your own test here"
print("Testing:", MY_TEST, "\\n")

print("Fine-tuned model:", core.ask(model, tok, scn, MY_TEST))
with model.disable_adapter():
    print("Original model:  ", core.ask(model, tok, scn, MY_TEST))"""),

    ("md", """## Step 8: Post your result

Copy the line below into the class leaderboard your instructor shares."""),

    ("code", """core.scorecard(TEAM_NAME, scn, {"examples": N_EXAMPLES, "data": DATA, "epochs": EPOCHS}, base, docs, tuned);"""),

    ("md", """## Discuss with your team

1. **Prompt vs docs vs fine-tuning.** Which method won on accuracy? On cost per request (prompt tokens)? What would change if your policy document were 200 pages instead of one?
2. **Tacit judgment.** Your policy was fully written down. In most companies the best experts' judgment *isn't*. Which method still works when the rules can't be written down?
3. **Data is the asset.** How much did clean vs noisy data matter compared with the number of examples? Who in your company owns labeled data like this today?
4. **Open vs closed weights.** You just trained a model you could run on your own servers. When does that matter (privacy, cost, control, regulation), and when would you rather use a closed frontier model through an API?
5. **Risk.** Look at the remaining mistakes. Which ones would you let a model make unsupervised, and where must a human stay in the loop? What happens when the policy changes next quarter?

---
*Finished early?* Go back to Step 4, change your settings (or `SCENARIO` in Step 1, then re-run Steps 2-6) and train again. Each `core.train(...)` call starts fresh from the original model."""),
]


DRY_RUN_CELLS = [
    ("md", """# Instructor dry run: will students see a real change after fine-tuning?

Run this **once, a few days before class**. For each of the five scenarios it measures, on **100** held-out test cases:

* the two baselines: **prompt only** and **prompt + policy docs**,
* **fine-tuned** accuracy at different amounts of clean and noisy training data (the student settings cards),
* how long training takes on your GPU.

It then tells you, per scenario, the **fewest training examples that give a clear improvement**, meaning the fine-tuned 95% range sits entirely above the baseline's range. Use that to set the default `N_EXAMPLES` and the settings cards.

| `MODE` | Fine-tuning runs per scenario | Rough time, 5 scenarios |
|---|---|---|
| `"quick"` | 100 clean, 100 noisy (cards B and D) | ~3 hours on a free T4 (measured, 3 Oct 2026) |
| `"full"` | 25 / 50 / 100 / 200 / 300 clean, 100 / 300 noisy | Not measured. Roughly 10 hours on a T4 by extrapolation, so use an L4 or A100 (Colab Pro) |

*The free tier cut the GPU off after about 5.5 hours in one session, so `"full"` will not finish on a free T4 in one go.* Results are saved after every run, so if Colab disconnects, re-run the cells and it continues where it stopped. The report prints the measured training speed."""),

    ("md", """## 1. Setup

Runtime → Change runtime type → **T4 GPU** (or L4 / A100 with Colab Pro), then run:"""),
    ("code", f"""# Downloads the lab materials and installs two libraries (~1 minute)
REPO = "{REPO}"
BRANCH = "{BRANCH}"
import os, sys
if not os.path.exists("/content/lab-repo"):
    !git clone -q --depth 1 -b {{BRANCH}} {{REPO}} /content/lab-repo
os.chdir("/content/lab-repo/nemotron-lab")
!pip install -q bitsandbytes peft
sys.path.insert(0, ".")
from lab import core
from IPython.display import Markdown, display
import pandas as pd
print("Ready. Scenarios:")
display(pd.DataFrame(core.list_scenarios()))"""),


    ("code", """# Options
MODE = "quick"          # "quick" or "full"
SCENARIOS = [s["scenario"] for s in core.list_scenarios()]   # or e.g. ["invoice_intake", "expense_audit"]
SAVE_TO_DRIVE = True    # keeps results if the Colab session ends (asks for Google Drive permission)

OUT = "dry_run_results.csv"
if SAVE_TO_DRIVE:
    from google.colab import drive
    drive.mount("/content/drive")
    OUT = "/content/drive/MyDrive/nemotron_dry_run_results.csv"
SETTINGS = core.QUICK_SWEEP if MODE == "quick" else core.FULL_SWEEP
print("Results file:", OUT)
print("Fine-tuning settings (examples, data, epochs):", SETTINGS)"""),

    ("code", """# Loads NVIDIA Nemotron onto the GPU (~3 minutes)
model, tok = core.load_model()"""),

    ("md", "## 2. Run everything (leave the tab open)"),

    ("code", """model, rows = core.sweep(model, tok, SCENARIOS, SETTINGS, n_test=100, out_csv=OUT)"""),

    ("md", """## 3. Results

**How to read the recommendations:**

* *fewest examples: clearly beats prompt*: the smallest training set whose fine-tuned 95% range lies entirely above the prompt-only range. If this is **100 or less**, the default student setting (card B) will show a detectable change.
* *fewest examples: clearly beats prompt+docs*: the stronger test. Fine-tuning should beat pasting the policy into every prompt, too.
* **"not reached"** means no setting cleared the bar. Raise the default `N_EXAMPLES` (or `EPOCHS`) for that scenario, or don't assign it.

Copy the numbers into the *Dry-run results* table in `instructor/INSTRUCTOR-GUIDE.md`."""),

    ("code", """table, recs = core.sweep_report(OUT)
display(recs)
display(table)"""),

    ("code", """# Download the raw results (one row per run, including per-field accuracy)
from google.colab import files
files.download(OUT)"""),

    ("md", """## 4. Optional: more examples for invoice_intake, and fine-tuned + docs

Run this after sections 1-3 if `invoice_intake` reports **"not reached"**. It fine-tunes that scenario on more examples (200 and 300), then on the card B and card D settings, and tests every fine-tuned model twice on the same 100 held-out cases:

* **fine-tuned**: the normal prompt (no policy), as in section 2,
* **fine-tuned+docs**: the same fine-tuned model with the policy pasted into the prompt.

Allow about 2 hours on a T4. Results go to a separate file, `nemotron_ft_plus_docs_results.csv`, and the cell resumes if re-run. It needs `SAVE_TO_DRIVE = True`."""),

    ("code", r'''# Extra experiment on invoice_intake: more training examples, and every fine-tuned model is tested twice:
# with the normal prompt ("fine-tuned") and with the policy docs pasted into the prompt ("fine-tuned+docs").
# Results are appended after every test, so re-running this cell resumes where it stopped.
import csv, os, time
OUT2 = "/content/drive/MyDrive/nemotron_ft_plus_docs_results.csv"
# 200 and 300 clean examples first; then the original card B / card D settings (100 clean, 100 noisy).
PLAN = [("invoice_intake", 200, "clean", 2), ("invoice_intake", 300, "clean", 2),
        ("invoice_intake", 100, "clean", 2), ("invoice_intake", 100, "noisy", 2)]

def _done():
    if not os.path.exists(OUT2):
        return set()
    with open(OUT2, newline="", encoding="utf-8") as fh:
        return {(r["scenario"], r["method"], r["examples"], r["data"], r["epochs"]) for r in csv.DictReader(fh)}

def _save(row):
    new = not os.path.exists(OUT2)
    with open(OUT2, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=core.SWEEP_COLUMNS)
        if new:
            w.writeheader()
        w.writerow(row)

for key, n, data, epochs in PLAN:
    done = _done()
    need = [m for m in ("fine-tuned", "fine-tuned+docs") if (key, m, str(n), data, str(epochs)) not in done]
    if not need:
        continue
    scn = core.load_scenario(key)
    print(f"\n=== {key}: fine-tune on {n} {data} examples x {epochs} epoch(s)")
    t0 = time.time()
    model, losses = core.train(model, tok, scn, n_examples=n, data=data, epochs=epochs)
    minutes = round((time.time() - t0) / 60, 1)
    loss = round(sum(losses[-5:]) / len(losses[-5:]), 4)
    for m in need:
        res = core.evaluate(model, tok, scn, "prompt+docs" if m == "fine-tuned+docs" else "fine-tuned", n=100)
        _save(core._sweep_row(scn, res, m, n, data, epochs, minutes, loss))
        s = res["summary"]
        print(f"RESULT {key} | {m} | {n} {data} | {s['all fields correct %']}% ({s['95% range']})")
print("\nALL DONE")'''),
]


DEMO_CELLS = [
    ("md", """# Projector demo: chat with Nemotron before and after fine-tuning

Put this on the projector. It is a plain chat page on top of the model:

1. **Ask.** Type a message and Nemotron answers, as it was downloaded.
2. **Fine-tune.** Press *Fine-tune*, add the labelled files students sent back, and start. The progress shows on screen.
3. **Switch and ask again.** Switch the chat to the fine-tuned model and ask the same questions again.

**Getting labels from the class.** In the *Fine-tune* box, download the examples file and share it (for example as a Google Sheet). Students fill in the label columns using the company's rules and send the file back as CSV. Several files are fine; when two students label the same message, the more common label is used.

Fine-tuning on 100 examples takes about 9 to 13 minutes on a free T4.

*To rehearse without a GPU, on a laptop:* `python -m lab.demo --simulate` (answers are simulated)."""),

    ("md", """## 1. Setup

Runtime → Change runtime type → **T4 GPU**, then run:"""),
    ("code", f"""# Downloads the lab materials and installs two libraries (~1 minute)
REPO = "{REPO}"
BRANCH = "{BRANCH}"
import os, sys
if not os.path.exists("/content/lab-repo"):
    !git clone -q --depth 1 -b {{BRANCH}} {{REPO}} /content/lab-repo
os.chdir("/content/lab-repo/nemotron-lab")
!pip install -q bitsandbytes peft
sys.path.insert(0, ".")
from lab import core, demo
print("Ready.")"""),

    ("code", """# Loads NVIDIA Nemotron onto the GPU (~3 minutes)
model, tok = core.load_model()"""),

    ("md", """## 2. Start the chat

The next cell prints a link. Click it to open the chat in a new tab, and put that tab on the projector. The link only works in your own browser."""),

    ("code", """engine = demo.launch(model, tok)"""),

    ("md", """## 3. Keep the session alive

Leave this cell running during class and keep this browser tab open, so Colab does not treat the session as idle."""),

    ("code", """demo.keep_running(engine)"""),
]


def write(cells, out):
    nb_cells = []
    for kind, src in cells:
        lines = src.strip("\n").splitlines(keepends=True)
        if kind == "md":
            nb_cells.append({"cell_type": "markdown", "metadata": {}, "source": lines})
        else:
            nb_cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
                             "source": lines})
    nb = {"cells": nb_cells, "nbformat": 4, "nbformat_minor": 0,
          "metadata": {"accelerator": "GPU", "colab": {"provenance": [], "gpuType": "T4"},
                       "kernelspec": {"display_name": "Python 3", "name": "python3"},
                       "language_info": {"name": "python"}}}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {out} ({len(nb_cells)} cells)")


def main():
    write(CELLS, OUT)
    write(DRY_RUN_CELLS, OUT.parent / "instructor_dry_run.ipynb")
    write(DEMO_CELLS, OUT.parent / "projector_demo.ipynb")


if __name__ == "__main__":
    main()
