"""FastAPI 后端测试：注入 fake 依赖验证各路由（Phase 5.2）。"""

from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from pokemon_battle_assistant.api.app import create_app
from pokemon_battle_assistant.modules.orchestrator import Orchestrator


class FakeBuilder:
    def generate_team(self, requirement: str, format: str = "gen9bssregi"):
        return SimpleNamespace(
            team={"name": "V0", "format": format, "team": []},
            valid=True,
            reasoning="r0",
            validation_errors=[],
        )

    def iterate_team(self, team: dict, report: dict, format: str = "gen9bssregi"):
        return SimpleNamespace(
            team={**team, "name": "V1"},
            valid=True,
            reasoning="r1",
            validation_errors=[],
        )


class FakeLabRunner:
    async def run(self, config):
        stats = {
            "total_battles": 1,
            "wins": 1,
            "losses": 0,
            "errors": 0,
            "win_rate": 1.0,
            "by_opponent": {},
        }
        return SimpleNamespace(stats=stats, results=[])


class FakeReport:
    def __init__(self, analysis_id: str) -> None:
        self.analysis_id = analysis_id
        self.strategy_advice = {"summary": f"总结 {analysis_id}", "team_builder_feedback": ["反馈"]}
        self.opponent_profile = {"style": "均衡"}

    def to_dict(self):
        return {
            "analysis_id": self.analysis_id,
            "strategy_advice": self.strategy_advice,
            "opponent_profile": self.opponent_profile,
        }


class FakeAnalysisEngine:
    def __init__(self) -> None:
        self.results: dict[str, FakeReport] = {}

    async def analyze_battle(self, battle_tag: str, depth: str = "full", *, record=None) -> str:
        analysis_id = f"aid-{battle_tag}"
        self.results[analysis_id] = FakeReport(analysis_id)
        return analysis_id

    def get_result(self, analysis_id: str) -> FakeReport:
        return self.results[analysis_id]  # KeyError -> 404

    def list_analyses(self):
        return [{"analysis_id": key} for key in self.results]


async def fake_battle_runner(payload):
    return {"battle_tag": "bat-api", "turns": 3, "won": True, "files": {}}


class ApiTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.builder = FakeBuilder()
        self.lab = FakeLabRunner()
        self.engine = FakeAnalysisEngine()
        self.orchestrator = Orchestrator(
            team_builder=self.builder,
            lab_runner=self.lab,
            analysis_engine=self.engine,
            output_root=self.tmp,
        )
        app = create_app(
            team_builder=self.builder,
            lab_runner=self.lab,
            analysis_engine=self.engine,
            orchestrator=self.orchestrator,
            battle_runner=fake_battle_runner,
            teams_root=self.tmp / "teams",
        )
        client_cm = TestClient(app)
        self.client = client_cm.__enter__()
        self.addCleanup(client_cm.__exit__, None, None, None)

    def _wait_job(self, path: str, tries: int = 100) -> dict:
        for _ in range(tries):
            data = self.client.get(path).json()
            if data.get("status") != "running":
                return data
            time.sleep(0.02)
        raise AssertionError(f"任务未完成：{path}")

    def test_health_and_formats(self):
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "ok")
        resp = self.client.get("/api/formats")
        ids = [fmt["id"] for fmt in resp.json()["formats"]]
        self.assertIn("gen9bssregi", ids)
        self.assertIn("gen9vgc2026regi", ids)

    def test_teams_crud_and_validate(self):
        template = {"name": "apiteam", "format": "gen9bssregi", "team": [{"species": "pikachu"}]}
        resp = self.client.post("/api/teams", json={"name": "apiteam", "template": template})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["name"], "apiteam")

        dup = self.client.post("/api/teams", json={"name": "apiteam", "template": template})
        self.assertEqual(dup.status_code, 409)

        bad = self.client.post("/api/teams", json={"name": "bad", "template": {"team": []}})
        self.assertEqual(bad.status_code, 400)

        listing = self.client.get("/api/teams").json()["teams"]
        self.assertEqual([item["name"] for item in listing], ["apiteam"])

        detail = self.client.get("/api/teams/apiteam")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["team"]["format"], "gen9bssregi")

        missing = self.client.get("/api/teams/nope")
        self.assertEqual(missing.status_code, 404)

        validated = self.client.post("/api/teams/apiteam/validate", json={"format": "gen9bssregi"})
        self.assertEqual(validated.status_code, 200)
        self.assertIn("valid", validated.json())

        deleted = self.client.delete("/api/teams/apiteam")
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(self.client.get("/api/teams/apiteam").status_code, 404)

    def test_team_builder_generate_iterate_history(self):
        resp = self.client.post(
            "/api/team-builder/generate", json={"requirement": "电系快攻", "format": "gen9bssregi"}
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertTrue(payload["valid"])
        self.assertEqual(payload["team"]["name"], "V0")

        iterate = self.client.post(
            "/api/team-builder/iterate",
            json={"team": payload["team"], "report": {"summary": "复盘"}, "format": "gen9bssregi"},
        )
        self.assertEqual(iterate.status_code, 200)
        self.assertEqual(iterate.json()["team"]["name"], "V1")

        history = self.client.get("/api/team-builder/history").json()["history"]
        self.assertEqual(len(history), 2)
        self.assertEqual([item["action"] for item in history], ["generate", "iterate"])

    def test_battle_job_lifecycle(self):
        resp = self.client.post("/api/battle/start", json={"template": "xiaobian"})
        self.assertEqual(resp.status_code, 200)
        job_id = resp.json()["job_id"]

        status = self._wait_job(f"/api/battle/{job_id}/status")
        self.assertEqual(status["status"], "done")

        result = self.client.get(f"/api/battle/{job_id}/result").json()
        self.assertEqual(result["battle_tag"], "bat-api")
        self.assertTrue(result["won"])

        missing = self.client.get("/api/battle/nope/status")
        self.assertEqual(missing.status_code, 404)

    def test_lab_job_and_report(self):
        resp = self.client.post(
            "/api/lab/start", json={"team": "t", "opponents": ["a"], "battles_per_opponent": 1}
        )
        self.assertEqual(resp.status_code, 200)
        job_id = resp.json()["job_id"]

        self._wait_job(f"/api/lab/{job_id}/status")
        report = self.client.get(f"/api/lab/{job_id}/report").json()
        self.assertEqual(report["stats"]["win_rate"], 1.0)

    def test_analysis_submit_and_get(self):
        resp = self.client.post("/api/analysis/battle/bat-x", json={"record": {"battle": {}}})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["analysis_id"], "aid-bat-x")

        listing = self.client.get("/api/analysis/list").json()["analyses"]
        self.assertEqual(listing, [{"analysis_id": "aid-bat-x"}])

        detail = self.client.get("/api/analysis/aid-bat-x")
        self.assertEqual(detail.status_code, 200)
        self.assertIn("strategy_advice", detail.json())

        missing = self.client.get("/api/analysis/aid-nope")
        self.assertEqual(missing.status_code, 404)

    def test_orchestrator_start_status_confirm(self):
        resp = self.client.post(
            "/api/orchestrator/start",
            json={
                "requirement": "电系快攻",
                "opponents": ["rival"],
                "iterations": 2,
                "auto": False,
                "battles": 1,
                "output_root": str(self.tmp),
            },
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        job_id, run_id = body["job_id"], body["run_id"]

        self._wait_job(f"/api/orchestrator/jobs/{job_id}")
        status = self.client.get(f"/api/orchestrator/{run_id}/status").json()
        self.assertEqual(status["state"], "waiting_confirm")
        self.assertEqual(status["current_iteration"], 1)

        confirmed = self.client.post(f"/api/orchestrator/{run_id}/confirm")
        self.assertEqual(confirmed.status_code, 200)
        self.assertEqual(confirmed.json()["state"], "completed")
        self.assertEqual(confirmed.json()["current_iteration"], 2)

        again = self.client.post(f"/api/orchestrator/{run_id}/confirm")
        self.assertEqual(again.status_code, 409)

        history = self.client.get(f"/api/orchestrator/{run_id}/history").json()["iterations"]
        self.assertEqual(len(history), 2)

        missing = self.client.get("/api/orchestrator/run-nope/status")
        self.assertEqual(missing.status_code, 404)


if __name__ == "__main__":
    unittest.main()
