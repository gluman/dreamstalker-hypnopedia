#!/usr/bin/env python3
"""DreamStalker - Hypnopedia Learning System CLI"""

import json
from pathlib import Path

import click
import yaml

from ragflow.goal_planner import GoalPlanner
from content.package_builder import PackageBuilder
from content.test_generator import TestGenerator
from content.session_manager import SessionManager, LearningGoal, TestResult
from core.audio_generator import NightAudioGenerator, NightConfig, TMRConfig
from core.anchor_generator import AnchorGenerator
from protocols.lucid_dream import LucidDreamProtocol, Technique
from protocols.obe import OBEProtocol

CONFIG_PATH = Path(__file__).parent / "config.yaml"


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def get_ragflow(cfg: dict) -> dict:
    return {
        "base_url": cfg["ragflow"]["base_url"],
        "api_key": cfg["ragflow"]["api_key"],
        "dataset_id": "57e3405527a111f1ad97929ce6da87e6",
    }


@click.group()
def cli():
    """DreamStalker - Hypnopedia Learning System"""


@cli.command()
@click.option("--goal", required=True, help="Learning topic/goal")
@click.option("--count", default=5, help="Number of subtopics")
@click.option("--output", required=True, help="Output path for plan JSON")
def plan(goal: str, count: int, output: str):
    """Create a learning plan using GoalPlanner."""
    cfg = load_config()
    rf = get_ragflow(cfg)
    planner = GoalPlanner(
        base_url=rf["base_url"], api_key=rf["api_key"], dataset_id=rf["dataset_id"]
    )
    result = planner.create_plan(goal=goal, max_subtopics=count)
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    click.echo(f"Plan saved: {output} ({len(result.get('subtopics', []))} subtopics)")


@cli.command()
@click.option("--plan", "plan_path", required=True, help="Path to plan JSON")
def prepare(plan_path: str):
    """Prepare a sleep session: build package, generate audio, create tests."""
    cfg = load_config()

    with open(plan_path, encoding="utf-8") as f:
        plan_data = json.load(f)

    session_mgr = SessionManager(data_dir=cfg.get("data_dir", "data"))
    goal = LearningGoal(
        title=plan_data["title"],
        topics=[s["title"] for s in plan_data.get("subtopics", [])],
    )
    session = session_mgr.create_session(goal=goal)
    sid = session.id
    click.echo(f"Session created: {sid}")

    # 1. Build content package
    rf = get_ragflow(cfg)
    builder = PackageBuilder(
        base_url=rf["base_url"], api_key=rf["api_key"], dataset_id=rf["dataset_id"]
    )
    pkg = builder.build(session_id=sid, plan=plan_data)
    click.echo(f"Package built: {pkg.id} ({len(pkg.items)} items)")

    # 2. Generate test suite
    tester = TestGenerator(
        base_url=rf["base_url"], api_key=rf["api_key"], dataset_id=rf["dataset_id"]
    )
    test_suite = tester.generate(session_id=sid, plan=plan_data)
    click.echo(f"Test suite: {len(test_suite.questions)} questions")

    # 3. Assign anchors
    anchor_gen = AnchorGenerator()
    anchor_map = anchor_gen.assign(session_id=sid, package=pkg)
    click.echo(f"Anchors: {len(anchor_map)} assigned")

    # 4. Generate falling-asleep audio (25 min)
    audio_gen = NightAudioGenerator(output_dir=cfg.get("audio_dir", "audio"))
    night_cfg = NightConfig(duration_minutes=25, tmr=TMRConfig(enabled=True))
    audio_path = audio_gen.generate(session_id=sid, package=pkg, config=night_cfg)
    click.echo(f"Audio generated: {audio_path}")

    # 5. Save everything
    session_mgr.attach_package(sid, pkg)
    session_mgr.attach_tests(sid, test_suite)
    session_mgr.attach_anchors(sid, anchor_map)
    session_mgr.attach_audio(sid, str(audio_path))
    click.echo(f"Session {sid} ready.")


@cli.command()
@click.option("--session-id", required=True, help="Session ID to test")
@click.option("--count", default=10, help="Number of questions")
def test(session_id: str, count: int):
    """Run an interactive verification test."""
    cfg = load_config()
    session_mgr = SessionManager(data_dir=cfg.get("data_dir", "data"))
    suite = session_mgr.get_test_suite(session_id)

    questions = suite.questions[:count]
    results = []
    for i, q in enumerate(questions, 1):
        click.echo(f"\nQ{i}: {q.text}")
        if q.options:
            for j, opt in enumerate(q.options, 1):
                click.echo(f"  {j}. {opt}")
        answer = input("Your answer: ").strip()
        correct = q.check(answer)
        results.append(TestResult(question_id=q.id, user_answer=answer, correct=correct))
        click.echo("  Correct!" if correct else f"  Wrong. Answer: {q.answer}")

    score = sum(1 for r in results if r.correct)
    click.echo(f"\nResult: {score}/{len(results)}")
    session_mgr.save_test_results(session_id, results)


@cli.command()
@click.option("--session-id", required=True, help="Session ID")
def report(session_id: str):
    """Show a session report."""
    cfg = load_config()
    session_mgr = SessionManager(data_dir=cfg.get("data_dir", "data"))
    session = session_mgr.get_session(session_id)
    results = session_mgr.get_test_results(session_id)

    click.echo(f"Session: {session.id}")
    click.echo(f"Goal: {session.goal.title}")
    click.echo(f"Status: {session.status}")
    click.echo(f"Created: {session.created_at}")
    if results:
        correct = sum(1 for r in results if r.correct)
        click.echo(f"Tests: {correct}/{len(results)} correct")


@cli.command()
@click.option("--status", default=None, help="Filter by status")
def sessions(status: str):
    """List all sessions."""
    cfg = load_config()
    session_mgr = SessionManager(data_dir=cfg.get("data_dir", "data"))
    all_sessions = session_mgr.list_sessions(status=status)
    if not all_sessions:
        click.echo("No sessions found.")
        return
    for s in all_sessions:
        click.echo(f"  {s.id}  {s.status:10s}  {s.goal.title}")


@cli.command()
@click.option("--type", "proto_type", type=click.Choice(["lucid", "obe"]), required=True)
@click.option("--technique", type=click.Choice(["wild", "mild", "ssild", "fild"]), default=None)
def protocols(proto_type: str, technique: str):
    """Show lucid dreaming or OBE protocols."""
    if proto_type == "lucid":
        proto = LucidDreamProtocol()
        tech = Technique(technique) if technique else Technique.WILD
        click.echo(proto.get_protocol(tech))
    else:
        proto = OBEProtocol()
        click.echo(proto.get_protocol())



@cli.command()
@click.option("--host", default="127.0.0.1", help="Host address")
@click.option("--port", default=8000, help="Port number")
def web(host: str, port: int):
    """Start the web interface."""
    import uvicorn
    click.echo(f"Starting DreamStalker web at http://{host}:{port}")
    uvicorn.run("web.app:app", host=host, port=port, reload=True)
if __name__ == "__main__":
    cli()
