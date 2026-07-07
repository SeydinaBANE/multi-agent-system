"""Dependencies FastAPI exposant le Container et le WorkflowService construits au lifespan."""

from fastapi import Request

from app.application.container import Container
from app.application.workflow_service import WorkflowService


def get_container(request: Request) -> Container:
    """Retourne le Container applicatif construit au démarrage (app.state.container)."""
    return request.app.state.container


def get_workflow_service(request: Request) -> WorkflowService:
    """Retourne le WorkflowService applicatif construit au démarrage (app.state.workflow_service)."""
    return request.app.state.workflow_service
