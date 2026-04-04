"""DreamStalker FastAPI Web Application."""

import json
import requests
from pathlib import Path
from datetime import datetime
import uuid

from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader

from content.session_manager import SessionManager, LearningGoal, TestResult
from content.package_builder import PackageBuilder
from content.test_generator import TestGenerator
from core.audio_generator import NightAudioGenerator
from core.anchor_generator import AnchorGenerator
from core.logger import DreamLogger

BASE_DIR = Path(__file__).resolve().parent.parent
SESSIONS_DIR = BASE_DIR / "data" / "sessions"
RAGFLOW_BASE = "http://192.168.0.156:9380/api/v1/datasets"
RAGFLOW_KEY = "ragflow-UJmyXeAW4Eb6OcWNCxc8oq_Q92CTUbZWGtz2hXHqRq8"
DATASET_ID = "57e3405527a111f1ad97929ce6da87e6"

app = FastAPI(title="DreamStalker")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "web" / "static")), name="static")

jinja = Environment(loader=FileSystemLoader(str(BASE_DIR / "web" / "templates")), autoescape=True)

sm = SessionManager(str(SESSIONS_DIR))
pb = PackageBuilder()
tg = TestGenerator()
ag = AnchorGenerator()
ng = NightAudioGenerator()

progress_store = {}
logger = DreamLogger()


def _render(name, **ctx):
    t = jinja.get_template(name)
    return HTMLResponse(t.render(**ctx))


def _sd(s):
    if s is None: return None
    if isinstance(s, dict): return s
    g = s.goal
    return {"session_id": s.session_id, "goal": {"topic": g.topic} if hasattr(g, "topic") else str(g), "status": s.status, "created_at": s.created_at}


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    sessions = sm.list_sessions()
    for s in sessions:
        sid = s.get("session_id", "")
        sdir = SESSIONS_DIR / sid
        s["id"] = sid
        s["goal"] = s.get("goal", {}).get("topic", "Unknown")
        s["created"] = s.get("created_at", "")[:16]
        s["has_audio"] = (sdir / "night_session.wav").exists()
        s["has_test"] = (sdir / "test.json").exists()
        s["has_report"] = (sdir / "results.json").exists()
    return _render("dashboard.html", sessions=sessions)


@app.get("/prepare", response_class=HTMLResponse)
async def prepare_page():
    return _render("prepare.html")


@app.get("/session/{sid}", response_class=HTMLResponse)
async def session_detail(sid: str):
    session = sm.get_session(sid)
    if not session: return HTMLResponse("<h1>Not found</h1>", status_code=404)
    sdir = SESSIONS_DIR / sid
    items = []
    pkg = sdir / "package.json"
    if pkg.exists(): items = json.loads(pkg.read_text(encoding="utf-8"))
    return _render("session.html", session=_sd(session), items=items[:10], total_items=len(items), audio_exists=(sdir / "night_session.wav").exists())


@app.get("/test/{sid}", response_class=HTMLResponse)
async def test_page(sid: str):
    session = sm.get_session(sid)
    if not session: return HTMLResponse("<h1>Not found</h1>", status_code=404)
    sdir = SESSIONS_DIR / sid
    tests = []
    tp = sdir / "test.json"
    if tp.exists(): tests = json.loads(tp.read_text(encoding="utf-8"))
    return _render("test.html", session=_sd(session), tests_json=json.dumps(tests, ensure_ascii=False), total_tests=len(tests))


@app.get("/report/{sid}", response_class=HTMLResponse)
async def report_page(sid: str):
    session = sm.get_session(sid)
    if not session: return HTMLResponse("<h1>Not found</h1>", status_code=404)
    sdir = SESSIONS_DIR / sid
    report_data = None
    rp = sdir / "results.json"
    if rp.exists(): report_data = json.loads(rp.read_text(encoding="utf-8"))
    return _render("report.html", session=_sd(session), report=report_data)


@app.post("/api/plan")
async def create_plan(payload: dict):
    goal = payload.get("goal", "")
    count = payload.get("count", 20)
    if not goal: return JSONResponse({"error": "goal required"}, status_code=400)
    try:
        hdr = {"Authorization": "Bearer " + RAGFLOW_KEY, "Content-Type": "application/json"}
        resp = requests.post(RAGFLOW_BASE + "/" + DATASET_ID + "/retrieve", headers=hdr, json={"question": goal, "page_size": count}, timeout=30)
        chunks = resp.json().get("data", []) if resp.ok else []
    except Exception: chunks = []
    items = []
    seen = set()
    for chunk in chunks[:count]:
        text = chunk.get("content", "") if isinstance(chunk, dict) else str(chunk)
        for sent in [s.strip() for s in text.split(".") if len(s.strip()) > 20][:2]:
            if sent not in seen and len(items) < count: seen.add(sent); items.append({"fact": sent, "category": "general"})
    if not items: items = [{"fact": "Fact " + str(i+1) + " about " + goal, "category": "general"} for i in range(min(count, 5))]
    plan = {"goal": goal, "items": items, "sources": ["RAGFlow"], "created_at": datetime.now().isoformat()}
    pp = SESSIONS_DIR / ("plan_" + datetime.now().strftime("%Y%m%d_%H%M") + ".json")
    pp.parent.mkdir(parents=True, exist_ok=True)
    pp.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return JSONResponse({"plan": plan, "plan_path": str(pp)})


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    url = RAGFLOW_BASE + "/" + DATASET_ID + "/documents"
    content = await file.read()
    files = {"file": (file.filename, content, file.content_type)}
    headers = {"Authorization": "Bearer " + RAGFLOW_KEY}
    try:
        resp = requests.post(url, headers=headers, files=files, timeout=120)
        return JSONResponse(resp.json() if resp.ok else {"error": resp.text})
    except Exception as e: return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/progress/{session_id}")
