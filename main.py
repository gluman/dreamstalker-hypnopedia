#!/usr/bin/env python3
"""DreamStalker - Hypnopedia Learning System CLI"""

import json
from pathlib import Path

import click

from core.config import get_ragflow_config, get_settings
from ragflow.goal_planner import GoalPlanner
from content.package_builder import PackageBuilder
from content.test_generator import TestGenerator
from content.session_manager import SessionManager, LearningGoal, SleepSession, TestResult
from core.audio_generator import NightAudioGenerator
from core.anchor_generator import AnchorGenerator
from protocols.lucid_dream import LucidDreamProtocol, Technique
from protocols.obe import OBEProtocol


@click.group()
def cli():
    """DreamStalker - Hypnopedia Learning System"""


@cli.command()
@click.option("--goal", required=True, help="Learning topic/goal")
@click.option("--count", default=5, help="Number of subtopics")
@click.option("--output", required=True, help="Output path for plan JSON")
def plan(goal: str, count: int, output: str):
    """Create a learning plan by extracting key facts from RAGFlow knowledge base."""
    rf = get_ragflow_config()
    planner = GoalPlanner(
        base_url=rf["base_url"], api_key=rf["api_key"], dataset_id=rf["dataset_id"]
    )
    try:
        result = planner.create_learning_plan(goal_description=goal, items_count=count)
    except Exception as e:
        click.echo(f"Error creating plan: {e}", err=True)
        raise click.Abort()
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    click.echo(f"Plan saved: {output} ({len(result.get('items', []))} items)")


@cli.command()
@click.option("--plan", "plan_path", required=True, help="Path to plan JSON")
def prepare(plan_path: str):
    """Prepare a sleep session: build package, generate audio, create tests."""
    cfg = get_settings()

    with open(plan_path, encoding="utf-8") as f:
        plan_data = json.load(f)

    session_mgr = SessionManager(base_path=cfg.get("data_dir", "data") + "/sessions")
    goal = LearningGoal(
        topic=plan_data.get("goal", "Unknown"),
        description=plan_data.get("goal", ""),
        target_items_count=len(plan_data.get("items", [])),
    )
    session = session_mgr.create_session(goal=goal)
    sid = session.session_id
    click.echo(f"Session created: {sid}")

    # 1. Build content package
    rf = get_ragflow_config()
    builder = PackageBuilder()
    pkg = builder.build_sleep_package(items=plan_data.get("items", []))
    click.echo(f"Package built: {len(pkg.get('items', []))} items")

    # 2. Generate test suite
    tester = TestGenerator()
    test_suite = tester.generate_full_test_suite(items=plan_data.get("items", []))
    click.echo(f"Test suite: {test_suite['metadata']['total']} questions")

    # 3. Assign anchors
    anchor_gen = AnchorGenerator()
    items_with_anchors = anchor_gen.assign_anchors(plan_data.get("items", []))
    click.echo(f"Anchors: {len(items_with_anchors)} assigned")

    # 4. Generate falling-asleep audio
    audio_gen = NightAudioGenerator()
    audio_path = str(Path(cfg.get("audio_dir", "data/audio")) / f"{sid}_night.wav")
    installation_text = builder.build_installation_text(
        plan_data.get("goal", ""), len(plan_data.get("items", []))
    )
    audio_gen.generate_falling_asleep_phase(
        items=items_with_anchors,
        installation_text=installation_text,
        duration_min=25.0,
        output_path=audio_path,
    )
    click.echo(f"Audio generated: {audio_path}")

    # 5. Save everything
    session_mgr.save_package(session, items_with_anchors)
    session_mgr.save_test(session, test_suite.get("tests", []))
    session_mgr.save_audio(session, audio_path)
    click.echo(f"Session {sid} ready.")


