# Pre-read: How do you bring your data to a model?

*About 15 minutes. Read before class. You will fine-tune a real AI model in class, so no coding background is needed, but this note is.*

---

## 1. The problem: a brilliant new hire who knows nothing about your company

A frontier AI model is like a brilliant new hire from a top MBA program. It writes well, reasons well, and knows a lot about the world. But on day one it doesn't know:

- that your **Platinum** customers jump the queue,
- that invoices over **$10,000** need the CFO,
- that your best underwriter gets nervous when a policy is **less than 30 days old**.

None of that is on the internet. It lives in your policy documents, your systems, and, most valuable of all, in the heads of your best people.

So the core question of this session is: **how do you get your company's data and judgment into the model?**

## 2. Three ways to bring data to a model

| | **Prompting** | **RAG** (retrieval-augmented generation) | **Fine-tuning** |
|---|---|---|---|
| **The new-hire analogy** | Hand them a sticky note with instructions every time | Give them a search box over the company wiki | Train them for three months alongside your best expert |
| **How it works** | You write the instructions (and maybe a few examples) into each request | A system finds the relevant documents and pastes them into the request automatically | You show the model hundreds or thousands of *input → expert answer* examples and update its internal weights |
| **Where the knowledge lives** | In the prompt | In a document store, and in the prompt at question time | **In the model itself** |
| **Best for** | Quick start, general tasks | Facts that change often, large document collections, citing sources | A *repeatable judgment* or format applied the same way thousands of times |
| **Weak spot** | Long rules get ignored; every request pays for the long prompt | Only as good as what it retrieves; can't capture judgment nobody wrote down | Needs good labeled data; must be retrained when the rules change |

These aren't mutually exclusive. Many real systems fine-tune a model *and* use RAG for up-to-date facts.

<details>
<summary><b>Quick check:</b> Your company's product catalog changes every week. Prompting, RAG or fine-tuning? (click to reveal)</summary>

**RAG.** Facts that change often belong in a document store the model can look up. Fine-tuning them in would mean retraining every week.
</details>

<details>
<summary><b>Quick check:</b> You want 50,000 insurance claims a day routed exactly the way your best claims manager would. Which one?</summary>

**Fine-tuning** is the strongest candidate: a narrow, high-volume, repeatable judgment with a clear right answer and lots of historical examples. You would still test it against prompting and RAG, which is exactly what you'll do in class.
</details>

## 3. What fine-tuning actually does

A language model is a very large set of numbers (*weights*); Nemotron Nano 4B has about 4 billion of them. Training nudges those numbers so the model's answers move closer to the examples it is shown.

The vocabulary you'll see in the lab:

- **Training example:** one input plus the expert's correct output. For example, a complaint email → `{"priority": "P1", "route_to": "accessibility_desk", ...}`.
- **Loss:** how "surprised" the model is by the expert's answer. Training pushes it down.
- **Epoch:** one pass through all the training examples.
- **Overfitting:** memorizing the training examples instead of learning the rule. This is why we always test on **held-out** examples the model never saw.
- **LoRA (low-rank adaptation):** instead of changing all 4 billion weights, train small add-on "adapter" layers (under 1% of the size). This is why you can fine-tune on a free GPU in minutes.
- **4-bit quantization:** storing each weight in 4 bits instead of 16, so the model fits on a small GPU.

### Fine-tuning and determinism

Business processes need **consistency**: the same claim should get the same decision on Monday and on Friday. Two different things contribute to that:

1. **Deterministic decoding:** setting the model to always pick its single most likely answer ("temperature 0"), so the same input always gives the same output. It's easy, but it only makes the model *consistently* whatever it already is, which may be consistently wrong.
2. **Fine-tuning:** changing *what* the model's most likely answer is, so it's consistently the answer your expert would give, in exactly the format your systems expect.

Prompting asks the model to follow your rules. Fine-tuning makes following them its default behavior.

<details>
<summary><b>Quick check:</b> A model gives the same wrong answer every time you ask. Is it deterministic? Is it useful?</summary>

It is deterministic, but not useful. Consistency is only valuable when it is consistently *right*. That's the gap fine-tuning is meant to close.
</details>

