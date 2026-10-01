"""Coordinator: validate -> immutable cost snapshot -> six parallel agents -> review."""

import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path
from types import MappingProxyType

from agents import AGENTS, AGENT_ORDER
from finance import calculate
from learning import build_proposals
from validation import validate_project

ROOT = Path(__file__).resolve().parents[1]


def load_policy():
    return json.loads((ROOT / "config" / "policy.json").read_text(encoding="utf-8"))


def freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({key: freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(freeze(item) for item in value)
    return value


def plain(value):
    if isinstance(value, (dict, MappingProxyType)):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(item) for item in value]
    return value


def analyze(payload, today=None, policy=None):
    started = time.perf_counter()
    today = today or date.today()
    policy = policy or load_policy()
    project = validate_project(payload, today=today)
    snapshot = freeze(project)
    financial = calculate(snapshot, policy, today)
    frozen_financial = freeze(financial)

    def run(agent_id):
        agent_start = time.perf_counter()
        report = AGENTS[agent_id](snapshot, frozen_financial, today)
        report["durationMs"] = round((time.perf_counter() - agent_start) * 1000, 2)
        return report

    # Cost arithmetic is shared, not recalculated by probabilistic agents. All domain
    # agents read the SAME frozen revision; no races or circular pricing dependencies.
    with ThreadPoolExecutor(max_workers=6, thread_name_prefix="eo-domain") as pool:
        futures = {agent_id: pool.submit(run, agent_id) for agent_id in AGENT_ORDER}
        reports = [futures[agent_id].result() for agent_id in AGENT_ORDER]
    insights = []
    for report in reports:
        for item in report["insights"]:
            insights.append({**item, "agentId": report["id"], "agentName": report["name"]})
    severity = {"critical": 0, "warning": 1, "success": 2, "info": 3}
    insights.sort(key=lambda item: severity[item["level"]])
    criticals = sum(i["level"] == "critical" for i in insights)
    warnings = sum(i["level"] == "warning" for i in insights)
    readiness = "blocked" if criticals else "review" if warnings else "ready-internal"
    learning = build_proposals(snapshot, policy, today)
    return plain({"schemaVersion": 1, "policyVersion": policy["version"],
                  "analyzedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  "asOf": today.isoformat(), "event": project["event"], **financial,
                  "agents": reports, "insights": insights, "learning": learning,
                  "review": {"status": readiness, "criticalCount": criticals,
                             "warningCount": warnings, "requiresHumanApproval": True,
                             "note": "Kalkulasi rule-based, bukan LLM. Wajib review quote, scope, pajak, dan persetujuan manusia sebelum proposal dikirim."},
                  "execution": {"mode": "parallel-rules", "agentCount": 6, "dependency": "validated-cost-snapshot",
                                "durationMs": round((time.perf_counter() - started) * 1000, 2)}})
