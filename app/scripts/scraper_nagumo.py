from __future__ import annotations

import argparse
import hashlib
from datetime import datetime, timezone
from collections import Counter
from sqlalchemy import text
import json
import re
import time
from decimal import Decimal
from urllib.parse import urlencode, urljoin, urlparse

from playwright.sync_api import (
    BrowserContext,
    Page,
    Playwright,
    sync_playwright,
)

from app.core.database import SessionLocal
from app.models.historico_preco import HistoricoPreco
from app.models.loja_externa import LojaExterna
from app.models.produto import Produto


BASE = "https://www.nagumo.com.br"

# Intervalo moderado entre páginas do catálogo.
INTERVALO_ENTRE_REQUISICOES_SEGUNDOS = 3.0

# Pausa entre categorias.
INTERVALO_ENTRE_CATEGORIAS_SEGUNDOS = 3.0

# Número de tentativas para selecionar uma loja.
MAX_TENTATIVAS_SELECAO_LOJA = 3

# Tempo de espera entre tentativas de seleção.
INTERVALO_RETRY_LOJA_SEGUNDOS = 3.0

TAMANHO_PAGINA = 40
MAX_PAGINAS_CATEGORIA = 1500
# Teto conservador baseado na recusa observada; nao e autorizacao de acesso.
LIMITE_RESULTADOS = 1000

LATITUDE = "-23.5325875"
LONGITUDE = "-46.335124"


class AcessoRecusado(RuntimeError):
    """Uma recusa impede novas consultas ate liberacao administrativa."""
    def __init__(self, status: int, etapa: str):
        self.status = status
        self.etapa = etapa
        super().__init__(f"HTTP {status} em {etapa}. Coleta suspensa.")


def verificar_acesso(status: int, etapa: str, headers=None) -> None:
    # Nunca imprime cookies, tokens, corpo ou todos os headers.
    headers = headers or {}
    seguros = {k: str(headers[k])[:160] for k in
               ("content-type", "retry-after", "x-request-id", "cf-ray") if k in headers}
    print(json.dumps({"evento": "http", "utc": datetime.now(timezone.utc).isoformat(),
                      "etapa": etapa, "status": status, "headers": seguros}, ensure_ascii=False))
    if status in (403, 429):
        raise AcessoRecusado(status, etapa)


def verificar_pausa(db):
    estado = db.execute(text("SELECT status_http, etapa FROM nagumo_coleta_pausa WHERE id = 1")).first()
    db.commit()
    if estado:
        raise RuntimeError(f"Coleta bloqueada administrativamente: HTTP {estado[0]} em {estado[1]}. "
                           "Confirme os limites e a liberacao com o Nagumo antes de retomar.")


def registrar_pausa(db, erro):
    db.rollback()
    db.execute(text("""INSERT INTO nagumo_coleta_pausa (id, status_http, etapa, registrado_em)
        VALUES (1, :status, :etapa, :agora)
        ON CONFLICT (id) DO UPDATE SET status_http=excluded.status_http,
        etapa=excluded.etapa, registrado_em=excluded.registrado_em"""),
        {"status": erro.status, "etapa": erro.etapa, "agora": datetime.now(timezone.utc)})
    db.commit()


def ler_checkpoint(db, codigo, categoria):
    row = db.execute(text("""SELECT proxima_posicao, assinaturas, concluida
        FROM nagumo_coleta_checkpoint WHERE loja_codigo=:codigo AND categoria=:categoria"""),
        {"codigo": codigo, "categoria": categoria}).first()
    return (row[0], set(json.loads(row[1])), bool(row[2])) if row else (0, set(), False)


def salvar_checkpoint(db, codigo, categoria, posicao, assinaturas, concluida):
    db.execute(text("""INSERT INTO nagumo_coleta_checkpoint
        (loja_codigo, categoria, proxima_posicao, assinaturas, concluida, atualizado_em)
        VALUES (:codigo, :categoria, :posicao, :assinaturas, :concluida, :agora)
        ON CONFLICT (loja_codigo, categoria) DO UPDATE SET
        proxima_posicao=excluded.proxima_posicao, assinaturas=excluded.assinaturas,
        concluida=excluded.concluida, atualizado_em=excluded.atualizado_em"""),
        {"codigo": codigo, "categoria": categoria, "posicao": posicao,
         "assinaturas": json.dumps(sorted(assinaturas)), "concluida": concluida,
         "agora": datetime.now(timezone.utc)})


