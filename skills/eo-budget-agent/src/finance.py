"""Deterministic IDR arithmetic: Decimal internally, whole rupiah at boundaries."""

from datetime import date
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, localcontext
from validation import CATEGORIES


def dec(value):
    return Decimal(str(value))


def money(value):
    return int(dec(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def percent(part, whole):
    return float((dec(part) / dec(whole) * 100).quantize(Decimal("0.01"))) if whole else None


def round_up(value, step):
    return int((dec(value) / dec(step)).to_integral_value(rounding=ROUND_CEILING) * dec(step))


def calculate(project, policy, today):
    with localcontext() as context:
        context.prec = 50
        return _calculate(project, policy, today)


def _calculate(project, policy, today):
    f, event = project["finance"], project["event"]
    lines, category_totals = [], {category: 0 for category in CATEGORIES}
    direct, detailed_overhead, pre_event_vendor = 0, 0, 0
    fresh_count, fresh_value, expired_count, estimate_count, known_actual_cost = 0, 0, 0, 0, 0
    actual_count = 0
    for item in project["items"]:
        line = dict(item)
        line["total"] = money(dec(item["quantity"]) * dec(item["duration"]) * dec(item["unitPrice"]))
        line["actualTotal"] = None
        line["variance"] = None
        if item["actualUnitPrice"] is not None:
            line["actualTotal"] = money(dec(item["quantity"]) * dec(item["duration"]) * dec(item["actualUnitPrice"]))
            line["variance"] = line["actualTotal"] - line["total"]
            known_actual_cost += line["actualTotal"]
            actual_count += 1
        if item["kind"] == "direct":
            direct += line["total"]
            category_totals[item["category"]] += line["total"]
        else:
            detailed_overhead += line["total"]
        pre_event_vendor += money(dec(line["total"]) * dec(item["advancePercent"]) / 100)
        verified = date.fromisoformat(item["verifiedAt"]) if item["verifiedAt"] else None
        expiry = date.fromisoformat(item["validUntil"]) if item["validUntil"] else None
        is_recent = verified is not None and (today - verified).days <= policy["quoteMaxAgeDays"]
        covers_event = (expiry is not None and expiry >= date.fromisoformat(event["date"])) or (item["confidence"] == "contract" and expiry is None)
        line["freshQuote"] = item["confidence"] != "estimate" and is_recent and covers_event
        line["expired"] = expiry is not None and expiry < today
        if line["freshQuote"]:
            fresh_count += 1
            fresh_value += line["total"]
        if line["expired"]:
            expired_count += 1
        if item["confidence"] == "estimate":
            estimate_count += 1
        lines.append(line)
    allocated_overhead = money(dec(direct) * dec(f["overheadPercent"]) / 100)
    overhead = detailed_overhead + allocated_overhead
    hpp = direct + overhead
    reserve = money(dec(hpp) * dec(f["contingencyPercent"]) / 100)
    risk_cost = hpp + reserve
    categories = [{"id": key, "name": CATEGORIES[key], "total": value,
                   "sharePercent": percent(value, direct) or 0}
                  for key, value in category_totals.items() if value]
    categories.sort(key=lambda c: c["total"], reverse=True)
    totals = {"directCost": direct, "overhead": overhead, "detailedOverhead": detailed_overhead,
              "allocatedOverhead": allocated_overhead, "hpp": hpp, "contingency": reserve,
              "riskAdjustedCost": risk_cost, "hppPerAttendee": money(dec(hpp) / event["attendees"]),
              "actualItemCost": known_actual_cost, "actualItemCount": actual_count,
              "actualComplete": actual_count == len(lines)}
    vat_factor = 1 + dec(f["vatPercent"]) / 100

    def scenario(scenario_id, label, margin):
        price = round_up(dec(risk_cost) / (1 - dec(margin) / 100), f["rounding"])
        return {"id": scenario_id, "label": label, "targetMarginPercent": margin,
                "price": price, "invoiceTotal": price + money(dec(price) * dec(f["vatPercent"]) / 100),
                "profit": price - risk_cost, "marginPercent": percent(price - risk_cost, price)}

    scenarios = [scenario("floor", "Batas negosiasi", f["minimumMarginPercent"]),
                 scenario("target", "Harga ideal", f["targetMarginPercent"]),
                 scenario("premium", "Ruang value-added", min(90, f["targetMarginPercent"] + 8))]
    recommended = scenarios[1]["price"]
    selected = f["offerPrice"] or recommended
    # Withholding changes cash, not revenue or HPP. The applicable base is user-confirmed.
    vat = money(dec(selected) * dec(f["vatPercent"]) / 100)
    withholding = money(dec(selected) * dec(f["withholdingPercent"]) / 100 * dec(f["withholdingBasePercent"]) / 100)
    invoice = selected + vat
    pricing = {"floorPrice": scenarios[0]["price"], "recommendedPrice": recommended,
               "recommendedInvoiceTotal": scenarios[1]["invoiceTotal"], "selectedPrice": selected,
               "vat": vat, "withholding": withholding, "invoiceTotal": invoice,
               "clientReceipt": invoice - withholding, "projectedProfit": selected - risk_cost,
               "marginPercent": percent(selected - risk_cost, selected),
               "marginBeforeReservePercent": percent(selected - hpp, selected),
               "markupPercent": percent(selected - risk_cost, risk_cost),
               "pricePerAttendee": money(dec(selected) / event["attendees"]), "scenarios": scenarios}
    budget_ex_vat = int((dec(f["clientBudget"]) / vat_factor).to_integral_value(rounding=ROUND_FLOOR)) if f["budgetIncludesVat"] else f["clientBudget"]
    required_budget = scenarios[1]["invoiceTotal"] if f["budgetIncludesVat"] else recommended
    offered_budget = invoice if f["budgetIncludesVat"] else selected
    scope_options = []
    for line in sorted(lines, key=lambda item: item["total"], reverse=True):
        if line["priority"] != "essential" and line["category"] != "safety" and line["kind"] == "direct":
            saving = money(dec(line["total"]) * (1 + dec(f["overheadPercent"]) / 100) * (1 + dec(f["contingencyPercent"]) / 100))
            scope_options.append({"itemId": line["id"], "name": line["name"], "directSaving": line["total"],
                                  "riskAdjustedSaving": saving, "action": "Tinjau spesifikasi / opsi vendor; bukan pemotongan otomatis."})
    budget = {"clientBudget": f["clientBudget"], "budgetExVat": budget_ex_vat,
              "includesVat": f["budgetIncludesVat"], "recommendedFits": required_budget <= f["clientBudget"],
              "offerFits": offered_budget <= f["clientBudget"], "recommendedBudget": required_budget,
              "offerBudget": offered_budget, "recommendedGap": max(0, required_budget - f["clientBudget"]),
              "headroom": f["clientBudget"] - offered_budget,
              "utilizationPercent": percent(offered_budget, f["clientBudget"]),
              "maximumHppAtTarget": int((dec(budget_ex_vat) * (1 - dec(f["targetMarginPercent"]) / 100) / (1 + dec(f["contingencyPercent"]) / 100)).to_integral_value(rounding=ROUND_FLOOR)),
              "scopeOptions": scope_options[:4]}
    available_dp = money(dec(selected - withholding) * dec(f["downPaymentPercent"]) / 100)
    dp_invoice = money(dec(invoice) * dec(f["downPaymentPercent"]) / 100)
    pre_event_need = pre_event_vendor + allocated_overhead + reserve
    cashflow = {"downPaymentInvoice": dp_invoice, "availableDownPayment": available_dp,
                "vendorPreEvent": pre_event_vendor, "overheadReserve": allocated_overhead,
                "riskReserve": reserve, "preEventNeed": pre_event_need,
                "fundingGap": max(0, pre_event_need - available_dp),
                "requiredDownPaymentPercent": percent(pre_event_need, selected - withholding),
                "remainingClientReceipt": invoice - withholding - money(dec(invoice - withholding) * dec(f["downPaymentPercent"]) / 100),
                "note": "Simulasi satu termin sebelum event. PPN tidak digunakan sebagai modal; cadangan dan overhead alokasi disisihkan penuh. Jadwal aktual perlu divalidasi."}
    quality = {"itemCount": len(lines), "estimateCount": estimate_count, "freshQuoteCount": fresh_count,
               "pendingQuoteCount": len(lines) - fresh_count, "expiredCount": expired_count,
               "unpricedCount": sum(1 for line in lines if not line["unitPrice"]),
               "verifiedCostPercent": percent(fresh_value, direct + detailed_overhead) or 0,
               "taxVerified": f["taxVerified"]}
    return {"rab": {"items": lines, "categories": categories}, "totals": totals, "pricing": pricing,
            "budget": budget, "cashflow": cashflow, "quality": quality}
