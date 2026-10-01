import copy
import json
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from engine import analyze
from validation import ValidationError, validate_project

TODAY = date(2026, 9, 30)


def project():
    value = json.loads((ROOT / "data" / "sample-project.json").read_text())
    value["items"] = [value["items"][0]]
    value["items"][0].update(unitPrice=100_000_000, quantity=1, duration=1)
    value["finance"].update(overheadPercent=0, contingencyPercent=0,
                             targetMarginPercent=25, minimumMarginPercent=15,
                             rounding=1000, clientBudget=200_000_000)
    return value


class CalculationTests(unittest.TestCase):
    def test_margin_is_not_markup(self):
        result = analyze(project(), today=TODAY)
        self.assertEqual(result["totals"]["hpp"], 100_000_000)
        self.assertEqual(result["pricing"]["recommendedPrice"], 133_334_000)
        self.assertGreaterEqual(result["pricing"]["marginPercent"], 25)
        self.assertEqual(len(result["agents"]), 6)
        self.assertEqual(result["execution"]["mode"], "parallel-rules")

    def test_overhead_and_reserve_separated(self):
        value = project()
        value["finance"].update(overheadPercent=10, contingencyPercent=10)
        result = analyze(value, today=TODAY)
        self.assertEqual(result["totals"]["overhead"], 10_000_000)
        self.assertEqual(result["totals"]["hpp"], 110_000_000)
        self.assertEqual(result["totals"]["contingency"], 11_000_000)
        self.assertEqual(result["totals"]["riskAdjustedCost"], 121_000_000)

    def test_vat_is_not_revenue_and_withholding_is_not_expense(self):
        value = project()
        value["finance"].update(vatPercent=11, taxStatus="pkp", taxVerified=True,
                                 withholdingPercent=2, offerPrice=200_000_000)
        result = analyze(value, today=TODAY)
        self.assertEqual(result["pricing"]["invoiceTotal"], 222_000_000)
        self.assertEqual(result["pricing"]["withholding"], 4_000_000)
        self.assertEqual(result["pricing"]["clientReceipt"], 218_000_000)
        self.assertEqual(result["pricing"]["projectedProfit"], 100_000_000)
        self.assertEqual(result["budget"]["budgetExVat"], 180_180_180)
        self.assertEqual(result["cashflow"]["availableDownPayment"], 98_000_000)

    def test_withholding_base_is_configurable(self):
        value = project()
        value["finance"].update(offerPrice=200_000_000, withholdingPercent=2,
                                 withholdingBasePercent=40)
        self.assertEqual(analyze(value, today=TODAY)["pricing"]["withholding"], 1_600_000)

    def test_quantity_and_duration(self):
        value = project()
        value["items"][0].update(quantity=2.5, duration=3, unitPrice=10001)
        result = analyze(value, today=TODAY)
        self.assertEqual(result["totals"]["directCost"], 75008)
        self.assertEqual(result["rab"]["items"][0]["total"], 75008)

    def test_round_up_does_not_violate_floor(self):
        for cost in (1, 100, 99999, 300000, 975111):
            value = project()
            value["items"][0]["unitPrice"] = cost
            result = analyze(value, today=TODAY)
            self.assertGreaterEqual(result["pricing"]["marginPercent"], 25)
            self.assertGreaterEqual(result["pricing"]["recommendedPrice"], result["pricing"]["floorPrice"])

    def test_lower_offer_reports_negative_margin_and_budget_fail(self):
        value = project()
        value["finance"].update(offerPrice=50_000_000, clientBudget=40_000_000)
        result = analyze(value, today=TODAY)
        self.assertEqual(result["pricing"]["marginPercent"], -100)
        self.assertFalse(result["budget"]["offerFits"])
        self.assertEqual(result["budget"]["recommendedGap"], 93_334_000)
        pricing_agent = next(a for a in result["agents"] if a["id"] == "pricing")
        self.assertEqual(pricing_agent["status"], "blocked")

    def test_zero_cost_does_not_crash_or_invent_profit(self):
        value = project()
        value["items"][0]["unitPrice"] = 0
        result = analyze(value, today=TODAY)
        self.assertIsNone(result["pricing"]["marginPercent"])
        self.assertEqual(result["pricing"]["recommendedPrice"], 0)

    def test_margin_guard_uses_exact_amounts_not_display_percent(self):
        value = project()
        value["finance"]["offerPrice"] = 133_333_333
        result = analyze(value, today=TODAY)
        self.assertEqual(result["pricing"]["marginPercent"], 25)
        agent = next(a for a in result["agents"] if a["id"] == "pricing")
        self.assertTrue(any(i["code"] == "below-target" for i in agent["insights"]))

    def test_cashflow_reserves_vat_and_full_contingency(self):
        value = project()
        value["finance"].update(overheadPercent=10, contingencyPercent=10,
                                 offerPrice=200_000_000, downPaymentPercent=10,
                                 vatPercent=11, taxStatus="pkp", withholdingPercent=2)
        value["items"][0]["advancePercent"] = 60
        result = analyze(value, today=TODAY)
        self.assertEqual(result["cashflow"]["availableDownPayment"], 19_600_000)
        self.assertEqual(result["cashflow"]["preEventNeed"], 81_000_000)
        self.assertEqual(result["cashflow"]["fundingGap"], 61_400_000)
        self.assertEqual(result["cashflow"]["downPaymentInvoice"], 22_200_000)

    def test_snapshot_deeply_immutable(self):
        from engine import freeze
        snapshot = freeze(validate_project(project(), today=TODAY))
        with self.assertRaises(TypeError):
            snapshot["items"][0]["unitPrice"] = 0
        with self.assertRaises(TypeError):
            snapshot["finance"]["targetMarginPercent"] = 100

    def test_explicit_overhead_is_counted_once(self):
        value = project()
        extra = copy.deepcopy(value["items"][0])
        extra.update(id="admin", kind="overhead", unitPrice=5_000_000)
        value["items"].append(extra)
        result = analyze(value, today=TODAY)
        self.assertEqual(result["totals"]["overhead"], 5_000_000)
        self.assertEqual(result["totals"]["hpp"], 105_000_000)

    def test_input_is_not_mutated_by_parallel_agents(self):
        value = project()
        before = copy.deepcopy(value)
        analyze(value, today=TODAY)
        self.assertEqual(value, before)

    def test_templates_all_analyze(self):
        templates = json.loads((ROOT / "data" / "templates.json").read_text())["templates"]
        for template in templates:
            with self.subTest(template=template["id"]):
                result = analyze(template["project"], today=TODAY)
                self.assertEqual(sum(c["total"] for c in result["rab"]["categories"]), result["totals"]["directCost"])
                self.assertEqual(len(result["agents"]), 6)
                self.assertGreaterEqual(result["pricing"]["marginPercent"], 25)

    def test_essential_and_safety_are_not_cut_suggestions(self):
        value = project()
        value["finance"]["clientBudget"] = 10_000_000
        result = analyze(value, today=TODAY)
        self.assertEqual(result["budget"]["scopeOptions"], [])

    def test_stale_and_expired_quote_is_not_fresh(self):
        value = project()
        value["items"][0].update(confidence="quote", vendor="Vendor A",
                                 reference="Q-001", verifiedAt="2026-08-01", validUntil="2026-09-20")
        result = analyze(value, today=TODAY)
        self.assertEqual(result["quality"]["freshQuoteCount"], 0)
        self.assertEqual(result["quality"]["expiredCount"], 1)

    def test_quote_must_cover_event_date(self):
        value = project()
        value["items"][0].update(confidence="quote", vendor="Vendor A",
                                 reference="Q-001", verifiedAt="2026-09-29", validUntil="2026-10-05")
        result = analyze(value, today=TODAY)
        self.assertEqual(result["quality"]["freshQuoteCount"], 0)

    def test_concurrent_requests_have_isolated_snapshots(self):
        from concurrent.futures import ThreadPoolExecutor
        values = [project() for _ in range(12)]
        for index, value in enumerate(values):
            value["items"][0]["unitPrice"] = index * 10000
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda p: analyze(p, today=TODAY), values))
        self.assertEqual([r["totals"]["hpp"] for r in results], [i * 10000 for i in range(12)])


