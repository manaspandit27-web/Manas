# Activity walkthrough: what the instructor does and what students do

The instructor runs everything, on the projector. Students don't install or run anything: they label examples, and the model is fine-tuned on their labels in front of them.

The timings are a suggestion and have not been rehearsed with a class. As of 3 October 2026 the flow has been run in Colab with simulated answers, but not yet with the real model on a GPU.

## Before class

**Instructor**

1. Pick one company, for example Skyward Airways (`airline_complaints`). Avoid `invoice_intake`: the dry run showed it needs about 300 examples.
2. Take `scenarios/airline_complaints/examples_to_label.csv` from this repo. It has 100 customer messages with four empty columns: `category`, `priority`, `route_to`, `compensation`.
3. Put it in a Google Sheet and decide who labels which rows.
4. Prepare the rules handout: `scenarios/airline_complaints/policy.md`, one page.
5. Shortly before class, open [`notebooks/projector_demo.ipynb`](../notebooks/projector_demo.ipynb) in Colab on a T4 GPU and run the first four cells: setup, company, load the model (about 3 minutes), start the chat. The last one prints the chat's address. Open it in a new tab.

**Students**

- Optionally read the pre-read. Bring a laptop or tablet.

## In class

| Step | Instructor | Students |
|---|---|---|
| **1. Framing** (about 10 min) | Introduces prompting, RAG and fine-tuning. | Listen. |
| **2. Ask the original model** (about 8 min) | Puts the chat on the projector. It opens with the instruction the model is given and the model's reply. Types three to five customer messages, or clicks the starter ones. | With the rules in hand, say what the answer should be for each message, then see what the model answered. It is mostly wrong. |
| **3. Label** (about 12 min) | Shares the Google Sheet and the rules. When they finish, downloads the sheet as CSV (File → Download → CSV). | Open the sheet and go to their rows. For each message, read it, apply the rules, and type a value in each of the four columns. |
| **4. Fine-tune** (about 12 min) | Switches the projector to the Colab notebook. Runs the cell that loads the CSV, which prints how many labelled examples it read and shows them as a table. Runs the fine-tuning cell, which shows a live progress bar and then the loss curve. Leads discussion while it trains. | Watch the code run on their own labels. Discuss. |
| **5. Switch and ask again** (about 8 min) | Runs the last cell, `chat.serve("fine-tuned")`. Goes back to the chat tab and presses **Ask the same questions again**. | Compare the new answers with the earlier ones and with the rules. |
| **6. Debrief** (about 10 min) | Runs the debrief questions and the takeaway (see the [instructor guide](INSTRUCTOR-GUIDE.md)). | Discuss. |

## The three notebook cells the class sees

```python
# The examples the class labelled: choose the CSV file (or files) the students sent back
from google.colab import files
labelled = chat.read_labelled(files.upload())
pd.DataFrame(labelled).head(10)
```

```python
# Fine-tune Nemotron on those examples.
# LoRA training: about 1% of the model's weights are trained, the rest stay as downloaded.
losses = chat.finetune(labelled, epochs=2)
core.plot_loss(losses)
```

```python
chat.serve("fine-tuned")   # chat.serve("original") switches back
```

## What a student does for one message

Message: *"The stroller we gate-checked on SK1048 (Miami to Phoenix) came back bent and unusable."*

| Column | They type | Why, from the rules |
|---|---|---|
| category | `baggage` | Damaged baggage, which includes strollers |
| priority | `P3` | Not Platinum or Gold, not a cancellation, no long delay |
| route_to | `baggage_services` | Baggage complaints go to that team |
| compensation | `none` | Baggage is compensated through the claim process, not here |

## Things to know

- **Comparing answers is by eye.** The chat does not mark answers right or wrong. For a number, use the dry run: on Skyward, the original model got 7% of test cases fully right and a model fine-tuned on 100 clean examples got 73% (see [`dry-run-2026-10-03/`](dry-run-2026-10-03/README.md)).
- **Labels are typed freely.** Capitals, spaces and hyphens are forgiven, but a misspelled value means that row is skipped. The notebook says how many rows it skipped.
- **One label per message.** In a shared sheet each message is labelled once, so nobody checks a student's mistake. If several files cover the same message, the more common label is used.
- **The chat can't answer during fine-tuning.** One GPU does both jobs. The chat page says so while the model is training.
- **The GPU is the risk.** Free Colab GPUs are not guaranteed, and the free tier cut ours off after about 5.5 hours of use. Have Colab Pro or pay-as-you-go ready for class, and do a full real run beforehand.
