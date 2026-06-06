"""DreamStalker FastAPI Web Application."""

import json
import threading
import requests
from pathlib import Path
from datetime import datetime
import uuid

from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel, Field

from content.session_manager import SessionManager, LearningGoal, TestResult
from core.config import get_ragflow_config
from core.services import ServiceContainer

from ragflow.goal_planner import GoalPlanner

BASE_DIR = Path(__file__).resolve().parent.parent

app = FastAPI(title="DreamStalker")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "web" / "static")), name="static")

jinja = Environment(loader=FileSystemLoader(str(BASE_DIR / "web" / "templates")), autoescape=True)

services = ServiceContainer()
sm = services.session_manager
pb = services.package_builder
tg = services.test_generator
ag = services.anchor_generator
ng = services.night_audio_generator
SESSIONS_DIR = services.sessions_dir
logger = services.logger

progress_store = {}
progress_lock = threading.Lock()


class PlanRequest(BaseModel):
    goal: str = Field(..., min_length=1, max_length=500)
    count: int = Field(20, ge=1, le=100)


class PrepareRequest(BaseModel):
    plan: dict
    hours: float = Field(7.0, ge=1.0, le=12.0)


class TestSubmitRequest(BaseModel):
    answers: list[dict]


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
    enriched = []
    for s in sessions:
        sid = s.session_id
        sdir = SESSIONS_DIR / sid
        goal_topic = s.goal.topic if hasattr(s.goal, "topic") else "Unknown"
        enriched.append({
            "id": sid,
            "goal": goal_topic,
            "created": s.created_at[:16],
            "status": s.status,
            "has_audio": (sdir / "night_session.wav").exists(),
            "has_test": (sdir / "test.json").exists(),
            "has_report": (sdir / "results.json").exists(),
        })
    return _render("dashboard.html", sessions=enriched)


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
async def create_plan(payload: PlanRequest):
    goal = payload.goal
    count = payload.count

    rf = get_ragflow_config()
    planner = GoalPlanner(
        base_url=rf["base_url"], api_key=rf["api_key"], dataset_id=rf["dataset_id"]
    )
    try:
        plan = planner.create_learning_plan(goal_description=goal, items_count=count)
    except Exception as e:
        # Graceful degradation: return fallback plan
        logger.error("RAGFlow plan failed, using fallback", error=str(e))
        items = [{"fact": f"Fact {i+1} about {goal}", "category": "general"} for i in range(min(count, 5))]
        plan = {"goal": goal, "items": items, "sources": ["fallback"], "created_at": datetime.now().isoformat()}

    pp = SESSIONS_DIR / f"plan_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    pp.parent.mkdir(parents=True, exist_ok=True)
    pp.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return JSONResponse({"plan": plan, "plan_path": str(pp)})


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    rf = get_ragflow_config()
    url = rf["base_url"].rstrip("/") + f"/api/v1/datasets/{rf['dataset_id']}/documents"
    content = await file.read()
    files = {"file": (file.filename, content, file.content_type)}
    headers = {"Authorization": f"Bearer {rf['api_key']}"}
    try:
        resp = requests.post(url, headers=headers, files=files, timeout=120)
        return JSONResponse(resp.json() if resp.ok else {"error": resp.text})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/progress/{session_id}")
async def get_progress(session_id: str):
    with progress_lock:
        p = progress_store.get(session_id, {"step": "idle", "current": 0, "total": 6, "message": "Ожидание", "percent": 0})
    return JSONResponse(p)


@app.post("/api/prepare")
async def prepare_session(payload: PrepareRequest, background_tasks: BackgroundTasks):
    plan = payload.plan
    if not plan or "items" not in plan:
        return JSONResponse({"error": "plan with items required"}, status_code=400)
    items = plan.get("items", [])
    if not items:
        return JSONResponse({"error": "plan.items must not be empty"}, status_code=400)
    goal_desc = plan.get("goal", "learning")
    pid = str(uuid.uuid4())

    # Create session immediately so user gets an ID
    goal = LearningGoal(topic=goal_desc, description=goal_desc, target_items_count=len(items))
    session = sm.create_session(goal)
    sid = session.session_id
    sdir = SESSIONS_DIR / sid
    sdir.mkdir(parents=True, exist_ok=True)

    progress_store[pid] = {"step": "queued", "current": 0, "total": 6, "message": "В очереди...", "percent": 0}

    # Run heavy work in background
    background_tasks.add_task(_build_session, sid, sdir, items, goal_desc, pid, session)

    return JSONResponse({"session_id": sid, "progress_id": pid, "message": "Session preparation started"})


def _build_session(sid, sdir, items, goal_desc, pid, session):
    """Background task: build package, tests, anchors, audio."""
    def _upd(step, current, message):
        with progress_lock:
            progress_store[pid] = {"step": step, "current": current, "total": 6, "message": message, "percent": round(current / 6 * 100)}

    try:
        _upd("Сбор пакета", 1, "Сбор пакета знаний...")
        pkg = pb.build_sleep_package(items, compress_rate=20.0)
        pb.save_package(pkg, str(sdir / "package.json"))

        _upd("Генерация тестов", 2, "Генерация тестов...")
        ts = tg.generate_full_test_suite(items, tests_per_type=3)
        tg.save_test_suite(ts, str(sdir / "test_suite.json"))
        ti = ts.get("tests", [])
        (sdir / "test.json").write_text(json.dumps(ti, ensure_ascii=False, indent=2), encoding="utf-8")

        _upd("Назначение якорей", 3, "Назначение якорей...")
        ia = ag.assign_anchors(items)

        _upd("Генерация аудио", 4, "Генерация аудио...")
        inst = pb.build_installation_text(goal_desc, len(items))
        ap = str(sdir / "night_session.wav")
        ng.generate_falling_asleep_phase(items=ia, installation_text=inst, duration_min=1.0, output_path=ap)

        _upd("Сохранение", 5, "Сохранение сессии...")
        sm.save_audio(session, ap)
        sm.save_package(session, ia)
        sm.save_test(session, ti)

        progress_store[pid] = {"step": "done", "current": 6, "total": 6, "message": "Готово", "percent": 100}
    except Exception as e:
        logger.error("Session build failed", session_id=sid, error=str(e))
        progress_store[pid] = {"step": "failed", "current": 0, "total": 6, "message": f"Ошибка: {e}", "percent": 0}


@app.get("/api/sessions")
async def list_sessions():
    return JSONResponse({"sessions": [_sd(s) for s in sm.list_sessions()]})


@app.get("/api/audio/{sid}")
async def serve_audio(sid: str):
    wav = SESSIONS_DIR / sid / "night_session.wav"
    if not wav.exists(): return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(str(wav), media_type="audio/wav", filename=sid + "_night.wav")


@app.post("/api/test/{sid}/submit")
async def submit_test(sid: str, payload: TestSubmitRequest):
    answers = payload.answers
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
