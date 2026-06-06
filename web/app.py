"""DreamStalker FastAPI Web Application.

API v1 endpoints are defined in web/routers/v1.py.
Legacy /api/* endpoints are kept as deprecated shims for backward compatibility.
"""

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader

from core.services import ServiceContainer
from web.routers import v1 as v1_router

BASE_DIR = Path(__file__).resolve().parent.parent

app = FastAPI(
    title="DreamStalker",
    version="1.0.0",
    description="Hypnopedia learning system — sleep-based knowledge encoding",
)

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

# Service container — single source of truth
services = ServiceContainer()
sm = services.session_manager
SESSIONS_DIR = services.sessions_dir
logger = services.logger

# Wire versioned router
v1_router.configure(
    sm=sm,
    pb=services.package_builder,
    tg=services.test_generator,
    ag=services.anchor_generator,
    ng=services.night_audio_generator,
    sessions_dir=SESSIONS_DIR,
    logger=logger,
)
app.include_router(v1_router.router)


# --- Legacy /api/* shims (deprecated) -------------------------------------
# These forward to v1 handlers for backward compatibility.
from fastapi import Request
from fastapi.responses import JSONResponse

@app.get("/api/sessions", deprecated=True)
async def _legacy_sessions(request: Request):
    return await v1_router.list_sessions()

@app.post("/api/plan", deprecated=True)
async def _legacy_plan(request: Request):
    return await v1_router.create_plan(await request.json())

@app.post("/api/prepare", deprecated=True)
async def _legacy_prepare(request: Request, background_tasks=None):
    from fastapi import BackgroundTasks
    bg = background_tasks or BackgroundTasks()
    return await v1_router.prepare_session(await request.json(), bg)

@app.get("/api/progress/{id}", deprecated=True)
async def _legacy_progress(id: str):
    return await v1_router.get_progress(id)

@app.get("/api/audio/{sid}", deprecated=True)
async def _legacy_audio(sid: str):
    return await v1_router.serve_audio(sid)

@app.post("/api/test/{sid}/submit", deprecated=True)
async def _legacy_test_submit(sid: str, request: Request):
    return await v1_router.submit_test(sid, await request.json())

@app.get("/api/report/{sid}", deprecated=True)
async def _legacy_report(sid: str):
    return await v1_router.get_report(sid)

@app.post("/api/upload", deprecated=True)
async def _legacy_upload(request: Request):
    from fastapi import UploadFile, File
    form = await request.form()
    file = form.get("file")
    if file is None:
        return JSONResponse({"error": "file required"}, status_code=400)
    return await v1_router.upload_file(file)


# --- HTML pages (unchanged) -------------------------------------------------

def _render(name, **ctx):
    t = jinja.get_template(name)
    return HTMLResponse(t.render(**ctx))


def _sd(s):
    if s is None:
        return None
    if isinstance(s, dict):
        return s
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

