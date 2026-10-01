import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from market import ResearchError, ResearchUnavailable, search_market
from validation import ValidationError


class MarketTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"FIRECRAWL_API_KEY": "test-server-only-key", "EO_ENABLE_RESEARCH": "1", "FIRECRAWL_API_URL": "https://api.firecrawl.dev"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_v2_request_and_provenance(self):
        def transport(request):
            self.assertEqual(request.full_url, "https://api.firecrawl.dev/v2/search")
            self.assertEqual(request.get_header("Authorization"), "Bearer test-server-only-key")
            payload = json.loads(request.data)
            self.assertEqual(payload["country"], "ID")
            self.assertEqual(payload["sources"], ["web"])
            return {"success": True, "data": {"web": [{"url": "https://vendor.example/led", "title": "LED vendor", "description": "Harga tergantung scope"}]}}
        result = search_market("sewa LED", "Jakarta", transport=transport)
        self.assertEqual(result["references"][0]["verification"], "unverified-web-reference")
        self.assertNotIn("test-server-only-key", json.dumps(result))

    def test_bad_urls_are_dropped(self):
        response = {"success": True, "data": {"web": [{"url": "javascript:alert(1)"}, {"url": "https://user:secret@host"}, {"url": "https://vendor.example"}]}}
        result = search_market("audio", "Jakarta", transport=lambda _: response)
        self.assertEqual(len(result["references"]), 1)

    def test_upstream_auth_body_is_not_exposed(self):
        def transport(_):
            raise HTTPError("https://api.firecrawl.dev", 401, "secret payload test-server-only-key", {}, None)
        with self.assertRaises(ResearchError) as caught:
            search_market("audio", "Jakarta", transport=transport)
        self.assertNotIn("test-server-only-key", str(caught.exception))

    def test_transport_failure_sanitized(self):
        def transport(_):
            raise URLError("credential in network error")
        with self.assertRaises(ResearchError) as caught:
            search_market("audio", "Jakarta", transport=transport)
        self.assertNotIn("credential", str(caught.exception))

    def test_disabled_research_cannot_spend_credits(self):
        with patch.dict(os.environ, {"EO_ENABLE_RESEARCH": "0"}):
            with self.assertRaises(ResearchUnavailable):
                search_market("audio", "Jakarta", transport=lambda _: self.fail("must not call upstream"))

    def test_invalid_query_rejected(self):
        with self.assertRaises(ValidationError):
            search_market("", "Jakarta")

    def test_invalid_upstream_response(self):
        for response in ({"success": False}, {"success": True, "data": {"web": {}}}, []):
            with self.assertRaises(ResearchError):
                search_market("audio", "Jakarta", transport=lambda _: response)

    def test_base_url_with_v2_is_not_duplicated(self):
        with patch.dict(os.environ, {"FIRECRAWL_API_URL": "https://api.firecrawl.dev/v2/"}):
            def transport(request):
                self.assertEqual(request.full_url, "https://api.firecrawl.dev/v2/search")
                return {"success": True, "data": {"web": []}}
            self.assertEqual(search_market("audio", "Jakarta", transport=transport)["references"], [])


if __name__ == "__main__":
    unittest.main()
