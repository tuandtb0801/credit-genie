import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from app.bnpl import decide_bnpl
from app.models import BnplReasoningAssessment


def assessment(*, confidence: float = 0.9) -> BnplReasoningAssessment:
    return BnplReasoningAssessment(
        affordability="adequate",
        risk="low",
        confidence=confidence,
        evidence_refs=["income.monthly_income"],
        flags=[] if confidence >= 0.6 else ["insufficient confidence"],
        reasoning="Evidence supports the deterministic affordability and risk anchors.",
    )


class DecideBnplTests(unittest.IsolatedAsyncioTestCase):
    async def _decide(self, applicant_id: str, agent_result: BnplReasoningAssessment):
        with (
            patch("app.bnpl._run_bnpl_reasoning", new=AsyncMock(return_value=agent_result)),
            patch("app.bnpl.new_decision_id", return_value="d-test-001"),
            patch("app.bnpl.save_decision", side_effect=lambda record: record),
        ):
            return await decide_bnpl(applicant_id)

    async def test_successful_agent_reasoning_is_recorded_and_allows_scoring(self):
        record = await self._decide("sarah-chen", assessment())

        self.assertEqual(record.outcome, "APPROVE")
        self.assertEqual(record.lineage.agent_reasoning_status, "completed")
        self.assertEqual(record.lineage.bnpl_reasoning_assessment["confidence"], 0.9)
        self.assertEqual(record.lineage.agent_messages[0].from_agent, "bnpl")
        self.assertIn("agent_reasoning", record.lineage.timing_ms)

    async def test_low_confidence_agent_forces_refer(self):
        record = await self._decide("sarah-chen", assessment(confidence=0.4))

        self.assertEqual(record.outcome, "REFER")
        self.assertEqual(record.reason_code, "AGENT_LOW_CONFIDENCE")
        self.assertIsNone(record.lineage.final_score)

    async def test_agent_timeout_cannot_auto_approve(self):
        async def slow_agent(_payload):
            await asyncio.sleep(0.02)
            return assessment()

        with (
            patch("app.bnpl.BNPL_AGENT_TIMEOUT_MS", 1),
            patch("app.bnpl._run_bnpl_reasoning", side_effect=slow_agent),
            patch("app.bnpl.new_decision_id", return_value="d-test-002"),
            patch("app.bnpl.save_decision", side_effect=lambda record: record),
        ):
            record = await decide_bnpl("sarah-chen")

        self.assertEqual(record.outcome, "REFER")
        self.assertEqual(record.reason_code, "AGENT_REASONING_UNAVAILABLE")
        self.assertEqual(record.lineage.agent_reasoning_status, "timeout")

    async def test_hard_rule_remains_binding_when_agent_times_out(self):
        async def slow_agent(_payload):
            await asyncio.sleep(0.02)
            return assessment()

        with (
            patch("app.bnpl.BNPL_AGENT_TIMEOUT_MS", 1),
            patch("app.bnpl._run_bnpl_reasoning", side_effect=slow_agent),
            patch("app.bnpl.new_decision_id", return_value="d-test-003"),
            patch("app.bnpl.save_decision", side_effect=lambda record: record),
        ):
            record = await decide_bnpl("maria-santos")

        self.assertEqual(record.outcome, "DECLINE")
        self.assertEqual(record.reason_code, "OVER_EXPOSED")
        self.assertEqual(record.lineage.agent_reasoning_status, "timeout")


if __name__ == "__main__":
    unittest.main()
