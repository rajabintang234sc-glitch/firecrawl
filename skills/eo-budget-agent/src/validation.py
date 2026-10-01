"""Strict boundary validation. Values returned here are JSON-compatible, not trusted quotes."""

import re
from datetime import date
from decimal import Decimal, InvalidOperation

CATEGORIES = {
    "production": "Produksi", "creative": "Creative", "management": "Management",
    "venue": "Venue", "hospitality": "Hospitality", "talent": "Talent",
    "logistics": "Logistik", "safety": "Safety & legal",
}
EVENT_TYPES = {"corporate", "launch", "activation"}
TAGS = {"venue", "stage", "audio", "led", "power", "design", "motion", "video",
        "producer", "director", "crew", "mc", "catering", "transport", "safety",
        "medical", "permits"}
ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")


class ValidationError(ValueError):
    def __init__(self, message, field="project"):
        super().__init__(message)
        self.field = field


def fail(field, message):
    raise ValidationError(message, field)


def obj(value, field):
    if not isinstance(value, dict):
        fail(field, f"{field} harus berupa objek JSON.")
    return value


def text(value, field, maximum=200, required=True):
    if not isinstance(value, str):
        fail(field, f"{field} harus berupa teks.")
    value = value.strip()
    if (required and not value) or len(value) > maximum or any(ord(c) < 32 for c in value):
        fail(field, f"{field} harus berisi teks valid, maksimal {maximum} karakter.")
    return value


def identifier(value, field):
    value = text(value, field, 80)
    if not ID_PATTERN.fullmatch(value):
        fail(field, f"{field} hanya boleh berisi huruf, angka, titik, tanda - _ atau :.")
    return value


def number(value, field, minimum=0, maximum=1_000_000_000_000, integral=False):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        fail(field, f"{field} harus berupa angka.")
    if len(str(value)) > 50:
        fail(field, f"{field} di luar batas angka yang didukung.")
    try:
        parsed = Decimal(str(value))
    except InvalidOperation:
        fail(field, f"{field} harus berupa angka.")
    if not parsed.is_finite() or parsed < minimum or parsed > maximum:
        fail(field, f"{field} harus di antara {minimum} dan {maximum}.")
    if parsed.as_tuple().exponent < -6:
        fail(field, f"{field} maksimal memiliki 6 angka desimal.")
    if integral and parsed != parsed.to_integral_value():
        fail(field, f"{field} harus berupa bilangan bulat.")
    return int(parsed) if parsed == parsed.to_integral_value() else float(parsed)


def flag(value, field):
    if not isinstance(value, bool):
        fail(field, f"{field} harus true atau false.")
    return value


def choice(value, field, options):
    if not isinstance(value, str) or value not in options:
        fail(field, f"{field} tidak dikenali. Pilih: {', '.join(sorted(options))}.")
    return value


def iso_date(value, field, optional=False):
    if value is None and optional:
        return None
    value = text(value, field, 10)
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        fail(field, f"{field} harus berupa tanggal valid YYYY-MM-DD.")
    if value != parsed.isoformat():
        fail(field, f"{field} harus menggunakan format YYYY-MM-DD.")
    if not 2000 <= parsed.year <= 2100:
        fail(field, f"{field} harus berada di rentang tahun 2000–2100.")
    return value


