import csv
import io
import json
import sys
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from engine import analyze
from exports import export_csv, export_proposal, safe_csv
from server import create_server
from test_engine import project


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = create_server("127.0.0.1", 0)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def request(self, path, payload=None, raw=None, headers=None):
        headers = {"Content-Type": "application/json", **(headers or {})}
        body = raw if raw is not None else json.dumps(payload).encode() if payload is not None else None
        request = Request(self.base + path, data=body, headers=headers)
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, response.read(), response.headers
        except HTTPError as response:
            return response.code, response.read(), response.headers

    def test_happy_path_bootstrap_then_analysis(self):
        status, body, _ = self.request("/api/bootstrap")
        self.assertEqual(status, 200)
        template = json.loads(body)["templates"][0]["project"]
        status, body, _ = self.request("/api/analyze", template)
        self.assertEqual(status, 200)
        report = json.loads(body)["report"]
        self.assertEqual(len(report["agents"]), 6)
        self.assertGreater(report["totals"]["hpp"], 0)
        self.assertTrue(report["review"]["requiresHumanApproval"])

    def test_invalid_margin_rejected_not_server_error(self):
        value = project()
        value["finance"]["targetMarginPercent"] = 100
        status, body, _ = self.request("/api/analyze", value)
        self.assertEqual(status, 422)
        self.assertIn("targetMarginPercent", json.loads(body)["field"])

    def test_malformed_json_rejected(self):
        self.assertEqual(self.request("/api/analyze", raw=b"{broken")[0], 400)

    def test_nonfinite_json_rejected(self):
        self.assertEqual(self.request("/api/analyze", raw=b'{"x": NaN}')[0], 400)

    def test_non_object_json_rejected(self):
        self.assertEqual(self.request("/api/analyze", raw=b"[]")[0], 400)

    def test_oversized_body_rejected(self):
        # The server rejects from Content-Length before receiving an oversized
        # upload. Sending headers alone also avoids client-side broken-pipe races.
        from http.client import HTTPConnection
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            connection.putrequest("POST", "/api/analyze")
            connection.putheader("Content-Type", "application/json")
            connection.putheader("Content-Length", "1048577")
            connection.endheaders()
            self.assertEqual(connection.getresponse().status, 413)
        finally:
            connection.close()

    def test_content_type_rejected(self):
        self.assertEqual(self.request("/api/analyze", project(), headers={"Content-Type": "text/plain"})[0], 415)

    def test_cross_origin_rejected(self):
        self.assertEqual(self.request("/api/analyze", project(), headers={"Origin": "https://evil.example"})[0], 403)

    def test_same_origin_accepted(self):
        self.assertEqual(self.request("/api/analyze", project(), headers={"Origin": self.base})[0], 200)

    def test_forwarded_preview_origin_accepted(self):
        self.assertEqual(self.request("/api/analyze", project(), headers={"Origin": "https://8080-test.e2b.app", "X-Forwarded-Host": "8080-test.e2b.app"})[0], 200)

    def test_no_frame_block_and_static_assets(self):
        status, _, headers = self.request("/")
        self.assertEqual(status, 200)
        self.assertNotIn("X-Frame-Options", headers)
        self.assertIn("nosniff", headers["X-Content-Type-Options"])
        for path in ("/app.js", "/styles.css"):
            self.assertEqual(self.request(path)[0], 200)

    def test_path_traversal_does_not_read_repository(self):
        self.assertEqual(self.request("/../config/policy.json")[0], 404)
        self.assertEqual(self.request("/%2e%2e/config/policy.json")[0], 404)

    def test_csv_export_computes_server_side(self):
        status, body, headers = self.request("/api/export", {"project": project(), "format": "csv"})
        self.assertEqual(status, 200)
        self.assertIn("attachment", headers["Content-Disposition"])
        self.assertIn("100000000", body.decode())

    def test_unknown_export_format_rejected(self):
        self.assertEqual(self.request("/api/export", {"project": project(), "format": "xlsx"})[0], 422)

    def test_disabled_research_returns_explanation(self):
        from unittest.mock import patch
        with patch.dict("os.environ", {"EO_ENABLE_RESEARCH": "0"}):
            status, body, _ = self.request("/api/market/search", {"query": "sewa LED", "city": "Jakarta"})
        self.assertEqual(status, 503)
        self.assertIn("server", json.loads(body)["error"])

    def test_stale_learning_proposal_rejected(self):
        self.assertEqual(self.request("/api/learning/apply", {"project": project(), "proposalIds": ["unknown"]})[0], 422)


class ExportSafetyTests(unittest.TestCase):
    def test_spreadsheet_injection_escaped(self):
        for value in ("=HYPERLINK(1)", "+SUM(A1)", "-1+1", "@SUM(1)", "  =cmd"):
            self.assertTrue(safe_csv(value).startswith("'"))
        self.assertEqual(safe_csv(-100), -100)

    def test_export_totals_match_report(self):
        value = project()
        report = analyze(value)
        rows = list(csv.reader(io.StringIO(export_csv(value, report).lstrip("\ufeff")), delimiter=";"))
        hpp = next(row for row in rows if row and row[0] == "HPP proyek full cost")
        self.assertEqual(int(hpp[1]), report["totals"]["hpp"])

    def test_proposal_escapes_markup_and_keeps_internal_costs_private(self):
        value = project()
        value["event"]["name"] = '<img src=x onerror="alert(1)">'
        report = analyze(value)
        result = export_proposal(value, report)
        self.assertNotIn('<img src=x', result)
        self.assertIn("&lt;img", result)
        self.assertNotIn("100.000.000", result)
        self.assertIn("DRAFT", result)


if __name__ == "__main__":
    unittest.main()