def assinatura_pagina(produtos):
    # IDs originais quando presentes; fallback conservador para nomes completos.
    identidades = []
    for produto in produtos:
        ident = produto.get("productID") or produto.get("productId") or produto.get("id") or produto.get("ean")
        identidades.append("id:" + str(ident) if ident else
                           "nome:" + chave_produto(str(produto.get("productName") or "")))
    return hashlib.sha256(json.dumps(sorted(identidades), ensure_ascii=False).encode()).hexdigest()


def chave_produto(nome: str) -> str:
    # Não remove acentos, marcas, pesos ou variantes.
    return " ".join(nome.split()).casefold()


# ============================================================
# NAVEGADOR
# ============================================================

def _criar_navegador(playwright: Playwright):

    browser = playwright.chromium.launch(
        headless=True,
    )

    context = browser.new_context(
        locale="pt-BR",
        timezone_id="America/Sao_Paulo",

        extra_http_headers={
            "Accept-Language": (
                "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
            ),
        },
    )

    return browser, context


# ============================================================
# ABRIR NAGUMO
# ============================================================

def _abrir_nagumo(page: Page) -> None:

    resposta = page.goto(
        BASE,
        wait_until="domcontentloaded",
        timeout=60000,
    )

    if resposta is None:
        raise RuntimeError(
            "O Nagumo não retornou resposta ao abrir "
            "a página inicial."
        )

    verificar_acesso(resposta.status, "pagina inicial", resposta.headers)

    if resposta.status >= 400:
        raise RuntimeError(
            f"Nagumo retornou HTTP {resposta.status} "
            "ao abrir a página inicial."
        )

    print("[OK] Nagumo aberto no navegador.")


# ============================================================
# SELECIONAR LOJA - UMA TENTATIVA
# ============================================================

def _tentar_selecionar_loja(
    page: Page,
    loja_codigo: str,
    lat: str,
    lng: str,
) -> tuple[bool, str]:

    resultado = page.evaluate(
        """
        async ({ storeId, lat, lng }) => {

            const parametros = new URLSearchParams({
                storeId: storeId,
                method: "Retirada",
                lat: lat,
                lng: lng
            });

            const url =
                "/on/demandware.store/" +
                "Sites-Nagumo-Site/" +
                "pt_BR/" +
                "Stores-SelectStore?" +
                parametros.toString();

            try {

                const resposta = await fetch(
                    url,
                    {
                        method: "GET",
                        credentials: "include",
                        headers: {
                            "Accept": "*/*",
                            "X-Requested-With": "XMLHttpRequest"
                        }
                    }
                );

                const texto = await resposta.text();

                return {
                    status: resposta.status,
                    texto: texto,
                    headers: {"content-type": resposta.headers.get("content-type"),
                              "retry-after": resposta.headers.get("retry-after"),
                              "x-request-id": resposta.headers.get("x-request-id")}
                };

            } catch (erro) {

                return {
                    status: 0,
                    texto: String(erro)
                };
            }
        }
        """,
        {
            "storeId": loja_codigo,
            "lat": lat,
            "lng": lng,
        },
    )

    status = resultado["status"]
    verificar_acesso(status, f"selecao da loja {loja_codigo}", resultado.get("headers"))
    texto = resultado["texto"]

    if status != 200:

        return (
            False,
            f"HTTP {status}."
        )

    try:

        dados = json.loads(texto)

    except json.JSONDecodeError:

        return (
            False,
            "Nagumo retornou uma resposta que não é JSON."
        )

    if not dados.get("success"):

        return (
            False,
            "Nagumo não confirmou a seleção."
        )

    return True, ""


# ============================================================
# SELECIONAR LOJA - COM RETRY
# ============================================================

