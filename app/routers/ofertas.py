from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_db
from app.schemas.oferta import OfertaResponse
from app.services import oferta_service


router = APIRouter(
    prefix="/ofertas",
    tags=["Ofertas"],
)


@router.get(
    "",
    response_model=list[OfertaResponse],
)
def listar_ofertas(
    limite: int = Query(
        20,
        ge=1,
        le=100,
        description="Quantidade máxima de ofertas retornadas",
    ),
    db: Session = Depends(get_db),
):
    return oferta_service.listar_ofertas(
        db,
        limite,
    )