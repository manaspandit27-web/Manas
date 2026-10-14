# Design notes: VC pitch screening (draft)

Status: **draft, with data.** The dealbook is `policy.md`. Pitches come from `scripts/vc_pitches.py`, whose `screen()` function applies the dealbook step by step and labels every pitch. The lab loads the scenario like the other five, but the instructor dry run leaves it out: it gets its own sweep on RCP.

| File | What it is |
|---|---|
| `train.csv` | 7,000 labelled pitches: the pool teams buy from or label (18 teams × 350 = 6,300, plus spare) |
| `train_noisy.csv` | The same pitches, 30% with one wrong label |
| `test.csv` | 500 held-out pitches; with 500, a score's 95% range is about ±4 points |
| `examples_to_label.csv` | 100 pitches with blank labels, chosen so every reason code appears |

Rebuild with `python scripts/generate_data.py` (the other five scenarios come out unchanged). `tests/test_vc_pitches.py` checks `screen()` against the dealbook's worked examples and edge cases, and the data against `screen()`.

## The task

Read a one-paragraph pitch and answer with two fields:

- `decision`: `pass`, `meeting` or `fast_track`
- `reason`: one of 12 codes, listed in the steps table of `policy.md`

The reason fixes the decision. Scoring both fields catches a model that writes a valid-looking pair that the dealbook never produces.

Ground truth is the dealbook applied to the facts stated in the pitch. The generator will pick hidden facts (stage, round size, HQ, sector, market, founder history, must-have met or not, business model, traction, intro source), write a pitch that states them, and label it by running the 11 steps in order.

## Why it should keep improving past a few hundred examples

| Layer | What the model must learn | How often it matters (set by the generator) |
|---|---|---|
| Common path | Steps 1, 5, 9 and 11, with the seed and Series A bars for B2B software | Most pitches: learned early |
| Thesis must-haves | 16 sector-specific rules (Table D) | Each sector's share is a generator setting; rare sectors give the tail |
| Portfolio conflicts | 24 active markets, 6 exited ones that must *not* block, and neighbouring markets that don't count | A few percent of pitches each: the slowest part to learn |
| Rule interactions | UK and Ireland at Series A only; rounds outside their own stage's range; a qualifying exit overriding a missing must-have (6a); the $50M exit cutoff; pre-seed having no bar; portfolio intros vs other intros | Rare by design |

Two settings control the shape of the learning curve:

1. **How uneven the sector frequencies are.** If they are flat, the curve tops out early. If a few sectors dominate and many are rare (now the *k*-th most common sector is 1/*k* as common as the top one), gains keep coming as the data grows.
2. **How many pitches sit near a boundary**: traction just under or over a bar, an exit at $45M vs $55M, a market next to a portfolio company's. More near-misses mean more examples are needed.

We tune both until the curve still rises clearly at about 6,300 examples (18 teams × 350 labels), first with cheap stand-in learners and then for real on RCP.

### First check: stand-in learners (`python scripts/vc_learning_curve.py`)

Accuracy on the reason code over the 500 test pitches, mean of 3 random samples per size. Current settings: `SECTOR_SKEW = 1.0`, `NEAR_MISS = 0.35`.

| Training examples | Decision tree on the hidden facts | TF-IDF + logistic regression on the text |
|---|---|---|
| 100 | 51% | 25% |
| 200 | 61% | 27% |
| 350 | 64% | 34% |
| 700 | 73% | 39% |
| 1,500 | 82% | 50% |
| 3,000 | 89% | 59% |
| 6,300 | 94% | 68% |

- **The shape is what we want.** Both keep rising through 6,300 with no plateau, gaining about 7–10 points each time the data doubles. The fact-level learner gets close to perfect only at full class volume.
- **Neither is the LLM.** The tree reads the facts perfectly, so it shows only how hard the rules are. TF-IDF can't compare numbers, so it understates what a model that reads can do. Nemotron should start higher than TF-IDF, because it understands "pre-revenue" or "$1.2M ARR" without training. Whether it keeps rising like the tree is exactly what the RCP sweep has to show.
- **If the real curve tops out too early,** raise `SECTOR_SKEW` (rarer sectors) or `NEAR_MISS` (more borderline cases) and regenerate. If it starts too low to be fun, lower them.

## Prompt + docs baseline

The dealbook is about 1,700 words, around six times longer than the current one-page policies. Pasting it into every request makes each request several times more expensive than one to a fine-tuned model. We measure the actual token counts with the Nemotron tokenizer and show them on the cost meter.

## Labelling in class

- A common pitch takes students about 30 seconds: steps 1–3, 5 and 9 on page 1.
- A rare one takes a minute or more: the thesis table, the portfolio appendix, the exited vs active check.
- These times are guesses until someone tries labelling 20 pitches with the dealbook open.

## Open questions for Manas and Rembrand

1. Are the rules realistic enough for an MBA room? A VC alum's read would help, especially Tables D and E.
2. Should step 4 (portfolio conflict) come before the thesis check, as now, or after? Before is stricter and easier to teach.
3. Is "weapons" right as an exclusion, given how much attention defense tech gets? It could be a good debate prompt either way.
4. Fund name and portfolio names are invented. Check none of them collide with a real fund or startup you care about.