def _selecionar_loja(
    page: Page,
    loja_codigo: str,
    lat: str,
    lng: str,
    playwright: Playwright | None = None,
    browser=None,
    context: BrowserContext | None = None,
) -> tuple[Page, BrowserContext | None, object]:
    """
    Tenta selecionar a loja várias vezes.

    Se o Nagumo retornar HTTP 500, a sessão do navegador
    pode ser recriada antes da próxima tentativa.

    Retorna:
        page
        context
        browser
    """

    ultimo_erro = "Erro desconhecido."

    for tentativa in range(
        1,
        MAX_TENTATIVAS_SELECAO_LOJA + 1,
    ):

        print(
            f"[INFO] Selecionando loja {loja_codigo} "
            f"(tentativa {tentativa}/"
            f"{MAX_TENTATIVAS_SELECAO_LOJA})..."
        )

        try:

            sucesso, erro = _tentar_selecionar_loja(
                page=page,
                loja_codigo=loja_codigo,
                lat=lat,
                lng=lng,
            )

            if sucesso:

                print(
                    f"[OK] Loja {loja_codigo} "
                    "selecionada no Nagumo."
                )

                return page, context, browser

            ultimo_erro = erro

            print(
                f"[AVISO] Falha ao selecionar loja "
                f"{loja_codigo}: {erro}"
            )

        except AcessoRecusado:
            raise
        except Exception as erro:

            ultimo_erro = str(erro)

            print(
                f"[AVISO] Erro na seleção da loja "
                f"{loja_codigo}: {erro}"
            )

        # ----------------------------------------------------
        # Se ainda haverá tentativa, aguardar.
        # ----------------------------------------------------

        if tentativa < MAX_TENTATIVAS_SELECAO_LOJA:

            print(
                f"[INFO] Aguardando "
                f"{INTERVALO_RETRY_LOJA_SEGUNDOS:.1f}s "
                "antes de tentar novamente..."
            )

            time.sleep(
                INTERVALO_RETRY_LOJA_SEGUNDOS
            )

            # ------------------------------------------------
            # Recriar contexto para limpar cookies/sessão.
            # ------------------------------------------------

            if (
                playwright is not None
                and browser is not None
            ):

                print(
                    "[INFO] Recriando sessão do Nagumo..."
                )

                try:

                    if context is not None:
                        context.close()

                except Exception:
                    pass

                context = browser.new_context(
                    locale="pt-BR",
                    timezone_id="America/Sao_Paulo",

                    extra_http_headers={
                        "Accept-Language": (
                            "pt-BR,pt;q=0.9,"
                            "en-US;q=0.8,en;q=0.7"
                        ),
                    },
                )

                page = context.new_page()

                try:

                    _abrir_nagumo(page)

                except AcessoRecusado:
                    raise
                except Exception as erro_abertura:

                    print(
                        "[AVISO] Não foi possível "
                        "reabrir o Nagumo: "
                        f"{erro_abertura}"
                    )

    raise RuntimeError(
        f"Não foi possível selecionar a loja "
        f"{loja_codigo} após "
        f"{MAX_TENTATIVAS_SELECAO_LOJA} tentativas.\n"
        f"Último erro: {ultimo_erro}"
    )


# ============================================================
# DESCOBRIR DEPARTAMENTOS
# ============================================================

def _descobrir_departamentos(
    page: Page,
) -> list[str]:

    departamentos = [
        "acougue",
        "basicos-e-matinais",
        "bazar",
        "bebidas",
        "frios-e-laticinios",
        "higiene-e-perfumaria",
        "hortifruti",
        "limpeza",
        "padaria",
        "peixaria",
        "pet-shop",
        "mercearia-doce",
        "mercearia-salgada",
    ]

    print(
        f"[OK] {len(departamentos)} departamentos "
        "principais configurados."
    )

    for cgid in departamentos:
        print(f"       - {cgid}")

    return departamentos


# ============================================================
# EXTRAIR PRODUTOS DO JSON
# ============================================================

def _extrair_produtos_da_pagina(resposta_texto: str) -> list[dict]:
    try:
        dados = json.loads(resposta_texto)
    except json.JSONDecodeError as erro:
        raise RuntimeError("Resposta de catalogo nao e JSON; coleta interrompida.") from erro
    produtos = dados.get("productsSearchResult") if isinstance(dados, dict) else None
    if not isinstance(produtos, list) or any(not isinstance(p, dict) for p in produtos):
        raise RuntimeError("Formato inesperado do catalogo; coleta interrompida.")
    if produtos and not any(isinstance(p.get("productName"), str) and p["productName"].strip() for p in produtos):
        raise RuntimeError("Pagina sem identificacao de produtos; coleta interrompida.")
    return produtos