async def get_progress(session_id: str):
    p = progress_store.get(session_id, {"step": "idle", "current": 0, "total": 6, "message": "Ожидание", "percent": 0})
    return JSONResponse(p)


@app.post("/api/prepare")
async def prepare_session(payload: dict):
    plan = payload.get("plan", {})
    if not plan: return JSONResponse({"error": "plan required"}, status_code=400)
    items = plan.get("items", [])
    goal_desc = plan.get("goal", "learning")
    pid = str(uuid.uuid4())

    def _upd(step, current, message):
        progress_store[pid] = {"step": step, "current": current, "total": 6, "message": message, "percent": round(current / 6 * 100)}

    _upd("Создание сессии", 1, "Создание сессии...")
    goal = LearningGoal(topic=goal_desc, description=goal_desc, target_items_count=len(items))
    session = sm.create_session(goal)
    sid = session.session_id
    sdir = SESSIONS_DIR / sid
    sdir.mkdir(parents=True, exist_ok=True)

    _upd("Сбор пакета", 2, "Сбор пакета знаний...")
    pkg = pb.build_sleep_package(items, compress_rate=20.0)
    pb.save_package(pkg, str(sdir / "package.json"))

    _upd("Генерация тестов", 3, "Генерация тестов...")
    ts = tg.generate_full_test_suite(items, tests_per_type=3)
    tg.save_test_suite(ts, str(sdir / "test_suite.json"))
    ti = ts.get("tests", [])
    (sdir / "test.json").write_text(json.dumps(ti, ensure_ascii=False, indent=2), encoding="utf-8")

    _upd("Назначение якорей", 4, "Назначение якорей...")
    ia = ag.assign_anchors(items)

    _upd("Генерация аудио", 5, "Генерация аудио...")
    inst = pb.build_installation_text(goal_desc, len(items))
    ap = str(sdir / "night_session.wav")
    ng.generate_falling_asleep_phase(items=ia, installation_text=inst, duration_min=1.0, output_path=ap)

    _upd("Сохранение", 6, "Сохранение сессии...")
    sm.save_audio(session, ap)
    sm.save_package(session, ia)
    sm.save_test(session, ti)

    progress_store[pid] = {"step": "done", "current": 6, "total": 6, "message": "Готово", "percent": 100}
    return JSONResponse({"session_id": sid, "progress_id": pid, "items_count": len(items), "tests_count": len(ti), "audio_path": ap})


@app.get("/api/sessions")
async def list_sessions():
    return JSONResponse({"sessions": [_sd(s) for s in sm.list_sessions()]})


@app.get("/api/audio/{sid}")
async def serve_audio(sid: str):
    wav = SESSIONS_DIR / sid / "night_session.wav"
    if not wav.exists(): return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(str(wav), media_type="audio/wav", filename=sid + "_night.wav")


@app.post("/api/test/{sid}/submit")
async def submit_test(sid: str, payload: dict):
    answers = payload.get("answers", [])
    sdir = SESSIONS_DIR / sid
    tp = sdir / "test.json"
    if not tp.exists(): return JSONResponse({"error": "not found"}, status_code=404)
    tests = json.loads(tp.read_text(encoding="utf-8"))
    tmap = {str(t.get("item_id", "")): t for t in tests}
    results, cc = [], 0
    for ans in answers:
        iid = str(ans.get("item_id", ""))
        ua = ans.get("answer", "").strip().lower()
        ti = tmap.get(iid, {})
        ca = ti.get("answer", "").strip().lower()
        ok = ((ua == ca) or (ua in ca) or (ca in ua)) if ca else False
        if ok: cc += 1
        results.append(TestResult(session_id=sid, item_id=iid, question=ti.get("question", ""), correct_answer=ti.get("answer", ""), user_answer=ans.get("answer", ""), is_correct=ok, response_time_sec=0.0))
    sm.save_test_results(results)
    total = len(answers)
    score = round(cc / total * 100, 1) if total > 0 else 0
    return JSONResponse({"score": score, "correct": cc, "total": total})


@app.get("/api/report/{sid}")
async def get_report(sid: str):
    sdir = SESSIONS_DIR / sid
    rp = sdir / "results.json"
    if rp.exists():
        data = json.loads(rp.read_text(encoding="utf-8"))
        total = len(data)
        correct = sum(1 for r in data if r.get("is_correct"))
        return JSONResponse({"session_id": sid, "total": total, "correct": correct, "accuracy": round(correct / total * 100, 1) if total else 0, "results": data})
    return JSONResponse({"session_id": sid, "total": 0, "correct": 0, "accuracy": 0, "results": []})
