"""État partagé du graph LangGraph — contrat commun à tous les agents."""

import operator
from typing import Annotated, TypedDict


class AgentState(TypedDict):
    """État transmis et enrichi par chaque nœud du graph."""

    task: str
    plan: list[str]
    research: list[str]
    critique: str
    final_answer: str
    iterations: int
    messages: Annotated[list, operator.add]