class PaginaCatalogo(list):
    def __init__(self, produtos, total=None):
        super().__init__(produtos)
        self.total = total


def _total_informado(dados):
    # Somente campos explicitamente associados a total de resultados.
    valores = []
    for objeto in (dados, dados.get("pagination"), dados.get("productSearch")):
        if not isinstance(objeto, dict):
            continue
        for chave in ("total", "totalCount", "totalResults", "totalProducts", "totalHits"):
            valor = objeto.get(chave)
            if type(valor) is int and valor >= 0:
                valores.append(valor)
            elif isinstance(valor, str) and valor.isascii() and valor.isdecimal() and len(valor) <= 12:
                valores.append(int(valor))
    return valores[0] if valores and len(set(valores)) == 1 else None


def _verificar_limite_posicao(inicio):
    if inicio < 0 or inicio >= LIMITE_RESULTADOS:
        raise RuntimeError(f"Limite de paginacao conservador atingido na posicao {inicio}; "
                           "aguarde confirmacao do fornecedor. Checkpoint preservado.")


def _buscar_pagina(context: BrowserContext, cgid: str, inicio: int) -> list[dict]:
    _verificar_limite_posicao(inicio)
    tamanho = min(TAMANHO_PAGINA, LIMITE_RESULTADOS - inicio)
    parametros = urlencode({"cgid": cgid, "start": inicio, "sz": tamanho})
    url = (f"{BASE}/on/demandware.store/Sites-Nagumo-Site/pt_BR/Search-UpdateGrid?{parametros}")
    resposta = context.request.get(url, headers={"Accept": "*/*", "Referer": f"{BASE}/"}, timeout=60000)
    try:
        verificar_acesso(resposta.status, f"categoria {cgid}, posicao {inicio}", resposta.headers)
        if resposta.status >= 400:
            raise RuntimeError(f"HTTP {resposta.status} na categoria {cgid}, posicao {inicio}")
        bruto = resposta.text()
        produtos = _extrair_produtos_da_pagina(bruto)
        total = _total_informado(json.loads(bruto))
        if len(produtos) > tamanho:
            raise RuntimeError("Resposta excede o tamanho de pagina solicitado.")
        print(f"[INFO] Categoria '{cgid}': posicao {inicio} -> {len(produtos)} produtos.")
        print(f"[INFO] Total informado pelo servidor: {total if total is not None else 'indisponivel'}")
        return PaginaCatalogo(produtos, total)
    finally:
        resposta.dispose()


# ============================================================
# CARREGAR PRODUTOS DA LOJA EM MEMÓRIA
# ============================================================

def _carregar_produtos_da_loja(
    db,
    loja_id: int,
) -> dict[str, Produto | None]:

    print(
        "[INFO] Carregando produtos existentes "
        "da loja no banco..."
    )

    produtos = (
        db.query(Produto)
        .filter(
            Produto.loja_externa_id == loja_id
        )
        .all()
    )

    mapa: dict[str, Produto | None] = {}

    for produto in produtos:

        nome = (
            produto.nome_produto or ""
        ).strip()

        if not nome:
            continue

        chave = chave_produto(nome)
        if chave in mapa:
            mapa[chave] = None
        else:
            mapa[chave] = produto

    ambiguos = sum(valor is None for valor in mapa.values())
    if ambiguos:
        print(f"[AVISO] {ambiguos} nomes ambiguos; registros preservados sem atualizar automaticamente.")

    print(
        f"[OK] {len(mapa)} chaves de produtos existentes "
        "carregados em memória."
    )

    return mapa


# ============================================================
# IMAGENS DISPONIVEIS NO JSON DO CATALOGO
# ============================================================

