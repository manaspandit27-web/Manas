"""The VC screening scenario: the labeller follows the dealbook, and the data matches the labeller.

Run from nemotron-lab/:  python -m pytest -q tests
"""

import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import vc_pitches as vc  # noqa: E402
from lab import core  # noqa: E402

F = vc.Facts
REASON_DECISION = {
    "stage_or_size": "pass", "geography": "pass", "excluded_sector": "pass", "portfolio_conflict": "pass",
    "outside_thesis": "pass", "thesis_requirement_missing": "pass", "insufficient_traction": "pass",
    "repeat_founder": "meeting", "thesis_fit": "meeting", "portfolio_intro": "meeting",
    "repeat_founder_exit": "fast_track", "strong_traction": "fast_track",
}


# The five worked examples at the end of policy.md.
@pytest.mark.parametrize("facts, expected", [
    (F("seed", 3.5, "Austin", "butcher_inventory", True, traction=210_000), ("meeting", "thesis_fit")),
    (F("Series A", 12, "Toronto", "vet_scribe", True, traction=2_400_000), ("pass", "portfolio_conflict")),
    (F("pre-seed", 1, "London", "api_testing", True), ("pass", "geography")),
    (F("seed", 4, "Boston", "cardiac_implant", False, exit_kind="cofounder", exit_value_m=120),
     ("meeting", "repeat_founder")),
    (F("seed", 2.5, "Chicago", "restaurant_ap", True, traction=80_000, intro="portfolio", intro_company="Pennywhistle"),
     ("meeting", "portfolio_intro")),
])
def test_dealbook_worked_examples(facts, expected):
    assert vc.screen(facts) == expected


def test_dealbook_edges():
    base = dict(stage="seed", amount_m=3, city="Boston", market="api_testing", must_have=True, traction=200_000)
    assert vc.screen(F(**base)) == ("meeting", "thesis_fit")
    assert vc.screen(F(**{**base, "amount_m": 7})) == ("pass", "stage_or_size")        # fits Series A, not seed
    assert vc.screen(F(**{**base, "stage": "Series B", "amount_m": 30})) == ("pass", "stage_or_size")
    assert vc.screen(F(**{**base, "city": "Dublin"})) == ("pass", "geography")         # UK/IE: Series A only
    assert vc.screen(F(**{**base, "city": "Dublin", "stage": "Series A", "amount_m": 8, "traction": 1_200_000})) \
        == ("meeting", "thesis_fit")
    assert vc.screen(F(**{**base, "exit_kind": "cofounder", "exit_value_m": 50})) == ("fast_track", "repeat_founder_exit")
    assert vc.screen(F(**{**base, "exit_kind": "cofounder", "exit_value_m": 48})) == ("meeting", "thesis_fit")
    assert vc.screen(F(**{**base, "exit_kind": "employee", "exit_value_m": 900})) == ("meeting", "thesis_fit")
    assert vc.screen(F(**{**base, "traction": 450_000})) == ("fast_track", "strong_traction")
    assert vc.screen(F(**{**base, "traction": 90_000})) == ("pass", "insufficient_traction")
    assert vc.screen(F(**{**base, "traction": 90_000, "intro": "other"})) == ("pass", "insufficient_traction")
    assert vc.screen(F(**{**base, "stage": "pre-seed", "amount_m": 1, "traction": 0})) == ("meeting", "thesis_fit")
    assert vc.screen(F(**{**base, "market": "bakery_inventory"})) == ("meeting", "thesis_fit")    # Crumbline exited
    assert vc.screen(F(**{**base, "market": "timeseries_db"})) == ("pass", "portfolio_conflict")  # Querylane active
    assert vc.screen(F(**{**base, "market": "drug_discovery"})) == ("pass", "outside_thesis")
    assert vc.screen(F(**{**base, "market": "cannabis"})) == ("pass", "excluded_sector")


def test_every_portfolio_company_has_a_market():
    in_markets = {m.portfolio for m in vc.MARKETS if m.portfolio}
    assert in_markets == set(vc.PORTFOLIO_STATUS)
    policy = (ROOT / "scenarios" / "vc_screening" / "policy.md").read_text()
    for name, status in vc.PORTFOLIO_STATUS.items():
        row = next(line for line in policy.splitlines() if line.startswith(f"| {name} |"))
        assert ("Active" in row) == (status == "active"), name


def test_generator_is_deterministic():
    a = [vc.generate(random.Random(7))[:2] for _ in range(3)]
    b = [vc.generate(random.Random(7))[:2] for _ in range(3)]
    assert a == b


def test_data_matches_dealbook():
    scn = core.load_scenario("vc_screening")
    for row in scn.train + scn.test:
        assert REASON_DECISION[row["reason"]] == row["decision"], row["id"]
    reasons = {r["reason"] for r in scn.train}
    assert reasons == set(REASON_DECISION)
    # rare reasons stay rare, but appear often enough to learn from the full pool
    counts = {k: sum(r["reason"] == k for r in scn.train) for k in REASON_DECISION}
    assert min(counts.values()) >= 50
    assert max(counts.values()) < 0.25 * len(scn.train)
