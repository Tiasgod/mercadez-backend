from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_db
from app.schemas.comparacao import ComparacaoResponse
from app.services import comparacao_service


router = APIRouter(
    prefix="/comparacao",
    tags=["Comparação de preços"],
)


@router.get(
    "",
    response_model=list[ComparacaoResponse],
)
def comparar(
    produto: str = Query(
        ...,
        min_length=2,
        description="Nome ou parte do nome do produto",
    ),
    db: Session = Depends(get_db),
):
    return comparacao_service.comparar_produtos(
        db,
        produto,
    )