def normalizar_url_imagem(valor: str) -> str | None:
    if not isinstance(valor, str) or not valor.strip():
        return None
    url = urljoin(BASE + "/", valor.strip())
    url = re.sub(r"^https?://www\.nagumo\.com\.br/[^?]*?/(?=https://ngostpubprd001\.blob\.core\.windows\.net/)", "", url, flags=re.I)
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https") or not parsed.hostname or re.search(r"https?://", parsed.path, re.I):
        return None
    if len(url) > 2048 or any(c.isspace() for c in url):
        return None
    if not re.search(r"\.(?:webp|png|jpe?g|gif|avif)(?:$)", parsed.path, re.I):
        return None
    if parsed.path.rsplit("/", 1)[-1].lower() in {"meunagumo.png", "noimage.png", "placeholder.png"}:
        return None
    return url


def _extrair_imagens(produto_nagumo: dict) -> list[str]:
    """Coleta URLs de imagem presentes no produto, sem downloads adicionais.

    Compatibilidade com os formatos comuns de SFCC: image, images,
    imageGroups, imageUrl, productImage e suas variacoes.
    """
    encontrados: list[str] = []
    vistos: set[str] = set()
    campos_url = {"url", "src", "link", "absurl", "absoluteurl", "imageurl", "image_url", "href"}
    campos_imagem = {"image", "images", "imagegroups", "imagegroup", "productimage",
                     "productimages", "imageurl", "image_url", "thumbnail", "thumbnailurl",
                     "largeimage", "smallimage", "mediumimage", "primaryimage", "variationimages"}

    def guardar(valor):
        if not isinstance(valor, str) or not valor.strip():
            return
        url = normalizar_url_imagem(valor)
        if not url or url in vistos:
            return
        vistos.add(url)
        encontrados.append(url)

    def percorrer(valor, contexto_imagem=False, profundidade=0):
        if profundidade > 10:
            return
        if isinstance(valor, str):
            if contexto_imagem:
                guardar(valor)
        elif isinstance(valor, list):
            for item in valor:
                percorrer(item, contexto_imagem, profundidade + 1)
        elif isinstance(valor, dict):
            for chave, item in valor.items():
                key = chave.lower().replace("_", "").replace("-", "")
                if key in campos_imagem or key.startswith("image") or key.endswith("image"):
                    percorrer(item, True, profundidade + 1)
                elif contexto_imagem and (key in campos_url or key in
                      {"large", "medium", "small", "hires", "desktop", "mobile", "images", "viewtype"}):
                    if key != "viewtype":
                        percorrer(item, True, profundidade + 1)
                elif contexto_imagem and isinstance(item, (dict, list)):
                    percorrer(item, True, profundidade + 1)

    percorrer(produto_nagumo)
    return encontrados


# ============================================================
# SALVAR / ATUALIZAR PRODUTO
# ============================================================

def _salvar_produto(
    db,
    loja: LojaExterna,
    produto_nagumo: dict,
    produtos_existentes: dict[str, Produto | None],
    historicos_criados: set[tuple[int, Decimal]],
    categoria: str | None = None,
) -> str:

    nome = (
        produto_nagumo
        .get("productName", "")
        .strip()
    )

    preco_raw = (
        produto_nagumo
        .get("price", {})
        .get("sales", {})
        .get("value")
    )

    if not nome:
        return "ignorado"

    if preco_raw is None:
        return "ignorado"

    try:

        preco = Decimal(
            str(preco_raw)
        )

    except Exception:

        return "ignorado"

    if not preco.is_finite() or preco < 0:
        return "ignorado"

    imagens_urls = _extrair_imagens(produto_nagumo)

    # ========================================================
    # PRODUTO NOVO
    # ========================================================

    chave = chave_produto(nome)
    if chave in produtos_existentes and produtos_existentes[chave] is None:
        return "ignorado"
    produto = produtos_existentes.get(chave)

    if produto is None:

        produto = Produto(
            nome_produto=nome,
            tags=categoria,
            preco=preco,
            quantidade=0,
            origem="EXTERNO",
            loja_externa_id=loja.id,
            imagem_url=imagens_urls[0] if imagens_urls else None,
            imagens_urls=imagens_urls,
        )

        db.add(produto)

        db.flush()

        db.add(
            HistoricoPreco(
                produto_id=produto.id,
                preco=preco,
            )
        )

        produtos_existentes[chave] = produto

        historicos_criados.add(
            (produto.id, preco)
        )

        return "novo"

    if categoria and not produto.tags:
        produto.tags = categoria

    # Preserve URLs principais válidas; repare concatenações e preencha lacunas.
    principal = normalizar_url_imagem(produto.imagem_url)
    antigas = produto.imagens_urls if isinstance(produto.imagens_urls, list) else []
    mescladas = list(dict.fromkeys(url for valor in [principal, *antigas, *imagens_urls]
                                  if (url := normalizar_url_imagem(valor))))
    if mescladas:
        if produto.imagens_urls != mescladas:
            produto.imagens_urls = mescladas
        if produto.imagem_url != (principal or mescladas[0]):
            produto.imagem_url = principal or mescladas[0]

    # ========================================================
    # PREÇO IGUAL
    # ========================================================

    if produto.preco == preco:

        return "sem_alteracao"

    # ========================================================
    # PREÇO ALTERADO
    # ========================================================

    produto.preco = preco

    chave_historico = (
        produto.id,
        preco,
    )

    db.add(HistoricoPreco(produto_id=produto.id, preco=preco))

    return "preco_alterado"


