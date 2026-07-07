"""Tests du routing conditionnel du graph."""

from app.agents.graph import should_revise
from tests.conftest import make_state


def test_should_revise_when_revision_needed_and_under_limit():
    state = make_state(critique="REVISION_NEEDED: ajoute des sources", iterations=1)
    assert should_revise(state) == "researcher"


def test_should_go_to_writer_when_limit_reached():
    state = make_state(critique="REVISION_NEEDED: encore insuffisant", iterations=2)
    assert should_revise(state) == "writer"


def test_should_go_to_writer_when_approved():
    state = make_state(critique="APPROVED: recherche solide", iterations=1)
    assert should_revise(state) == "writer"


def test_should_go_to_writer_when_no_critique():
    state = make_state(critique="", iterations=0)
    assert should_revise(state) == "writer"
