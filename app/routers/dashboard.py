"""Router NOVO: /dashboard — metricas agregadas para o perfil ADMIN."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_admin_id_atual, get_db
from app.schemas.dashboard import DashboardResponse
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("", response_model=DashboardResponse)
def dashboard(
    admin_id: int = Depends(get_admin_id_atual),
    db: Session = Depends(get_db),
):
    """GET /dashboard — visao geral da plataforma. Restrito a perfil ADMIN."""
    return dashboard_service.montar_dashboard(db)