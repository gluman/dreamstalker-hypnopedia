#!/usr/bin/env python3
"""DreamStalker - Hypnopedia Learning System CLI"""

import json
from pathlib import Path

import click
import yaml

from core.services import ServiceContainer, ServiceConfig
from ragflow.goal_planner import GoalPlanner
from content.session_manager import LearningGoal, TestResult
from core.audio_generator import NightAudioGenerator, NightConfig, TMRConfig
from core.anchor_generator import AnchorGenerator
from protocols.lucid_dream import LucidDreamProtocol, Technique
from protocols.obe import OBEProtocol


def get_container() -> ServiceContainer:
    return ServiceContainer()


@click.group()
def cli_group():
    """DreamStalker - Hypnopedia Learning System"""
    pass


@cli_group.command()
@click.option("--goal", required=True, help="Learning topic/goal")
@click.option("--count", default=5, help="Number of subtopics")
@click.option("--output", required=True, help="Output path for plan JSON")
def plan(goal: str, count: int, output: str):
    """Create a learning plan using GoalPlanner."""
    services = get_container()
    rf = services.ragflow_config
    planner = GoalPlanner(
        base_url=rf["base_url"], api_key=rf["api_key"], dataset_id=rf["dataset_id"]
    )
    result = planner.create_plan(goal=goal, max_subtopics=count)
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    click.echo(f"Plan saved: {output} ({len(result.get('subtopics', []))} subtopics)")


@cli_group.command()
@click.option("--plan", "plan_path", required=True, help="Path to plan JSON")
def prepare(plan_path: str):
    """Prepare a sleep session: build package, generate audio, create tests."""
    services = get_container()
    sm = services.session_manager
    pb = services.package_builder
    tg = services.test_generator
    ag = services.anchor_generator
    ng = services.night_audio_generator

    with open(plan_path, encoding="utf-8") as f:
        plan_data = json.load(f)

    goal = LearningGoal(
        title=plan_data["title"],
        topics=[s["title"] for s in plan_data.get("subtopics", [])],
    )
    session = sm.create_session(goal=goal)
    sid = session.id
    click.echo(f"Session created: {sid}")

    pkg = pb.build(session_id=sid, plan=plan_data)
    click.echo(f"Package built: {pkg.id} ({len(pkg.items)} items)")

    test_suite = tg.generate(session_id=sid, plan=plan_data)
    click.echo(f"Test suite: {len(test_suite.questions)} questions")

    anchor_map = ag.assign(session_id=sid, package=pkg)
    click.echo(f"Anchors: {len(anchor_map)} assigned")

    audio_cfg = NightConfig(duration_minutes=25, tmr=TMRConfig(enabled=True))
    audio_path = ng.generate(session_id=sid, package=pkg, config=audio_cfg)
    click.echo(f"Audio generated: {audio_path}")

    sm.attach_package(sid, pkg)
    sm.attach_tests(sid, test_suite)
    sm.attach_anchors(sid, anchor_map)
    sm.attach_audio(sid, str(audio_path))
    click.echo(f"Session {sid} ready.")


@cli_group.command()
@click.option("--session-id", required=True, help="Session ID to test")
@click.option("--count", default=10, help="Number of questions")
def test(session_id: str, count: int):
    """Run an interactive verification test."""
    services = get_container()
    sm = services.session_manager
    suite = sm.get_test_suite(session_id)

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
    sm.save_test_results(session_id, results)


@cli_group.command()
@click.option("--session-id", required=True, help="Session ID")
def report(session_id: str):
    """Show a session report."""
    services = get_container()
    sm = services.session_manager
    session = sm.get_session(session_id)
    results = sm.get_test_results(session_id)

    click.echo(f"Session: {session.id}")
    click.echo(f"Goal: {session.goal.title}")
    click.echo(f"Status: {session.status}")
    click.echo(f"Created: {session.created_at}")
    if results:
        correct = sum(1 for r in results if r.correct)
        click.echo(f"Tests: {correct}/{len(results)} correct")


@cli_group.command()
@click.option("--status", default=None, help="Filter by status")
def sessions(status: str):
    """List all sessions."""
    services = get_container()
    sm = services.session_manager
    all_sessions = sm.list_sessions(status=status)
    if not all_sessions:
        click.echo("No sessions found.")
        return
    for s in all_sessions:
        click.echo(f"  {s.id}  {s.status:10s}  {s.goal.title}")


@cli_group.command()
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


@cli_group.command()
@click.option("--host", default="127.0.0.1", help="Host address")
@click.option("--port", default=8000, help="Port number")
def web(host: str, port: int):
    """Start the web interface."""
    import uvicorn
    click.echo(f"Starting DreamStalker web at http://{host}:{port}")
    uvicorn.run("web.app:app", host=host, port=port, reload=True)


def cli():
    cli_group()


if __name__ == "__main__":
    cli()
