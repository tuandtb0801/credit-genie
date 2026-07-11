"""In-memory decision ledger, persisted to workspace/decisions/*.json as an audit trail.

Hackathon scope: no database, no hash-chaining — see docs/decision-modes-and-controls.md
section 6 ("Show in architecture but skip implementation"). Records are still immutable
once written: nothing in this module updates or deletes a saved decision.
"""

import itertools
import json
from datetime import date
from typing import Any

from app.config import DECISIONS_ROOT
from app.models import DecisionRecord


def _load_persisted_decisions() -> list[DecisionRecord]:
    """Rehydrate the ledger from disk so the audit trail survives server restarts."""
    records = []
    for path in sorted(DECISIONS_ROOT.glob("d-*.json")):
        try:
            records.append(DecisionRecord.model_validate_json(path.read_text()))
        except (ValueError, json.JSONDecodeError):
            continue  # skip corrupt/foreign files rather than refuse to start
    records.sort(key=lambda r: r.created_at)
    return records


def _resume_sequence(records: list[DecisionRecord], today: date) -> itertools.count:
    """Continue today's decision-id sequence past what's already on disk."""
    prefix = f"d-{today.isoformat()}-"
    max_seq = 0
    for record in records:
        if record.decision_id.startswith(prefix):
            try:
                max_seq = max(max_seq, int(record.decision_id.rsplit("-", 1)[-1]))
            except ValueError:
                continue
    return itertools.count(max_seq + 1)


_ledger: list[DecisionRecord] = _load_persisted_decisions()
_sequence_date = date.today()
_daily_sequence = _resume_sequence(_ledger, _sequence_date)


def _next_decision_id() -> str:
    global _sequence_date, _daily_sequence
    today = date.today()
    if today != _sequence_date:
        _sequence_date = today
        _daily_sequence = itertools.count(1)
    return f"d-{today.isoformat()}-{next(_daily_sequence):03d}"


def new_decision_id() -> str:
    return _next_decision_id()


def save_decision(record: DecisionRecord) -> DecisionRecord:
    _ledger.append(record)
    DECISIONS_ROOT.mkdir(parents=True, exist_ok=True)
    path = DECISIONS_ROOT / f"{record.decision_id}.json"
    path.write_text(record.model_dump_json(indent=2))
    return record


def list_decisions(applicant_id: str | None = None) -> list[DecisionRecord]:
    if applicant_id is None:
        return list(_ledger)
    return [d for d in _ledger if d.applicant_id == applicant_id]


def get_decision(decision_id: str) -> DecisionRecord | None:
    return next((d for d in _ledger if d.decision_id == decision_id), None)


def latest_decision_for(applicant_id: str) -> DecisionRecord | None:
    matches = list_decisions(applicant_id)
    return matches[-1] if matches else None


def decision_lookup_by_applicant() -> dict[str, dict[str, Any]]:
    """Most recent decision lineage per applicant, keyed for policy.simulate_policy_change."""
    lookup: dict[str, dict[str, Any]] = {}
    for record in _ledger:
        lookup[record.applicant_id] = record.lineage.model_dump()
    return lookup
