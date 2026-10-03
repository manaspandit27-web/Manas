# Granite Shield — Auto FNOL Routing Rules (internal)

**Claim type** — `collision`, `theft` (vehicle stolen), `glass` (windshield/window only), `weather` (hail, flood, falling tree), `vandalism` (keying, slashed tires, graffiti).

**Injury** — `yes` if anyone (insured, passenger, other driver) was hurt or received medical care; otherwise `no`.

**Estimate band** — repair estimate, or vehicle value for thefts: `under_2k` (< $2,000), `2k_to_10k` ($2,000 – $10,000), `over_10k` (> $10,000).

**Route** (first match wins)
1. `special_investigations` (SIU) if the policy started **less than 30 days** before the loss, **or** it is a **theft reported more than 7 days** after it happened.
2. `senior_adjuster` if there is **any injury**.
3. `fast_track` if it is a `glass` claim **or** the estimate is `under_2k` — paid same-day, no adjuster.
4. `standard_adjuster` otherwise.
