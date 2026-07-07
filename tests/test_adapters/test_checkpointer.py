"""Tests de CheckpointerAdapter — bascule vers MemorySaver si Postgres est indisponible."""

import sys
from unittest.mock import MagicMock, patch

from langgraph.checkpoint.memory import MemorySaver

from app.adapters.checkpointer.postgres_checkpointer import CheckpointerAdapter


async def test_setup_falls_back_to_memory_saver_on_error():
    adapter = CheckpointerAdapter()

    broken_module = MagicMock()
    broken_module.AsyncConnectionPool = MagicMock(side_effect=Exception("no psycopg"))

    with patch.dict(sys.modules, {"psycopg_pool": broken_module}):
        await adapter.setup()

    assert isinstance(adapter._checkpointer, MemorySaver)


def test_get_graph_compiles_once():
    from tests.conftest import fake_container

    adapter = CheckpointerAdapter()
    container = fake_container()

    graph_a = adapter.get_graph(container)
    graph_b = adapter.get_graph(container)

    assert graph_a is graph_b