## 4. Open-weight vs. closed-weight models

| | **Closed-weight** (e.g. GPT, Claude, Gemini) | **Open-weight** (e.g. NVIDIA Nemotron, Llama, Qwen, Mistral) |
|---|---|---|
| **Access** | Through the vendor's API; you never see the weights | Download the weights and run them anywhere |
| **Capability** | Usually the most capable general models | Often smaller; can match or beat frontier models on a *narrow* task once fine-tuned |
| **Customization** | Prompting, RAG, and fine-tuning only where the vendor offers it | Full control: fine-tune any way you like |
| **Data & privacy** | Your data is sent to the vendor | Can run entirely on your own servers |
| **Cost** | Pay per token, on every request | Pay for your own hardware; small models are cheap to run at scale |
| **Who owns the result** | The vendor owns the model | You own your fine-tuned weights |

In class you'll use **NVIDIA Llama-3.1-Nemotron-Nano-4B**, an open-weight model from NVIDIA's Nemotron family, small enough to fine-tune on a free Google Colab GPU.

## 5. Case in point: replicating expert judgment in finance

In June 2026, **Bridgewater's AIA Labs and Thinking Machines Lab** published *[Learning to Replicate Expert Judgment in Financial Tasks](https://thinkingmachines.ai/news/learning-to-replicate-expert-judgment-in-financial-tasks/)*. The task was filtering and processing financial documents to surface information relevant to investment decisions, the kind of judgment an experienced investment analyst makes all day.

What they did, in short:

- collected **examples labeled by Bridgewater's investment experts**,
- **fine-tuned an open-weight model** (Qwen) using Thinking Machines' fine-tuning service, Tinker,
- compared it to frontier models used through prompting.

The custom model **outperformed the frontier models on these tasks, at a fraction of the cost to run**. The authors' central insight is the reason this session exists:

> Investor judgment contains a large amount of tacit pattern recognition that is hard to express in a prompt, but easier to transmit through carefully labeled examples.

Read the original post before class if you can; it's about a 14-minute read.

### Where does expert data come from?

If labeled examples are the asset, someone has to produce them. A fast-growing industry does exactly that. Companies such as **Mercor** recruit domain experts (former bankers, lawyers, doctors, consultants) to write and grade the examples that AI labs use to train and evaluate models. Inside a company, the equivalent source is your own historical decisions and your best employees' time.

Keep a question in mind for class: **is your company's labeled data a strategic asset? Who owns it, and how clean is it?**

## 6. What you'll do in class

You'll work in teams on one of five business processes: airline complaint triage, accounts-payable invoice intake, insurance claims routing, expense-policy audit, or B2B sales-lead qualification. Each one comes with a short case, a policy document, and 600 expert-labeled examples. You will:

1. test Nemotron with **prompting only**,
2. test it with the **policy document pasted in** (what RAG automates),
3. **fine-tune it** on expert-labeled examples, choosing how many and how clean,
4. compare all three on 40 held-out cases, then try to break your model.

## 7. Before class (5 minutes)

- [ ] Make sure you can sign in to **Google Colab** (colab.research.google.com) with a Google account.
- [ ] Open the lab notebook link your instructor sent and check that **Runtime → Change runtime type → T4 GPU** is available.
- [ ] Bring a laptop and charger. A phone won't work.

## Glossary

| Term | Meaning |
|---|---|
| **Weights** | The numbers inside a model that determine its behavior |
| **Open-weight** | A model whose weights are published for anyone to download and modify |
| **Prompt** | The text instructions and context sent to the model with each request |
| **Token** | A chunk of text (~¾ of a word); the unit models read and are billed by |
| **RAG** | Retrieval-augmented generation: automatically finding relevant documents and adding them to the prompt |
| **Fine-tuning** | Further training a model on your own examples so it changes its default behavior |
| **LoRA** | A cheap fine-tuning method that trains small adapter layers instead of the whole model |
| **Held-out test set** | Examples kept aside and never trained on, used to measure real performance |
| **Labeled data** | Inputs paired with the correct (expert) answer |