# ============================================================
# PROCESSAR UMA LOJA
# ============================================================

def _processar_loja(
    page: Page,
    context: BrowserContext,
    db,
    loja_nome: str,
    loja_codigo: str,
    categorias: list[str],
    playwright: Playwright,
    browser,
) -> tuple[int, Page, BrowserContext, object]:

    print()
    print("=" * 70)
    print(
        f"LOJA: {loja_nome} "
        f"(código {loja_codigo})"
    )
    print("=" * 70)

    # --------------------------------------------------------
    # Selecionar loja com retry.
    # --------------------------------------------------------

    page, context, browser = _selecionar_loja(
        page=page,
        loja_codigo=loja_codigo,
        lat=LATITUDE,
        lng=LONGITUDE,
        playwright=playwright,
        browser=browser,
        context=context,
    )

    # --------------------------------------------------------
    # Buscar / criar loja externa
    # --------------------------------------------------------

    loja = (
        db.query(LojaExterna)
        .filter_by(
            nome=loja_nome
        )
        .one_or_none()
    )

    if loja is None:

        loja = LojaExterna(
            nome=loja_nome,
            dominio="www.nagumo.com.br",
            plataforma="SFCC",
        )

        db.add(loja)

        db.flush()

        print(
            f"[OK] Loja externa criada: "
            f"{loja_nome}"
        )

    else:

        print(
            f"[OK] Loja externa encontrada: "
            f"{loja_nome}"
        )

    # --------------------------------------------------------
    # Carregar produtos existentes uma única vez.
    # --------------------------------------------------------

    produtos_existentes = (
        _carregar_produtos_da_loja(
            db=db,
            loja_id=loja.id,
        )
    )

    db.commit()
    contagem = Counter()
    for cgid in categorias:
        inicio, assinaturas, concluida = ler_checkpoint(db, loja_codigo, cgid)
        db.commit()
        if concluida:
            print(f"[INFO] Categoria {cgid} ja concluida neste ciclo.")
            continue
        while True:
            if inicio // TAMANHO_PAGINA >= MAX_PAGINAS_CATEGORIA:
                raise RuntimeError(f"Limite de paginacao atingido em {cgid}; revisar catalogo.")
            _verificar_limite_posicao(inicio)
            produtos = _buscar_pagina(context, cgid, inicio)
            assinatura = assinatura_pagina(produtos) if produtos else None
            if assinatura and assinatura in assinaturas:
                raise RuntimeError(f"Pagina repetida em {cgid}, posicao {inicio}; revisar paginacao.")
            lote = Counter()
            for item in produtos:
                resultado = _salvar_produto(db, loja, item, produtos_existentes, set(), cgid)
                lote[resultado] += 1
            if assinatura:
                assinaturas.add(assinatura)
            proxima = inicio + len(produtos)
            total = getattr(produtos, "total", None)
            if total is not None and total < proxima:
                raise RuntimeError("Total do catalogo inconsistente com a pagina recebida.")
            if total is not None and not produtos and inicio < total:
                raise RuntimeError("Pagina vazia antes do total informado.")
            concluida = (proxima == total if total is not None else
                         len(produtos) < min(TAMANHO_PAGINA, LIMITE_RESULTADOS - inicio))
            # Dados e checkpoint na mesma transacao: ambos gravados ou nenhum.
            salvar_checkpoint(db, loja_codigo, cgid, proxima, assinaturas, concluida)
            db.commit()
            contagem.update(lote)
            print(f"[OK] Lote gravado: loja {loja_codigo}, {cgid}, posicao {inicio}, {dict(lote)}")
            if concluida:
                break
            inicio = proxima
            time.sleep(INTERVALO_ENTRE_REQUISICOES_SEGUNDOS)
        time.sleep(INTERVALO_ENTRE_CATEGORIAS_SEGUNDOS)
    # Somente quando todas as categorias solicitadas terminam: novo ciclo na proxima execucao.
    for cgid in categorias:
        db.execute(text("DELETE FROM nagumo_coleta_checkpoint WHERE loja_codigo=:codigo AND categoria=:categoria"),
                   {"codigo": loja_codigo, "categoria": cgid})
    db.commit()
    print(f"[OK] Loja {loja_codigo} finalizada. Lotes desta execucao: {dict(contagem)}")
    return sum(contagem.values()), page, context, browser


