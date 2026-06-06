"""DreamStalker API v1 — versioned endpoints."""

import json
import threading
import uuid
from datetime import datetime
from pathlib import Path

import requests
from fastapi import APIRouter, BackgroundTasks, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse

from content.session_manager import LearningGoal, TestResult
from core.config import get_ragflow_config
from ragflow.goal_planner import GoalPlanner

router = APIRouter(prefix="/api/v1", tags=["v1"])

# These are injected by the main app at startup
_sm = None
_pb = None
_tg = None
_ag = None
_ng = None
_sessions_dir = None
_logger = None
_progress_store = {}
_progress_lock = threading.Lock()


def configure(sm, pb, tg, ag, ng, sessions_dir, logger):
    """Wire service container into the router (called from web/app.py)."""
    global _sm, _pb, _tg, _ag, _ng, _sessions_dir, _logger
    _sm = sm
    _pb = pb
    _tg = tg
    _ag = ag
    _ng = ng
    _sessions_dir = sessions_dir
    _logger = logger


@router.get("/sessions")
async def list_sessions():
    return JSONResponse({"sessions": [_sd(s) for s in _sm.list_sessions()]})


@router.post("/plan")
async def create_plan(payload: dict):
    from pydantic import BaseModel, Field
    from fastapi import HTTPException

    class PlanReq(BaseModel):
        goal: str = Field(..., min_length=1, max_length=500)
        count: int = Field(20, ge=1, le=100)

    try:
        req = PlanReq(**payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    rf = get_ragflow_config()
    planner = GoalPlanner(
        base_url=rf["base_url"], api_key=rf["api_key"], dataset_id=rf["dataset_id"]
    )
    try:
        plan = planner.create_learning_plan(goal_description=req.goal, items_count=req.count)
    except Exception as e:
        _logger.error(f"RAGFlow plan failed: {e}")
        items = [{"fact": f"Fact {i+1} about {req.goal}", "category": "general"} for i in range(min(req.count, 5))]
        plan = {"goal": req.goal, "items": items, "sources": ["fallback"], "created_at": datetime.now().isoformat()}

    pp = _sessions_dir / f"plan_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    pp.parent.mkdir(parents=True, exist_ok=True)
    pp.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return JSONResponse({"plan": plan, "plan_path": str(pp)})


@router.post("/upload")
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


@router.post("/prepare")
async def prepare_session(payload: dict, background_tasks: BackgroundTasks):
    from pydantic import BaseModel, Field
    from fastapi import HTTPException

    class PrepareReq(BaseModel):
        plan: dict
        hours: float = Field(7.0, ge=1.0, le=12.0)

    try:
        req = PrepareReq(**payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    plan = req.plan
    if not plan or "items" not in plan:
        raise HTTPException(status_code=400, detail="plan with items required")
    items = plan.get("items", [])
    if not items:
        raise HTTPException(status_code=400, detail="plan.items must not be empty")
    goal_desc = plan.get("goal", "learning")
    pid = str(uuid.uuid4())

    goal = LearningGoal(topic=goal_desc, description=goal_desc, target_items_count=len(items))
    session = _sm.create_session(goal)
    sid = session.session_id
    sdir = _sessions_dir / sid
    sdir.mkdir(parents=True, exist_ok=True)

    with _progress_lock:
        _progress_store[pid] = {"step": "queued", "current": 0, "total": 6, "message": "В очереди...", "percent": 0}

    background_tasks.add_task(_build_session, sid, sdir, items, goal_desc, pid, session)
    return JSONResponse({"session_id": sid, "progress_id": pid, "message": "Session preparation started"})


def _build_session(sid, sdir, items, goal_desc, pid, session):
    def _upd(step, current, message):
        with _progress_lock:
            _progress_store[pid] = {"step": step, "current": current, "total": 6, "message": message, "percent": round(current / 6 * 100)}

    try:
        _upd("Сбор пакета", 1, "Сбор пакета знаний...")
        pkg = _pb.build_sleep_package(items, compress_rate=20.0)
        _pb.save_package(pkg, str(sdir / "package.json"))

        _upd("Генерация тестов", 2, "Генерация тестов...")
        ts = _tg.generate_full_test_suite(items, tests_per_type=3)
        _tg.save_test_suite(ts, str(sdir / "test_suite.json"))
        ti = ts.get("tests", [])
        (sdir / "test.json").write_text(json.dumps(ti, ensure_ascii=False, indent=2), encoding="utf-8")

        _upd("Назначение якорей", 3, "Назначение якорей...")
        ia = _ag.assign_anchors(items)

        _upd("Генерация аудио", 4, "Генерация аудио...")
        inst = _pb.build_installation_text(goal_desc, len(items))
        ap = str(sdir / "night_session.wav")
        _ng.generate_falling_asleep_phase(items=ia, installation_text=inst, duration_min=1.0, output_path=ap)

        _upd("Сохранение", 5, "Сохранение сессии...")
        _sm.save_audio(session, ap)
        _sm.save_package(session, ia)
        _sm.save_test(session, ti)
    except Exception as e:
        _logger.error(f"Build session failed: {e}")
        with _progress_lock:
            _progress_store[pid] = {"step": "error", "current": 0, "total": 6, "message": str(e), "percent": 0}
        return

    with _progress_lock:
        _progress_store[pid] = {"step": "done", "current": 6, "total": 6, "message": "Готово", "percent": 100}


@router.get("/progress/{id}")
async def get_progress(id: str):
    with _progress_lock:
        p = _progress_store.get(id, {"step": "idle", "current": 0, "total": 6, "message": "Ожидание", "percent": 0})
    return JSONResponse(p)


@router.get("/audio/{sid}")
async def serve_audio(sid: str):
    wav = _sessions_dir / sid / "night_session.wav"
    if not wav.exists():
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(str(wav), media_type="audio/wav", filename=f"{sid}_night.wav")


@router.post("/test/{sid}/submit")
async def submit_test(sid: str, payload: dict):
    from pydantic import BaseModel
    from fastapi import HTTPException

    class TestReq(BaseModel):
        answers: list[dict]

    try:
        req = TestReq(**payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    answers = req.answers
    sdir = _sessions_dir / sid
    tp = sdir / "test.json"
    if not tp.exists():
        return JSONResponse({"error": "not found"}, status_code=404)
    tests = json.loads(tp.read_text(encoding="utf-8"))
    tmap = {str(t.get("item_id", "")): t for t in tests}
    results, cc = [], 0
    for ans in answers:
        iid = str(ans.get("item_id", ""))
        ua = ans.get("answer", "").strip().lower()
        ti = tmap.get(iid, {})
        ca = ti.get("answer", "").strip().lower()
        ok = ((ua == ca) or (ua in ca) or (ca in ua)) if ca else False
        if ok:
            cc += 1
        results.append(TestResult(session_id=sid, item_id=iid, question=ti.get("question", ""),
                                  correct_answer=ti.get("answer", ""), user_answer=ans.get("answer", ""),
                                  is_correct=ok, response_time_sec=0.0))
    _sm.save_test_results(results)
    total = len(answers)
    score = round(cc / total * 100, 1) if total > 0 else 0
    return JSONResponse({"score": score, "correct": cc, "total": total})


@router.get("/report/{sid}")
async def get_report(sid: str):
    sdir = _sessions_dir / sid
    rp = sdir / "results.json"
    if rp.exists():
        data = json.loads(rp.read_text(encoding="utf-8"))
        total = len(data)
        correct = sum(1 for r in data if r.get("is_correct"))
        return JSONResponse({
            "session_id": sid,
            "total": total,
            "correct": correct,
            "accuracy": round(correct / total * 100, 1) if total else 0,
            "results": data,
        })
    return JSONResponse({"session_id": sid, "total": 0, "correct": 0, "accuracy": 0, "results": []})


def _sd(s):
    if s is None:
        return None
    if isinstance(s, dict):
        return s
    g = s.goal
    return {
        "session_id": s.session_id,
        "goal": {"topic": g.topic} if hasattr(g, "topic") else str(g),
        "status": s.status,
        "created_at": s.created_at,
    }
