"""Tests du routing conditionnel et de l'état initial du graph."""

import pytest

from app.agents.orchestrator import should_revise, _initial_state
from tests.conftest import make_state


# ── should_revise ──────────────────────────────────────────────────────────

def test_should_revise_when_revision_needed_and_under_limit():
    state = make_state(critique="REVISION_NEEDED: ajoute des sources", iteration=1)
    assert should_revise(state) == "researcher"


def test_should_go_to_writer_when_limit_reached():
    state = make_state(critique="REVISION_NEEDED: encore insuffisant", iteration=2)
    assert should_revise(state) == "writer"


def test_should_go_to_writer_when_approved():
    state = make_state(critique="APPROVED: recherche solide", iteration=1)
    assert should_revise(state) == "writer"


def test_should_go_to_writer_when_no_critique():
    state = make_state(critique="", iteration=0)
    assert should_revise(state) == "writer"


# ── _initial_state ─────────────────────────────────────────────────────────

def test_initial_state_sets_task():
    state = _initial_state("Ma tâche")
    assert state["task"] == "Ma tâche"


def test_initial_state_has_empty_collections():
    state = _initial_state("t")
    assert state["plan"] == []
    assert state["research"] == []
    assert state["messages"] == []


def test_initial_state_iteration_zero():
    assert _initial_state("t")["iteration"] == 0


def test_initial_state_empty_strings():
    state = _initial_state("t")
    assert state["critique"] == ""
    assert state["final_answer"] == ""
