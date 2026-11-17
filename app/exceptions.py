"""
Excecoes de negocio customizadas — equivalentes as classes em
com.mercadez.exception do backend Java. O tratamento delas em respostas
HTTP padronizadas acontece nos exception handlers registrados em main.py.
"""


class NegocioException(Exception):
    """Erro de regra de negocio (ex: email ja cadastrado). Vira HTTP 400."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class NaoEncontradoException(Exception):
    """Recurso nao encontrado. Vira HTTP 404."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class CredenciaisInvalidasException(Exception):
    """Email ou senha incorretos no login. Vira HTTP 401."""

    def __init__(self, message: str = "Email ou senha incorretos."):
        self.message = message
        super().__init__(message)


class AcessoNegadoException(Exception):
    """Usuario autenticado mas sem permissao para a acao. Vira HTTP 403."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)