# ============================================================
# EXECUÇÃO PRINCIPAL
# ============================================================

def rodar(
    lojas: list[dict],
    categorias: list[str] | None = None,
    todos: bool = False,
) -> None:

    playwright = None

    browser = None
    context = None
    db = None

    try:
        db = SessionLocal()
        db.expire_on_commit = False
        verificar_pausa(db)
        playwright = sync_playwright().start()

        # ----------------------------------------------------
        # Criar navegador
        # ----------------------------------------------------

        browser, context = _criar_navegador(
            playwright
        )

        page = context.new_page()

        # ----------------------------------------------------
        # Abrir Nagumo
        # ----------------------------------------------------

        _abrir_nagumo(page)

        # ----------------------------------------------------
        # Banco
        # ----------------------------------------------------

        # ----------------------------------------------------
        # Definir categorias
        # ----------------------------------------------------

        if todos:

            categorias_processar = (
                _descobrir_departamentos(
                    page
                )
            )

        elif categorias:

            categorias_processar = categorias

        else:

            raise ValueError(
                "Informe --todos ou --categorias."
            )

        print()
        print(
            f"[INFO] Categorias que serão processadas: "
            f"{len(categorias_processar)}"
        )

        print(
            f"[INFO] Intervalo entre páginas: "
            f"{INTERVALO_ENTRE_REQUISICOES_SEGUNDOS}s"
        )

        print(
            f"[INFO] Intervalo entre categorias: "
            f"{INTERVALO_ENTRE_CATEGORIAS_SEGUNDOS}s"
        )

        print()

        total_geral = 0
        lojas_concluidas = 0
        lojas_com_erro = 0

        # ----------------------------------------------------
        # Processar cada loja
        # ----------------------------------------------------

        for loja in lojas:

            try:

                (
                    total,
                    page,
                    context,
                    browser,
                ) = _processar_loja(
                    page=page,
                    context=context,
                    db=db,
                    loja_nome=loja["nome"],
                    loja_codigo=loja["codigo"],
                    categorias=categorias_processar,
                    playwright=playwright,
                    browser=browser,
                )

                total_geral += total
                lojas_concluidas += 1

            except Exception:
                # Qualquer coleta incompleta deve falhar, inclusive na matriz do GitHub.
                raise

        # ----------------------------------------------------
        # Resultado final
        # ----------------------------------------------------

        print()
        print("=" * 70)
        print("SCRAPER FINALIZADO")
        print("=" * 70)

        print(
            f"[OK] Total de produtos analisados: "
            f"{total_geral}"
        )

        print(
            f"[OK] Lojas concluídas: "
            f"{lojas_concluidas}/{len(lojas)}"
        )

        if lojas_com_erro > 0:

            print(
                f"[AVISO] Lojas com erro: "
                f"{lojas_com_erro}"
            )

        print(
            f"[OK] Categorias configuradas: "
            f"{len(categorias_processar)}"
        )

        print()
        print(
            "[OK] Banco protegido contra "
            "históricos desnecessários."
        )

    except AcessoRecusado as erro:
        if db is not None:
            registrar_pausa(db, erro)
        raise
    except Exception:
        if db is not None:
            db.rollback()
        raise

    finally:

        if db is not None:
            db.close()

        if context is not None:

            try:
                context.close()
            except Exception:
                pass

        if browser is not None:

            try:
                browser.close()
            except Exception:
                pass

        if playwright is not None:
            playwright.stop()


