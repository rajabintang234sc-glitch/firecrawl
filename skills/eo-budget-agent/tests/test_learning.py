import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from engine import analyze, load_policy
from learning import apply_proposals
from validation import ValidationError
from test_engine import TODAY, project


def with_observations(rates=(110_000_000, 115_000_000, 120_000_000)):
    value = project()
    row = value["items"][0]
    value["observations"] = [dict(itemId=row["id"], eventId=f"completed-{index}", eventType=value["event"]["type"],
                                  city="Jakarta", unit=row["unit"], specification=row["name"],
                                  unitPrice=rate, recordedAt="2026-09-01") for index, rate in enumerate(rates)]
    return value


class LearningTests(unittest.TestCase):
    def test_recommendation_is_smoothed_not_auto_applied(self):
        value = with_observations()
        before = copy.deepcopy(value)
        proposal = analyze(value, today=TODAY)["learning"]["proposals"][0]
        self.assertTrue(proposal["eligible"])
        self.assertEqual(proposal["proposedPrice"], 103_750_000)
        self.assertEqual(value, before)

    def test_apply_creates_audit_and_invalidates_old_quote(self):
        value = with_observations()
        value["items"][0].update(confidence="quote", vendor="A", reference="Q-10", verifiedAt="2026-09-29", validUntil="2026-12-01")
        proposal_id = analyze(value, today=TODAY)["learning"]["proposals"][0]["id"]
        result = apply_proposals(value, [proposal_id], load_policy(), today=TODAY)
        self.assertEqual(result["items"][0]["unitPrice"], 103_750_000)
        self.assertEqual(result["items"][0]["confidence"], "estimate")
        self.assertIsNone(result["items"][0]["verifiedAt"])
        self.assertEqual(len(result["audit"]), 1)
        self.assertEqual(value["items"][0]["unitPrice"], 100_000_000)

    def test_single_observation_needs_more_events(self):
        value = with_observations((110_000_000,))
        proposal = analyze(value, today=TODAY)["learning"]["proposals"][0]
        self.assertFalse(proposal["eligible"])
        with self.assertRaises(ValidationError):
            apply_proposals(value, [proposal["id"]], load_policy(), today=TODAY)

    def test_outliers_cannot_be_applied(self):
        value = with_observations((200_000_000, 205_000_000, 210_000_000))
        proposal = analyze(value, today=TODAY)["learning"]["proposals"][0]
        self.assertFalse(proposal["eligible"])
        self.assertTrue(any("deviasi" in reason for reason in proposal["reasons"]))

    def test_different_city_unit_specification_type_and_old_rates_ignored(self):
        for field, different in (("city", "Bandung"), ("unit", "m²"), ("specification", "Venue outdoor"),
                                  ("eventType", "launch"), ("recordedAt", "2025-01-01")):
            value = with_observations()
            for observation in value["observations"]:
                observation[field] = different
            self.assertEqual(analyze(value, today=TODAY)["learning"]["proposals"], [])

    def test_duplicate_event_cannot_inflate_sample_count(self):
        value = with_observations()
        value["observations"][1]["eventId"] = value["observations"][0]["eventId"]
        with self.assertRaises(ValidationError):
            analyze(value, today=TODAY)

    def test_stale_proposal_is_rejected_without_partial_update(self):
        value = with_observations()
        proposal = analyze(value, today=TODAY)["learning"]["proposals"][0]
        value["items"][0]["unitPrice"] = 105_000_000
        before = copy.deepcopy(value)
        with self.assertRaises(ValidationError):
            apply_proposals(value, [proposal["id"]], load_policy(), today=TODAY)
        self.assertEqual(value, before)

    def test_batch_is_atomic_when_one_proposal_invalid(self):
        value = with_observations()
        proposal = analyze(value, today=TODAY)["learning"]["proposals"][0]
        before = copy.deepcopy(value)
        with self.assertRaises(ValidationError):
            apply_proposals(value, [proposal["id"], "nonexistent"], load_policy(), today=TODAY)
        self.assertEqual(value, before)

    def test_excessive_spread_blocked_even_when_median_matches(self):
        value = with_observations((1_000_000, 100_000_000, 199_000_000))
        proposal = analyze(value, today=TODAY)["learning"]["proposals"][0]
        self.assertFalse(proposal["eligible"])
        self.assertTrue(any("Sebaran" in reason for reason in proposal["reasons"]))


if __name__ == "__main__":
    unittest.main()