def validate_project(payload, today=None):
    today = today or date.today()
    payload = obj(payload, "project")
    if payload.get("schemaVersion") != 1 or isinstance(payload.get("schemaVersion"), bool):
        fail("schemaVersion", "Gunakan schemaVersion 1.")
    raw_event = obj(payload.get("event"), "event")
    event = {
        "id": identifier(raw_event.get("id"), "event.id"),
        "name": text(raw_event.get("name"), "event.name", 120),
        "type": choice(raw_event.get("type"), "event.type", EVENT_TYPES),
        "city": text(raw_event.get("city"), "event.city", 80),
        "attendees": number(raw_event.get("attendees"), "event.attendees", 1, 100_000, True),
        "eventDays": number(raw_event.get("eventDays"), "event.eventDays", 1, 30, True),
        "setupDays": number(raw_event.get("setupDays", 1), "event.setupDays", 0, 30, True),
        "date": iso_date(raw_event.get("date"), "event.date"),
        "environment": choice(raw_event.get("environment", "indoor"), "event.environment", {"indoor", "outdoor", "hybrid"}),
    }
    raw_finance = obj(payload.get("finance"), "finance")
    finance = {}
    for key, default in (("clientBudget", 0), ("offerPrice", 0)):
        finance[key] = number(raw_finance.get(key, default), f"finance.{key}", integral=True)
    for key, default, upper in (
        ("overheadPercent", 8, 100), ("contingencyPercent", 7.5, 100),
        ("targetMarginPercent", 25, 79.99), ("minimumMarginPercent", 15, 79.99),
        ("vatPercent", 0, 100), ("withholdingPercent", 0, 100),
        ("withholdingBasePercent", 100, 100), ("downPaymentPercent", 50, 100),
    ):
        finance[key] = number(raw_finance.get(key, default), f"finance.{key}", 0, upper)
    if finance["minimumMarginPercent"] > finance["targetMarginPercent"]:
        fail("finance.minimumMarginPercent", "Margin minimum tidak boleh melebihi margin target.")
    finance["budgetIncludesVat"] = flag(raw_finance.get("budgetIncludesVat", True), "finance.budgetIncludesVat")
    finance["taxVerified"] = flag(raw_finance.get("taxVerified", False), "finance.taxVerified")
    finance["taxStatus"] = choice(raw_finance.get("taxStatus", "unconfirmed"), "finance.taxStatus", {"unconfirmed", "pkp", "non_pkp"})
    finance["rounding"] = number(raw_finance.get("rounding", 100_000), "finance.rounding", 1, 1_000_000, True)
    if finance["rounding"] not in {1, 1000, 10000, 50000, 100000, 1000000}:
        fail("finance.rounding", "Pembulatan harus 1, 1.000, 10.000, 50.000, 100.000, atau 1.000.000 rupiah.")
    if finance["taxStatus"] == "non_pkp" and finance["vatPercent"] != 0:
        fail("finance.vatPercent", "Status non-PKP tidak boleh menagihkan PPN. Tinjau status pajak terlebih dahulu.")
    raw_items = payload.get("items")
    if not isinstance(raw_items, list) or not 1 <= len(raw_items) <= 250:
        fail("items", "RAB harus memuat 1–250 baris biaya.")
    items, seen = [], set()
    for index, raw in enumerate(raw_items):
        path = f"items[{index}]"
        raw = obj(raw, path)
        item_id = identifier(raw.get("id"), f"{path}.id")
        if item_id in seen:
            fail(f"{path}.id", "ID baris RAB harus unik.")
        seen.add(item_id)
        item = {
            "id": item_id,
            "name": text(raw.get("name"), f"{path}.name", 200),
            "category": choice(raw.get("category"), f"{path}.category", CATEGORIES),
            "unit": text(raw.get("unit", "paket"), f"{path}.unit", 30),
            "quantity": number(raw.get("quantity"), f"{path}.quantity", 0.000001, 1_000_000),
            "duration": number(raw.get("duration", 1), f"{path}.duration", 0.000001, 365),
            "unitPrice": number(raw.get("unitPrice"), f"{path}.unitPrice"),
            "kind": choice(raw.get("kind", "direct"), f"{path}.kind", {"direct", "overhead"}),
            "priority": choice(raw.get("priority", "essential"), f"{path}.priority", {"essential", "flexible", "optional"}),
            "quantityBasis": choice(raw.get("quantityBasis", "fixed"), f"{path}.quantityBasis", {"fixed", "attendees"}),
            "durationBasis": choice(raw.get("durationBasis", "fixed"), f"{path}.durationBasis", {"fixed", "eventDays", "totalDays"}),
            "advancePercent": number(raw.get("advancePercent", 50), f"{path}.advancePercent", 0, 100),
            "confidence": choice(raw.get("confidence", "estimate"), f"{path}.confidence", {"estimate", "quote", "contract"}),
            "vendor": text(raw.get("vendor", ""), f"{path}.vendor", 120, False),
            "reference": text(raw.get("reference", ""), f"{path}.reference", 500, False),
            "verifiedAt": iso_date(raw.get("verifiedAt"), f"{path}.verifiedAt", True),
            "validUntil": iso_date(raw.get("validUntil"), f"{path}.validUntil", True),
            "actualUnitPrice": None if raw.get("actualUnitPrice") is None else number(raw["actualUnitPrice"], f"{path}.actualUnitPrice"),
        }
        tags = raw.get("tags", [])
        if not isinstance(tags, list) or len(tags) > 20:
            fail(f"{path}.tags", "Tags harus berupa daftar, maksimal 20.")
        item["tags"] = list(dict.fromkeys(choice(tag, f"{path}.tags", TAGS) for tag in tags))
        if item["verifiedAt"] and date.fromisoformat(item["verifiedAt"]) > today:
            fail(f"{path}.verifiedAt", "Tanggal verifikasi tidak boleh di masa depan.")
        if item["validUntil"] and item["verifiedAt"] and item["validUntil"] < item["verifiedAt"]:
            fail(f"{path}.validUntil", "Masa berlaku tidak boleh mendahului tanggal verifikasi.")
        if item["confidence"] != "estimate" and not all((item["vendor"], item["reference"], item["verifiedAt"])):
            fail(f"{path}.confidence", "Quote/kontrak wajib memiliki vendor, referensi dokumen, dan tanggal verifikasi.")
        if Decimal(str(item["quantity"])) * Decimal(str(item["duration"])) * Decimal(str(item["unitPrice"])) > 10**15:
            fail(path, "Total biaya per baris melampaui batas 1.000 triliun rupiah.")
        items.append(item)
    if any(i["kind"] == "overhead" for i in items) and finance["overheadPercent"] != 0:
        fail("finance.overheadPercent", "Pilih overhead per baris ATAU alokasi persentase. Set overhead 0% saat merinci overhead agar tidak dihitung dua kali.")
    raw_observations = payload.get("observations", [])
    if not isinstance(raw_observations, list) or len(raw_observations) > 2000:
        fail("observations", "Riwayat realisasi maksimal 2.000 observasi.")
    observations, observations_seen = [], set()
    for index, raw in enumerate(raw_observations):
        path = f"observations[{index}]"
        raw = obj(raw, path)
        observation = {
            "itemId": identifier(raw.get("itemId"), f"{path}.itemId"),
            "eventId": identifier(raw.get("eventId"), f"{path}.eventId"),
            "eventType": choice(raw.get("eventType"), f"{path}.eventType", EVENT_TYPES),
            "city": text(raw.get("city"), f"{path}.city", 80),
            "unit": text(raw.get("unit"), f"{path}.unit", 30),
            "specification": text(raw.get("specification"), f"{path}.specification", 200),
            "unitPrice": number(raw.get("unitPrice"), f"{path}.unitPrice"),
            "recordedAt": iso_date(raw.get("recordedAt"), f"{path}.recordedAt"),
        }
        if date.fromisoformat(observation["recordedAt"]) > today:
            fail(f"{path}.recordedAt", "Tanggal realisasi tidak boleh di masa depan.")
        key = (observation["eventId"], observation["itemId"])
        if key in observations_seen:
            fail(path, "Satu event hanya boleh menyumbang satu observasi untuk satu item.")
        observations_seen.add(key)
        observations.append(observation)
    raw_audit = payload.get("audit", [])
    if not isinstance(raw_audit, list) or len(raw_audit) > 500:
        fail("audit", "Audit lokal maksimal 500 revisi.")
    audit = []
    for index, raw in enumerate(raw_audit):
        path = f"audit[{index}]"
        raw = obj(raw, path)
        audit.append({
            "itemId": identifier(raw.get("itemId"), f"{path}.itemId"),
            "proposalId": identifier(raw.get("proposalId"), f"{path}.proposalId"),
            "previousPrice": number(raw.get("previousPrice"), f"{path}.previousPrice"),
            "newPrice": number(raw.get("newPrice"), f"{path}.newPrice"),
            "sampleCount": number(raw.get("sampleCount"), f"{path}.sampleCount", 1, 2000, True),
            "reviewedAt": text(raw.get("reviewedAt"), f"{path}.reviewedAt", 40),
        })
    return {"schemaVersion": 1, "event": event, "finance": finance, "items": items,
            "observations": observations, "audit": audit}
