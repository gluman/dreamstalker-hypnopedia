"""DreamStalker web interface tests."""

import time
import requests


def _retry_get(url, max_retries=3, delay=2):
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, timeout=30)
            if resp.status_code == 200:
                return resp
        except Exception:
            pass
        time.sleep(delay)
    return requests.get(url, timeout=30)


class TestDashboard:
    def test_dashboard_loads(self, page, base_url):
        page.goto(base_url + "/")
        heading = page.get_by_text("Sessions")
        heading.wait_for()
        assert heading.is_visible()

    def test_prepare_page_loads(self, page, base_url):
        page.goto(base_url + "/prepare")
        page.wait_for_load_state("networkidle")
        body = page.locator("body")
        assert body.is_visible()


class TestAPI:
    def test_api_sessions(self, base_url):
        resp = _retry_get(base_url + "/api/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert "sessions" in data
        assert isinstance(data["sessions"], list)

    def test_create_plan(self, base_url):
        resp = requests.post(
            base_url + "/api/plan",
            json={"goal": "test", "count": 5},
            timeout=30,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "plan" in data
        plan = data["plan"]
        assert plan["goal"] == "test"
        assert isinstance(plan["items"], list)
        assert len(plan["items"]) > 0

    def test_full_workflow(self, base_url):
        plan_resp = requests.post(
            base_url + "/api/plan",
            json={"goal": "quantum mechanics basics", "count": 3},
            timeout=30,
        )
        assert plan_resp.status_code == 200
        plan = plan_resp.json()["plan"]

        prep_resp = requests.post(
            base_url + "/api/prepare",
            json={"plan": plan},
            timeout=180,
        )
        assert prep_resp.status_code == 200
        prep_data = prep_resp.json()
        assert "session_id" in prep_data
        sid = prep_data["session_id"]

        audio_resp = requests.get(base_url + "/api/audio/" + sid, timeout=30)
        assert audio_resp.status_code == 200
        assert audio_resp.headers["content-type"].startswith("audio/")

    def test_report_endpoint(self, base_url):
        sessions_resp = _retry_get(base_url + "/api/sessions")
        if sessions_resp.status_code != 200:
            return

        sessions = sessions_resp.json()["sessions"]
        if not sessions:
            return

        sid = sessions[0].get("session_id") or sessions[0].get("id")
        if not sid:
            return

        report_resp = requests.get(base_url + "/api/report/" + sid, timeout=10)
        assert report_resp.status_code == 200
        data = report_resp.json()
        assert data["session_id"] == sid
