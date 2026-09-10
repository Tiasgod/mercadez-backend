"""
Ponto de entrada da aplicacao FastAPI — equivalente a
MercadezApplication.java + SecurityConfig.java (parte de CORS)
+ GlobalExceptionHandler.java (parte dos exception handlers).
"""
import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.exceptions import (
    AcessoNegadoException,
    CredenciaisInvalidasException,
    NaoEncontradoException,
    NegocioException,
)
from app.routers import afiliados, contato, listas, produtos, usuarios
from app.schemas.common import ErroResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mercadez")

app = FastAPI(
    title="Mercadez API",
    description="API REST da plataforma de comparacao de precos Mercadez.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Authorization"],
)

app.include_router(usuarios.router)
app.include_router(afiliados.router)
app.include_router(produtos.router)
app.include_router(contato.router)
app.include_router(listas.router)


def _erro_json(status_code: int, erro: str, mensagem: str) -> JSONResponse:
    body = ErroResponse(status=status_code, erro=erro, mensagem=mensagem)
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


@app.exception_handler(RequestValidationError)
async def handle_validation(request: Request, exc: RequestValidationError):
    """
    Erros de validacao do Pydantic. Convertidos para o MESMO formato e
    status HTTP (400, nao o 422 padrao do FastAPI) que o backend Java
    retornava via @Valid + MethodArgumentNotValidException.
    """
    mensagens = []
    for erro in exc.errors():
        campo = ".".join(str(p) for p in erro["loc"] if p != "body")
        mensagens.append(f"{campo}: {erro['msg']}" if campo else erro["msg"])
    return _erro_json(status.HTTP_400_BAD_REQUEST, "Dados invalidos", "; ".join(mensagens))


@app.exception_handler(NegocioException)
async def handle_negocio(request: Request, exc: NegocioException):
    return _erro_json(status.HTTP_400_BAD_REQUEST, "Erro de negocio", exc.message)


@app.exception_handler(NaoEncontradoException)
async def handle_nao_encontrado(request: Request, exc: NaoEncontradoException):
    return _erro_json(status.HTTP_404_NOT_FOUND, "Nao encontrado", exc.message)


@app.exception_handler(CredenciaisInvalidasException)
async def handle_credenciais(request: Request, exc: CredenciaisInvalidasException):
    return _erro_json(status.HTTP_401_UNAUTHORIZED, "Nao autorizado", exc.message)


@app.exception_handler(AcessoNegadoException)
async def handle_acesso_negado(request: Request, exc: AcessoNegadoException):
    return _erro_json(status.HTTP_403_FORBIDDEN, "Acesso negado", exc.message)


@app.exception_handler(Exception)
async def handle_generico(request: Request, exc: Exception):
    """Fallback generico — nunca expoe stack trace ao usuario."""
    logger.exception("Erro nao tratado em %s %s", request.method, request.url)
    return _erro_json(status.HTTP_500_INTERNAL_SERVER_ERROR, "Erro interno", "Ocorreu um erro inesperado.")


@app.get("/", tags=["Status"])
def raiz():
    return {"servico": "Mercadez API", "status": "online"}
