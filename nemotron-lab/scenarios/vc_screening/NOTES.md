# Design notes: VC pitch screening (draft)

Status: **dealbook draft only** (`policy.md`). There is no generator, data or `scenario.json` yet, so the lab does not load this scenario.

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

1. **How uneven the sector frequencies are.** If they are flat, the curve tops out early. If a few sectors dominate and many are rare (each roughly half as common as the one before), gains keep coming as the data grows.
2. **How many pitches sit near a boundary**: traction just under or over a bar, an exit at $45M vs $55M, a market next to a portfolio company's. More near-misses mean more examples are needed.

We tune both until the curve still rises clearly at about 6,300 examples (18 teams × 350 labels), first with a cheap stand-in classifier here and then for real on RCP.

## Prompt + docs baseline

The dealbook is about 1,700 words, around six times longer than the current one-page policies. Pasting it into every request makes each request several times more expensive than one to a fine-tuned model. We measure the actual token counts when the data exists and show them on the cost meter.

## Labelling in class

- A common pitch takes students about 30 seconds: steps 1–3, 5 and 9 on page 1.
- A rare one takes a minute or more: the thesis table, the portfolio appendix, the exited vs active check.
- These times are guesses until someone tries labelling 20 pitches with the dealbook open.

## Open questions for Manas and Rembrand

1. Are the rules realistic enough for an MBA room? A VC alum's read would help, especially Tables D and E.
2. Should step 4 (portfolio conflict) come before the thesis check, as now, or after? Before is stricter and easier to teach.
3. Is "weapons" right as an exclusion, given how much attention defense tech gets? It could be a good debate prompt either way.
4. Fund name and portfolio names are invented. Check none of them collide with a real fund or startup you care about.
