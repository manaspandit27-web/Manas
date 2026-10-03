"""Builds notebooks/finetune_lab.ipynb from the cells below (edit here, then re-run).

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

You will try the three ways to bring company knowledge to a model, on the same 40 test cases:

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

Same 40 test cases. None of them were in the training data."""),

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


def main():
    cells = []
    for kind, src in CELLS:
        lines = src.strip("\n").splitlines(keepends=True)
        if kind == "md":
            cells.append({"cell_type": "markdown", "metadata": {}, "source": lines})
        else:
            cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": lines})
    nb = {"cells": cells, "nbformat": 4, "nbformat_minor": 0,
          "metadata": {"accelerator": "GPU", "colab": {"provenance": [], "gpuType": "T4"},
                       "kernelspec": {"display_name": "Python 3", "name": "python3"},
                       "language_info": {"name": "python"}}}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {OUT} ({len(cells)} cells)")


if __name__ == "__main__":
    main()