class ValidationTests(unittest.TestCase):
    def assert_invalid(self, mutate):
        value = project()
        mutate(value)
        with self.assertRaises(ValidationError):
            validate_project(value, today=TODAY)

    def test_margin_100_rejected(self):
        self.assert_invalid(lambda p: p["finance"].update(targetMarginPercent=100))

    def test_minimum_cannot_exceed_target(self):
        self.assert_invalid(lambda p: p["finance"].update(minimumMarginPercent=30))

    def test_negative_rate_rejected(self):
        self.assert_invalid(lambda p: p["items"][0].update(unitPrice=-1))

    def test_non_finite_and_boolean_money_rejected(self):
        for bad in (float("nan"), float("inf"), True, "Infinity", "1e999", {}):
            with self.subTest(value=bad):
                self.assert_invalid(lambda p: p["items"][0].update(unitPrice=bad))

    def test_empty_items_rejected(self):
        self.assert_invalid(lambda p: p.update(items=[]))

    def test_duplicate_ids_rejected(self):
        self.assert_invalid(lambda p: p["items"].append(copy.deepcopy(p["items"][0])))

    def test_bad_category_rejected(self):
        self.assert_invalid(lambda p: p["items"][0].update(category="invented"))

    def test_overhead_double_count_rejected(self):
        self.assert_invalid(lambda p: (p["items"][0].update(kind="overhead"), p["finance"].update(overheadPercent=10)))

    def test_non_pkp_cannot_charge_vat(self):
        self.assert_invalid(lambda p: p["finance"].update(taxStatus="non_pkp", vatPercent=11))

    def test_unsubstantiated_quote_rejected(self):
        self.assert_invalid(lambda p: p["items"][0].update(confidence="quote"))

    def test_future_verified_date_rejected(self):
        self.assert_invalid(lambda p: p["items"][0].update(confidence="quote", vendor="A", reference="Q", verifiedAt="2027-01-01"))

    def test_zero_attendees_rejected(self):
        self.assert_invalid(lambda p: p["event"].update(attendees=0))

    def test_invalid_date_rejected(self):
        self.assert_invalid(lambda p: p["event"].update(date="2026-02-31"))

    def test_too_many_items_rejected(self):
        self.assert_invalid(lambda p: p.update(items=[dict(p["items"][0], id=str(i)) for i in range(251)]))

    def test_extreme_dates_rejected_before_timeline_arithmetic(self):
        for invalid in ("0001-01-01", "9999-12-31"):
            self.assert_invalid(lambda p: p["event"].update(date=invalid))

    def test_fractional_budget_and_offer_rejected(self):
        for field in ("clientBudget", "offerPrice"):
            self.assert_invalid(lambda p: p["finance"].update({field: 100.5}))

    def test_invalid_finance_flag_rejected(self):
        self.assert_invalid(lambda p: p["finance"].update(budgetIncludesVat="false"))


if __name__ == "__main__":
    unittest.main()
