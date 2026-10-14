"""Cheap check of the VC scenario's learning-curve shape, before spending GPU time (maintainers only).

Two stand-in learners, neither of them the LLM:
  facts - a decision tree on the hidden facts behind each pitch. It reads perfectly, so it shows how many
          examples it takes to learn the dealbook's rules alone.
  text  - TF-IDF + logistic regression on the pitch text. It has no idea what numbers mean, so it shows
          how far surface word patterns get.
The real curve comes from fine-tuning Nemotron on RCP; this only tells us whether the generator settings
(vc_pitches.SECTOR_SKEW, NEAR_MISS) leave room to improve at a few thousand examples.

Usage (from nemotron-lab/):  pip install scikit-learn && python scripts/vc_learning_curve.py
"""

import random
import sys
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate_data  # noqa: E402
import vc_pitches as vc  # noqa: E402

SIZES = [100, 200, 350, 700, 1500, 3000, 6300]
SEEDS = [0, 1, 2]


def rows_with_facts():
    """Rebuild the vc_screening rows exactly as generate_data.build does, keeping the facts."""
    seed = 1000 + list(generate_data.GENERATORS).index("vc_screening")
    n_train, n_test = generate_data.SIZES["vc_screening"]
    r = random.Random(seed)
    seen, rows = set(), []
    while len(rows) < n_train + n_test:
        text, labels, facts = vc.generate(r)
        if text in seen:
            continue
        seen.add(text)
        rows.append((text, labels["reason"], facts))
    return rows[:n_train], rows[n_train:]


def fact_features(f):
    m = vc.MARKET[f.market]
    one_hot = {
        "stage": ["pre-seed", "seed", "Series A", "Series B"], "region": ["us_ca", "uk_ie", "other"],
        "sector": sorted({x.sector for x in vc.MARKETS}), "market": [x.key for x in vc.MARKETS],
        "model": list(vc.BARS), "exit": ["none", "cofounder", "employee", "shutdown"], "intro": ["none", "portfolio", "other"],
    }
    vals = {"stage": f.stage, "region": vc.region(f.city), "sector": m.sector, "market": f.market, "model": m.model,
            "exit": f.exit_kind, "intro": f.intro}
    x = [float(vals[k] == v) for k, opts in one_hot.items() for v in opts]
    return x + [f.amount_m, float(f.must_have), float(f.exit_value_m), f.traction]


def main():
    train, test = rows_with_facts()
    y_test = [t[1] for t in test]
    Xf_train = np.array([fact_features(t[2]) for t in train])
    Xf_test = np.array([fact_features(t[2]) for t in test])
    vec = TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)
    vec.fit([t[0] for t in train])
    Xt_train, Xt_test = vec.transform([t[0] for t in train]), vec.transform([t[0] for t in test])

    print(f"test cases: {len(test)}; accuracy on the reason code (it fixes the decision), mean of {len(SEEDS)} samples\n")
    print(f"{'examples':>8} {'facts tree':>11} {'text tf-idf':>12}")
    for n in SIZES:
        acc_f, acc_t = [], []
        for s in SEEDS:
            idx = random.Random(s).sample(range(len(train)), n)
            y = [train[i][1] for i in idx]
            tree = DecisionTreeClassifier(random_state=s).fit(Xf_train[idx], y)
            acc_f.append(np.mean(tree.predict(Xf_test) == np.array(y_test)))
            lr = LogisticRegression(max_iter=2000, C=10).fit(Xt_train[idx], y)
            acc_t.append(np.mean(lr.predict(Xt_test) == np.array(y_test)))
        print(f"{n:>8} {100 * np.mean(acc_f):>10.1f}% {100 * np.mean(acc_t):>11.1f}%")


if __name__ == "__main__":
    main()
