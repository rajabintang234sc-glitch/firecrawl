"""Review-gated rate learning. No autonomous code edits or web-price ingestion."""

import copy
import hashlib
import json
from datetime import date, datetime, timezone
from statistics import median

from finance import dec, money, percent
from validation import ValidationError, validate_project


def comparable_text(value):
    return " ".join(value.casefold().split())


def build_proposals(project, policy, today):
    rules = policy["learning"]
    proposals = []
    for item in project["items"]:
        observations = [dict(observation) for observation in project["observations"]
                        if observation["itemId"] == item["id"]
                        and observation["eventType"] == project["event"]["type"]
                        and comparable_text(observation["city"]) == comparable_text(project["event"]["city"])
                        and comparable_text(observation["unit"]) == comparable_text(item["unit"])
                        and comparable_text(observation["specification"]) == comparable_text(item["name"])
                        and 0 <= (today - date.fromisoformat(observation["recordedAt"])).days <= rules["historyWindowDays"]]
        if not observations:
            continue
        observations.sort(key=lambda observation: (observation["eventId"], observation["recordedAt"]))
        rates = [dec(observation["unitPrice"]) for observation in observations]
        middle = median(rates)
        previous = dec(item["unitPrice"])
        deviation = percent(middle - previous, previous)
        spread = percent(max(rates) - min(rates), middle)
        reasons = []
        if len(observations) < rules["minimumSamples"]:
            reasons.append(f"Perlu minimal {rules['minimumSamples']} event berbeda; baru {len(observations)} sampel.")
        if previous == 0 or middle == 0:
            reasons.append("Harga nol perlu review manual; tidak dapat menjadi basis pembelajaran otomatis.")
        if deviation is not None and abs(deviation) > rules["maximumDeviationPercent"]:
            reasons.append("Perubahan median melewati batas deviasi kebijakan; periksa perubahan scope atau outlier.")
        if spread is not None and spread > rules["maximumSpreadPercent"]:
            reasons.append("Sebaran tarif terlalu lebar; pisahkan spesifikasi sebelum belajar.")
        fingerprint_data = {"eventId": project["event"]["id"], "itemId": item["id"], "previousPrice": item["unitPrice"],
                            "observations": observations, "policy": dict(rules), "today": today.isoformat()}
        proposal_id = hashlib.sha256(json.dumps(fingerprint_data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:24]
        proposed = money(previous + (middle - previous) * dec(rules["learningRate"]))
        proposals.append({"id": proposal_id, "itemId": item["id"], "name": item["name"],
                          "previousPrice": item["unitPrice"], "medianActualPrice": money(middle),
                          "proposedPrice": proposed, "sampleCount": len(observations),
                          "deviationPercent": deviation, "eligible": not reasons, "reasons": reasons,
                          "note": "Usulan estimasi berikutnya, bukan penawaran vendor terverifikasi."})
    return {"proposals": proposals, "observationCount": len(project["observations"]),
            "eligibleCount": sum(1 for p in proposals if p["eligible"]),
            "policy": dict(rules), "mode": "review-required"}


def apply_proposals(payload, proposal_ids, policy, today=None):
    today = today or date.today()
    project = validate_project(payload, today=today)
    if not isinstance(proposal_ids, list) or not proposal_ids or len(proposal_ids) > 250 or any(not isinstance(pid, str) for pid in proposal_ids):
        raise ValidationError("Pilih minimal satu proposal valid untuk disetujui.", "proposalIds")
    if len(set(proposal_ids)) != len(proposal_ids):
        raise ValidationError("Proposal duplikat tidak boleh diterapkan.", "proposalIds")
    available = {p["id"]: p for p in build_proposals(project, policy, today)["proposals"]}
    selected = []
    for proposal_id in proposal_ids:
        proposal = available.get(proposal_id)
        if not proposal:
            raise ValidationError("Proposal sudah berubah atau tidak ditemukan. Hitung ulang sebelum review.", "proposalIds")
        if not proposal["eligible"]:
            raise ValidationError("Proposal belum memenuhi kebijakan pembelajaran: " + " ".join(proposal["reasons"]), "proposalIds")
        selected.append(proposal)
    # Validate the entire batch before mutating. Applying an estimate invalidates its old quote.
    updated = copy.deepcopy(project)
    indexed = {item["id"]: item for item in updated["items"]}
    for proposal in selected:
        item = indexed[proposal["itemId"]]
        item.update(unitPrice=proposal["proposedPrice"], confidence="estimate", vendor="", reference="",
                    verifiedAt=None, validUntil=None, actualUnitPrice=None)
        updated["audit"].append({"itemId": item["id"], "proposalId": proposal["id"],
                                 "previousPrice": proposal["previousPrice"], "newPrice": proposal["proposedPrice"],
                                 "sampleCount": proposal["sampleCount"],
                                 "reviewedAt": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    updated["audit"] = updated["audit"][-500:]
    return validate_project(updated, today=today)
