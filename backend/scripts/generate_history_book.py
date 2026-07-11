"""Generate the synthetic historic-outcomes book (hint data category 4).

Run once from backend/: .venv/bin/python3 scripts/generate_history_book.py

Produces workspace/history/historic_outcomes.json: ~1000 past applicants with the same
flat-evidence feature shape the scoring engine uses, a historic decision, and a realized
outcome (default / no_default). Default probability is *correlated with the risk features*
(DTI, delinquency, utilization) via the engine's own deterministic anchors plus noise, so
calibration curves are meaningful — but this is synthetic omniscience used only to
demonstrate calibration/back-test logic, never model quality.
"""

import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tools import scoring  # noqa: E402
from app.tools.policy import get_active_policy, get_segment_config  # noqa: E402

SEED = 42
BOOK_SIZE = 1000
LGD = 0.45  # loss-given-default assumption used by the back-test

OUT_PATH = Path(__file__).resolve().parent.parent / "workspace" / "history" / "historic_outcomes.json"


def band_for(score: int) -> str:
    if score < 600:
        return "poor"
    if score < 660:
        return "fair"
    if score < 720:
        return "good"
    return "excellent"


def sample_max_dpd(rng: random.Random) -> int:
    roll = rng.random()
    if roll < 0.70:
        return 0
    if roll < 0.85:
        return rng.randint(1, 29)
    if roll < 0.93:
        return rng.randint(30, 59)
    if roll < 0.97:
        return rng.randint(60, 89)
    return rng.randint(90, 150)


def generate_record(rng: random.Random, idx: int, segment_cfg: dict) -> dict:
    credit_score = int(min(820, max(500, rng.gauss(680, 60))))
    monthly_income = round(rng.lognormvariate(8.35, 0.35), -1)  # ~2500-12000, median ~4200
    dti = min(0.85, max(0.02, rng.betavariate(2.5, 4.5) * 1.1))
    monthly_obligations = round(monthly_income * dti)
    utilization = round(min(1.0, max(0.0, rng.betavariate(2, 3.2))), 2)
    max_dpd = sample_max_dpd(rng)

    features = {
        "credit_score": credit_score,
        "score_band": band_for(credit_score),
        "credit_history_months": max(2, int(rng.lognormvariate(3.6, 0.7))),
        "monthly_income": monthly_income,
        "monthly_obligations": monthly_obligations,
        "dti_ratio": round(monthly_obligations / monthly_income, 4),
        "bnpl_active_count": min(7, int(rng.expovariate(0.7))),
        "utilization_ratio": utilization,
        "total_exposure": round(monthly_income * rng.uniform(1.0, 4.0), -2),
        "max_dpd": max_dpd,
    }

    # Default probability from the engine's own deterministic anchors + band effect + noise,
    # so predicted risk and realized outcomes correlate (that's what calibration measures).
    dti_anchor = scoring.compute_dti(monthly_income, monthly_obligations, segment_cfg["affordability"]["dti_decline_ceiling"])
    risk_anchor = scoring.compute_risk_anchor(max_dpd, utilization)
    blended = 0.5 * dti_anchor["suggested_score"] + 0.5 * risk_anchor["suggested_score"]
    band_bump = {"poor": 0.10, "fair": 0.04, "good": 0.0, "excellent": -0.03}[features["score_band"]]
    p_default = min(0.90, max(0.01, 0.50 - 0.55 * blended + band_bump + rng.gauss(0, 0.03)))

    return {
        "applicant_id": f"h-{idx:04d}",
        "features": features,
        "decision": "APPROVE",  # book = historically booked loans; outcomes observed on these
        "outcome": "default" if rng.random() < p_default else "no_default",
        "p_default_true": round(p_default, 4),
    }


def main() -> None:
    rng = random.Random(SEED)
    policy = get_active_policy()
    segment_cfg = get_segment_config(policy, "personal_loan")

    records = [generate_record(rng, i + 1, segment_cfg) for i in range(BOOK_SIZE)]
    base_rate = sum(r["outcome"] == "default" for r in records) / len(records)

    book = {
        "meta": {
            "seed": SEED,
            "size": BOOK_SIZE,
            "lgd": LGD,
            "base_default_rate": round(base_rate, 4),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "caveat": "Synthetic outcomes generated with feature-correlated probabilities — demonstrates calibration/back-test logic only, not model quality.",
        },
        "records": records,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(book, indent=1))
    print(f"Wrote {BOOK_SIZE} records to {OUT_PATH} (base default rate {base_rate:.1%})")


if __name__ == "__main__":
    main()
