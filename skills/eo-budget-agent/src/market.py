"""Optional server-only Firecrawl search; results are untrusted references, not rates."""

import json
import os
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from validation import text


class ResearchUnavailable(RuntimeError):
    pass


class ResearchError(RuntimeError):
    pass


def research_enabled():
    return os.environ.get("EO_ENABLE_RESEARCH") == "1" and bool(os.environ.get("FIRECRAWL_API_KEY"))


def safe_url(value):
    if not isinstance(value, str) or len(value) > 2000:
        return None
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            return None
        return value
    except ValueError:
        return None


def search_market(query, city, transport=None):
    query = text(query, "query", 300)
    city = text(city, "city", 80)
    if not research_enabled():
        raise ResearchUnavailable("Riset belum aktif. Administrator perlu mengatur EO_ENABLE_RESEARCH=1 dan FIRECRAWL_API_KEY di server, bukan di browser.")
    base = os.environ.get("FIRECRAWL_API_URL", "https://api.firecrawl.dev").rstrip("/")
    parts = urlsplit(base)
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
        raise ResearchError("Konfigurasi URL Firecrawl tidak valid.")
    endpoint = base + ("/search" if base.endswith("/v2") else "/v2/search")
    payload = {"query": f"{query} {city} event organizer vendor Indonesia", "limit": 5,
               "sources": ["web"], "country": "ID", "timeout": 20000}
    request = Request(endpoint, data=json.dumps(payload).encode(), method="POST",
                      headers={"Authorization": "Bearer " + os.environ["FIRECRAWL_API_KEY"], "Content-Type": "application/json"})
    try:
        if transport:
            response = transport(request)
        else:
            with urlopen(request, timeout=25) as upstream:
                raw = upstream.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise ResearchError("Hasil riset terlalu besar. Persempit pencarian.")
                response = json.loads(raw)
    except HTTPError as error:
        # Never propagate upstream response bodies or credentials into browser errors.
        if error.code in {401, 403}:
            raise ResearchError("Autentikasi Firecrawl perlu diperiksa oleh administrator.") from None
        if error.code in {402, 429}:
            raise ResearchError("Kredit atau batas permintaan Firecrawl tidak mencukupi.") from None
        raise ResearchError("Layanan riset belum dapat merespons. Coba lagi nanti.") from None
    except (URLError, TimeoutError, OSError, json.JSONDecodeError, UnicodeDecodeError):
        raise ResearchError("Koneksi riset gagal atau respons tidak valid.") from None
    if not isinstance(response, dict) or response.get("success") is not True:
        raise ResearchError("Firecrawl mengembalikan respons pencarian yang tidak valid.")
    data = response.get("data", {})
    records = data.get("web", []) if isinstance(data, dict) else data if isinstance(data, list) else []
    if not isinstance(records, list):
        raise ResearchError("Format hasil pencarian tidak valid.")
    references = []
    for record in records[:5]:
        if not isinstance(record, dict):
            continue
        url = safe_url(record.get("url"))
        if not url:
            continue
        references.append({"title": str(record.get("title") or "Referensi vendor")[:200],
                           "description": str(record.get("description") or "")[:800], "url": url,
                           "verification": "unverified-web-reference"})
    return {"searchedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "query": query, "city": city, "references": references,
            "note": "Referensi web bukan quote. Verifikasi tanggal, ukuran, periode sewa, availability, load-in/out, dan pajak. Tidak ada harga yang diperbarui otomatis."}
