"""Définition de l'état partagé entre tous les agents du pipeline."""

from __future__ import annotations
from typing import TypedDict, Annotated
import operator


class AgentState(TypedDict):
    """État mutable transmis de nœud en nœud dans le graph LangGraph."""
    task: str                                      # tâche originale
    plan: list[str]                                # étapes du Planner
    research: list[str]                            # résultats du Researcher
    critique: str                                  # feedback du Critic
    final_answer: str                              # réponse du Writer
    iteration: int                                 # compteur de cycles
    messages: Annotated[list, operator.add]        # historique — append-only