@cli.command()
@click.option("--session-id", required=True, help="Session ID to test")
@click.option("--count", default=10, help="Number of questions")
def test(session_id: str, count: int):
    """Run an interactive verification test."""
    cfg = get_settings()
    session_mgr = SessionManager(base_path=cfg.get("data_dir", "data") + "/sessions")
    session = session_mgr.load_session(session_id)
    test_path = Path(session.test_path) if session.test_path else Path(cfg.get("data_dir", "data")) / "sessions" / session_id / "test.json"

    if not test_path.exists():
        click.echo(f"No test found for session {session_id}", err=True)
        raise click.Abort()

    tests = json.loads(test_path.read_text(encoding="utf-8"))
    questions = tests[:count]
    results = []
    for i, q in enumerate(questions, 1):
        click.echo(f"\nQ{i}: {q.get('question', '')}")
        if q.get("options"):
            for j, opt in enumerate(q["options"], 1):
                click.echo(f"  {j}. {opt}")
        answer = input("Your answer: ").strip()
        correct_answer = q.get("answer", "")
        correct = answer.lower() == correct_answer.lower() or answer.lower() in correct_answer.lower() or correct_answer.lower() in answer.lower()
        results.append({
            "item_id": q.get("item_id", i),
            "question": q.get("question", ""),
            "correct_answer": correct_answer,
            "user_answer": answer,
            "is_correct": correct,
        })
        click.echo("  Correct!" if correct else f"  Wrong. Answer: {correct_answer}")

    score = sum(1 for r in results if r["is_correct"])
    click.echo(f"\nResult: {score}/{len(results)}")
    session_mgr.save_test_results(results)


@cli.command()
@click.option("--session-id", required=True, help="Session ID")
def report(session_id: str):
    """Show a session report."""
    cfg = get_settings()
    session_mgr = SessionManager(base_path=cfg.get("data_dir", "data") + "/sessions")
    session = session_mgr.load_session(session_id)

    click.echo(f"Session: {session.session_id}")
    click.echo(f"Goal: {session.goal.topic}")
    click.echo(f"Status: {session.status}")
    click.echo(f"Created: {session.created_at}")

    results_path = Path(cfg.get("data_dir", "data")) / "sessions" / session_id / "results.json"
    if results_path.exists():
        import json
        results = json.loads(results_path.read_text(encoding="utf-8"))
        correct = sum(1 for r in results if r.get("is_correct"))
        click.echo(f"Tests: {correct}/{len(results)} correct")


@cli.command()
@click.option("--status", default=None, help="Filter by status")
def sessions(status: str):
    """List all sessions."""
    cfg = get_settings()
    session_mgr = SessionManager(base_path=cfg.get("data_dir", "data") + "/sessions")
    all_sessions = session_mgr.list_sessions(status=status)
    if not all_sessions:
        click.echo("No sessions found.")
        return
    for s in all_sessions:
        click.echo(f"  {s['session_id']}  {s.get('status', 'unknown'):10s}  {s.get('goal', {}).get('topic', 'Unknown')}")


@cli.command()
@click.option("--type", "proto_type", type=click.Choice(["lucid", "obe"]), required=True)
@click.option("--technique", type=click.Choice(["wild", "mild", "ssild", "fild"]), default=None)
def protocols(proto_type: str, technique: str):
    """Show lucid dreaming or OBE protocols."""
    if proto_type == "lucid":
        proto = LucidDreamProtocol()
        tech = Technique(technique) if technique else Technique.WILD
        click.echo(proto.get_full_protocol(tech))
    else:
        proto = OBEProtocol()
        click.echo(proto.get_full_protocol())



@cli.command()
@click.option("--host", default="127.0.0.1", help="Host address")
@click.option("--port", default=8000, help="Port number")
def web_cmd(host: str, port: int):
    """Start the web interface."""
    import uvicorn
    click.echo(f"Starting DreamStalker web at http://{host}:{port}")
    uvicorn.run("web.app:app", host=host, port=port, reload=True)


if __name__ == "__main__":
    cli()