# ============================================================
# ARGUMENTOS DE LINHA DE COMANDO
# ============================================================

def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Scraper de produtos do Nagumo "
            "para o Mercadez."
        )
    )

    parser.add_argument(
        "--loja",
        type=str,
        help=(
            "Nome da loja. "
            "Pode ser usado junto com --loja-codigo."
        ),
    )

    parser.add_argument(
        "--loja-codigo",
        type=str,
        help="Código da loja no Nagumo.",
    )

    parser.add_argument(
        "--todas-lojas",
        action="store_true",
        help=(
            "Processa automaticamente "
            "as quinze lojas configuradas."
        ),
    )

    parser.add_argument(
        "--todos",
        action="store_true",
        help=(
            "Processa todos os departamentos "
            "configurados do Nagumo."
        ),
    )

    parser.add_argument(
        "--categorias",
        nargs="+",
        help=(
            "Categorias específicas. "
            "Exemplo: hortifruti bebidas padaria"
        ),
    )

    args = parser.parse_args()

    # --------------------------------------------------------
    # Lojas padrão do Mercadez
    # --------------------------------------------------------

    lojas_padrao = [
    # POA
    {"nome": "Nagumo Poa", "codigo": "22"},
    {"nome": "Nagumo Poa_Kemel", "codigo": "45"},

    # SUZANO
    {"nome": "Nagumo Suzano", "codigo": "27"},
    {"nome": "Nagumo_Suzano_Dona_Benta", "codigo": "23"},

    # ITAQUAQUECETUBA
    {"nome": "Nagumo Itaqua", "codigo": "30"},
    {"nome": "Nagumo_Itaqua_Vila_Zeferina", "codigo": "39"},

    # MOGI DAS CRUZES
    {"nome": "Nagumo_Mogi_Alto_Ipiranga", "codigo": "52"},

    # GUARULHOS
    {"nome": "Nagumo_Guarulhos_Merc_Bonsucesso", "codigo": "41"},
    {"nome": "Nagumo_Guarulhos_Cumbica", "codigo": "42"},
    {"nome": "Nagumo_Guarulhos_Shopping_Pimentas", "codigo": "49"},
    {"nome": "Nagumo_Guarulhos_Continental", "codigo": "51"},
    {"nome": "Nagumo_Guarulhos_Bonsucesso", "codigo": "55"},
    {"nome": "Nagumo_Guarulhos_Elenco", "codigo": "56"},
    {"nome": "Nagumo_Guarulhos_Anel_Viario", "codigo": "57"},
    {"nome": "Nagumo_Guarulhos_Alvorada", "codigo": "61"},
]

    # --------------------------------------------------------
    # Definir lojas
    # --------------------------------------------------------

    if args.todas_lojas:

        lojas = lojas_padrao

    elif args.loja and args.loja_codigo:

        lojas = [
            {
                "nome": args.loja,
                "codigo": args.loja_codigo,
            }
        ]

    else:

        raise SystemExit(
            "Informe --todas-lojas "
            "ou use --loja junto com --loja-codigo."
        )

    # --------------------------------------------------------
    # Definir categorias
    # --------------------------------------------------------

    if not args.todos and not args.categorias:

        raise SystemExit(
            "Informe --todos para buscar todo o catálogo "
            "ou --categorias para buscar categorias específicas."
        )

    # --------------------------------------------------------
    # Executar
    # --------------------------------------------------------

    rodar(
        lojas=lojas,
        categorias=args.categorias,
        todos=args.todos,
    )


if __name__ == "__main__":
    try:
        main()
    except AcessoRecusado as erro:
        print(f"[ERRO] {erro}", flush=True)
        raise SystemExit(1)

