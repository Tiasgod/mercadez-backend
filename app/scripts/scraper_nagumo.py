from __future__ import annotations

import argparse
import hashlib
import json
import re
import time

from datetime import datetime, timezone
from collections import Counter
from decimal import Decimal
from urllib.parse import urlencode, urljoin, urlparse

from sqlalchemy import text

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


# ============================================================
# CONFIGURACOES
# ============================================================

BASE = "https://www.nagumo.com.br"

INTERVALO_ENTRE_REQUISICOES_SEGUNDOS = 3.0
INTERVALO_ENTRE_CATEGORIAS_SEGUNDOS = 3.0

TAMANHO_PAGINA = 40
MAX_PAGINAS_CATEGORIA = 1500

# Limite conservador baseado nas recusas observadas.
LIMITE_RESULTADOS = 1000

LATITUDE = "-23.5325875"
LONGITUDE = "-46.335124"


# ============================================================
# DIAGNOSTICO HTTP
# ============================================================

class AcessoRecusado(RuntimeError):

    def __init__(self, status: int, etapa: str):

        self.status = status
        self.etapa = etapa

        super().__init__(
            f"HTTP {status} em {etapa}. "
            "Execucao interrompida."
        )


def verificar_acesso(
    status: int,
    etapa: str,
    headers=None,
) -> None:

    headers = headers or {}

    seguros = {
        k: str(headers[k])[:160]
        for k in (
            "content-type",
            "retry-after",
            "x-request-id",
            "cf-ray",
        )
        if k in headers
    }

    print(
        json.dumps(
            {
                "evento": "http",
                "utc": datetime.now(
                    timezone.utc
                ).isoformat(),
                "etapa": etapa,
                "status": status,
                "headers": seguros,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )

    if status in (403, 429):
        raise AcessoRecusado(status, etapa)


# ============================================================
# CHECKPOINTS NO NEON
# ============================================================

def ler_checkpoint(db, codigo, categoria):

    row = db.execute(
        text("""
            SELECT
                proxima_posicao,
                assinaturas,
                concluida
            FROM nagumo_coleta_checkpoint
            WHERE loja_codigo = :codigo
            AND categoria = :categoria
        """),
        {
            "codigo": codigo,
            "categoria": categoria,
        },
    ).first()

    if row:
        return (
            row[0],
            set(json.loads(row[1])),
            bool(row[2]),
        )

    return 0, set(), False


def salvar_checkpoint(
    db,
    codigo,
    categoria,
    posicao,
    assinaturas,
    concluida,
):

    db.execute(
        text("""
            INSERT INTO nagumo_coleta_checkpoint (
                loja_codigo,
                categoria,
                proxima_posicao,
                assinaturas,
                concluida,
                atualizado_em
            )
            VALUES (
                :codigo,
                :categoria,
                :posicao,
                :assinaturas,
                :concluida,
                :agora
            )
            ON CONFLICT (
                loja_codigo,
                categoria
            )
            DO UPDATE SET
                proxima_posicao =
                    excluded.proxima_posicao,
                assinaturas =
                    excluded.assinaturas,
                concluida =
                    excluded.concluida,
                atualizado_em =
                    excluded.atualizado_em
        """),
        {
            "codigo": codigo,
            "categoria": categoria,
            "posicao": posicao,
            "assinaturas": json.dumps(
                sorted(assinaturas)
            ),
            "concluida": concluida,
            "agora": datetime.now(timezone.utc),
        },
    )


# ============================================================
# IDENTIFICACAO DE PRODUTOS E PAGINAS
# ============================================================

def chave_produto(nome: str) -> str:

    return " ".join(nome.split()).casefold()


def assinatura_pagina(produtos):

    identidades = []

    for produto in produtos:

        ident = (
            produto.get("productID")
            or produto.get("productId")
            or produto.get("id")
            or produto.get("ean")
        )

        if ident:

            identidade = "id:" + str(ident)

        else:

            identidade = (
                "nome:"
                + chave_produto(
                    str(
                        produto.get("productName")
                        or ""
                    )
                )
            )

        identidades.append(identidade)

    return hashlib.sha256(
        json.dumps(
            sorted(identidades),
            ensure_ascii=False,
        ).encode()
    ).hexdigest()


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
            "O Nagumo nao retornou resposta "
            "ao abrir a pagina inicial."
        )

    verificar_acesso(
        resposta.status,
        "pagina inicial",
        resposta.headers,
    )

    if resposta.status >= 400:

        raise RuntimeError(
            f"Nagumo retornou HTTP "
            f"{resposta.status}."
        )

    print("[OK] Nagumo aberto no navegador.")


# ============================================================
# SELECIONAR LOJA
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
                    headers: {
                        "content-type":
                            resposta.headers.get("content-type"),
                        "retry-after":
                            resposta.headers.get("retry-after"),
                        "x-request-id":
                            resposta.headers.get("x-request-id")
                    }
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

    verificar_acesso(
        status,
        f"selecao da loja {loja_codigo}",
        resultado.get("headers"),
    )

    if status != 200:

        return False, f"HTTP {status}"

    try:

        dados = json.loads(
            resultado["texto"]
        )

    except json.JSONDecodeError:

        return (
            False,
            "Resposta de selecao nao e JSON.",
        )

    if not dados.get("success"):

        return (
            False,
            "Nagumo nao confirmou a selecao.",
        )

    return True, ""


def _selecionar_loja(
    page: Page,
    loja_codigo: str,
    lat: str,
    lng: str,
    playwright=None,
    browser=None,
    context=None,
):

    print(
        f"[INFO] Selecionando loja "
        f"{loja_codigo}..."
    )

    sucesso, erro = _tentar_selecionar_loja(
        page,
        loja_codigo,
        lat,
        lng,
    )

    if not sucesso:

        raise RuntimeError(
            f"Falha ao selecionar loja "
            f"{loja_codigo}: {erro}"
        )

    print(
        f"[OK] Loja {loja_codigo} selecionada."
    )

    return page, context, browser


# ============================================================
# DEPARTAMENTOS
# ============================================================

def _descobrir_departamentos(page: Page):

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
        f"[OK] {len(departamentos)} "
        "departamentos configurados."
    )

    for categoria in departamentos:

        print(f"       - {categoria}")

    return departamentos


# ============================================================
# EXTRAIR PRODUTOS DO JSON
# ============================================================

def _extrair_produtos_da_pagina(
    resposta_texto: str,
) -> list[dict]:

    try:

        dados = json.loads(resposta_texto)

    except json.JSONDecodeError as erro:

        raise RuntimeError(
            "Resposta do catalogo nao e JSON."
        ) from erro

    produtos = (
        dados.get("productsSearchResult")
        if isinstance(dados, dict)
        else None
    )

    if (
        not isinstance(produtos, list)
        or any(
            not isinstance(p, dict)
            for p in produtos
        )
    ):

        raise RuntimeError(
            "Formato inesperado do catalogo."
        )

    if produtos and not any(
        isinstance(
            p.get("productName"),
            str,
        )
        and p["productName"].strip()
        for p in produtos
    ):

        raise RuntimeError(
            "Pagina sem identificacao de produtos."
        )

    return produtos


class PaginaCatalogo(list):

    def __init__(self, produtos, total=None):

        super().__init__(produtos)

        self.total = total


# ============================================================
# IDENTIFICAR TOTAL DE PRODUTOS
# ============================================================

def _total_informado(dados):

    valores = []

    for objeto in (
        dados,
        dados.get("pagination"),
        dados.get("productSearch"),
    ):

        if not isinstance(objeto, dict):
            continue

        for chave in (
            "total",
            "totalCount",
            "totalResults",
            "totalProducts",
            "totalHits",
        ):

            valor = objeto.get(chave)

            if type(valor) is int and valor >= 0:

                valores.append(valor)

            elif (
                isinstance(valor, str)
                and valor.isascii()
                and valor.isdecimal()
                and len(valor) <= 12
            ):

                valores.append(int(valor))

    if valores and len(set(valores)) == 1:

        return valores[0]

    return None


# ============================================================
# PAGINACAO
# ============================================================

def _verificar_limite_posicao(inicio):

    if inicio < 0 or inicio >= LIMITE_RESULTADOS:

        raise RuntimeError(
            f"Limite conservador de paginacao "
            f"atingido na posicao {inicio}. "
            "Checkpoint preservado. "
            "Confirme o limite com o fornecedor."
        )


def _buscar_pagina(
    context: BrowserContext,
    cgid: str,
    inicio: int,
):

    _verificar_limite_posicao(inicio)

    tamanho = min(
        TAMANHO_PAGINA,
        LIMITE_RESULTADOS - inicio,
    )

    print(
        f"[INFO] Consulta: categoria={cgid}, "
        f"start={inicio}, sz={tamanho}"
    )

    inicio_http = time.monotonic()

    parametros = urlencode(
        {
            "cgid": cgid,
            "start": inicio,
            "sz": tamanho,
        }
    )

    url = (
        f"{BASE}/on/demandware.store/"
        "Sites-Nagumo-Site/pt_BR/"
        f"Search-UpdateGrid?{parametros}"
    )

    resposta = context.request.get(
        url,
        headers={
            "Accept": "*/*",
            "Referer": f"{BASE}/",
        },
        timeout=60000,
    )

    try:

        duracao = (
            time.monotonic() - inicio_http
        )

        print(
            f"[INFO] Resposta recebida "
            f"em {duracao:.2f}s"
        )

        verificar_acesso(
            resposta.status,
            f"categoria {cgid}, posicao {inicio}",
            resposta.headers,
        )

        if resposta.status >= 400:

            raise RuntimeError(
                f"HTTP {resposta.status} "
                f"na categoria {cgid}, "
                f"posicao {inicio}"
            )

        bruto = resposta.text()

        produtos = _extrair_produtos_da_pagina(
            bruto
        )

        total = _total_informado(
            json.loads(bruto)
        )

        if len(produtos) > tamanho:

            raise RuntimeError(
                "Resposta excede o tamanho "
                "de pagina solicitado."
            )

        print(
            f"[INFO] Categoria '{cgid}': "
            f"posicao {inicio} -> "
            f"{len(produtos)} produtos."
        )

        print(
            "[INFO] Total informado pelo servidor: "
            f"{total if total is not None else 'indisponivel'}"
        )

        return PaginaCatalogo(
            produtos,
            total,
        )

    finally:

        resposta.dispose()


# ============================================================
# CARREGAR PRODUTOS EXISTENTES
# ============================================================

def _carregar_produtos_da_loja(
    db,
    loja_id: int,
):

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

    mapa = {}

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

    ambiguos = sum(
        valor is None
        for valor in mapa.values()
    )

    if ambiguos:

        print(
            f"[AVISO] {ambiguos} nomes ambiguos. "
            "Registros preservados."
        )

    print(
        f"[OK] {len(mapa)} chaves "
        "carregadas em memoria."
    )

    return mapa


# ============================================================
# NORMALIZAR IMAGENS
# ============================================================

def normalizar_url_imagem(valor):

    if (
        not isinstance(valor, str)
        or not valor.strip()
    ):

        return None

    url = urljoin(
        BASE + "/",
        valor.strip(),
    )

    url = re.sub(
        r"^https?://www\.nagumo\.com\.br/"
        r"[^?]*?/(?=https://ngostpubprd001"
        r"\.blob\.core\.windows\.net/)",
        "",
        url,
        flags=re.I,
    )

    try:

        parsed = urlparse(url)

    except ValueError:

        return None

    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or re.search(
            r"https?://",
            parsed.path,
            re.I,
        )
    ):

        return None

    if (
        len(url) > 2048
        or any(c.isspace() for c in url)
    ):

        return None

    if not re.search(
        r"\.(?:webp|png|jpe?g|gif|avif)$",
        parsed.path,
        re.I,
    ):

        return None

    if (
        parsed.path.rsplit("/", 1)[-1].lower()
        in {
            "meunagumo.png",
            "noimage.png",
            "placeholder.png",
        }
    ):

        return None

    return url


# ============================================================
# EXTRAIR IMAGENS
# ============================================================

def _extrair_imagens(produto_nagumo):

    encontrados = []
    vistos = set()

    campos_url = {
        "url",
        "src",
        "link",
        "absurl",
        "absoluteurl",
        "imageurl",
        "image_url",
        "href",
    }

    campos_imagem = {
        "image",
        "images",
        "imagegroups",
        "imagegroup",
        "productimage",
        "productimages",
        "imageurl",
        "image_url",
        "thumbnail",
        "thumbnailurl",
        "largeimage",
        "smallimage",
        "mediumimage",
        "primaryimage",
        "variationimages",
    }

    def guardar(valor):

        if (
            not isinstance(valor, str)
            or not valor.strip()
        ):

            return

        url = normalizar_url_imagem(valor)

        if not url or url in vistos:

            return

        vistos.add(url)
        encontrados.append(url)

    def percorrer(
        valor,
        contexto_imagem=False,
        profundidade=0,
    ):

        if profundidade > 10:

            return

        if isinstance(valor, str):

            if contexto_imagem:

                guardar(valor)

        elif isinstance(valor, list):

            for item in valor:

                percorrer(
                    item,
                    contexto_imagem,
                    profundidade + 1,
                )

        elif isinstance(valor, dict):

            for chave, item in valor.items():

                key = (
                    chave.lower()
                    .replace("_", "")
                    .replace("-", "")
                )

                if (
                    key in campos_imagem
                    or key.startswith("image")
                    or key.endswith("image")
                ):

                    percorrer(
                        item,
                        True,
                        profundidade + 1,
                    )

                elif contexto_imagem and (
                    key in campos_url
                    or key in {
                        "large",
                        "medium",
                        "small",
                        "hires",
                        "desktop",
                        "mobile",
                        "images",
                        "viewtype",
                    }
                ):

                    if key != "viewtype":

                        percorrer(
                            item,
                            True,
                            profundidade + 1,
                        )

                elif (
                    contexto_imagem
                    and isinstance(
                        item,
                        (dict, list),
                    )
                ):

                    percorrer(
                        item,
                        True,
                        profundidade + 1,
                    )

    percorrer(produto_nagumo)

    return encontrados


# ============================================================
# SALVAR OU ATUALIZAR PRODUTO
# ============================================================

def _salvar_produto(
    db,
    loja,
    produto_nagumo,
    produtos_existentes,
    historicos_criados,
    categoria=None,
):

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

    if not nome or preco_raw is None:

        return "ignorado"

    try:

        preco = Decimal(str(preco_raw))

    except Exception:

        return "ignorado"

    if not preco.is_finite() or preco < 0:

        return "ignorado"

    imagens_urls = _extrair_imagens(
        produto_nagumo
    )

    chave = chave_produto(nome)

    if (
        chave in produtos_existentes
        and produtos_existentes[chave] is None
    ):

        return "ignorado"

    produto = produtos_existentes.get(chave)

    # PRODUTO NOVO

    if produto is None:

        produto = Produto(
            nome_produto=nome,
            tags=categoria,
            preco=preco,
            quantidade=0,
            origem="EXTERNO",
            loja_externa_id=loja.id,
            imagem_url=(
                imagens_urls[0]
                if imagens_urls
                else None
            ),
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

    # ATUALIZAR CATEGORIA

    if categoria and not produto.tags:

        produto.tags = categoria

    # PRESERVAR IMAGENS EXISTENTES

    principal = normalizar_url_imagem(
        produto.imagem_url
    )

    antigas = (
        produto.imagens_urls
        if isinstance(
            produto.imagens_urls,
            list,
        )
        else []
    )

    mescladas = list(
        dict.fromkeys(
            url
            for valor in [
                principal,
                *antigas,
                *imagens_urls,
            ]
            if (
                url := normalizar_url_imagem(
                    valor
                )
            )
        )
    )

    if mescladas:

        if produto.imagens_urls != mescladas:

            produto.imagens_urls = mescladas

        if produto.imagem_url != (
            principal or mescladas[0]
        ):

            produto.imagem_url = (
                principal or mescladas[0]
            )

    # PRECO SEM ALTERACAO

    if produto.preco == preco:

        return "sem_alteracao"

    # PRECO ALTERADO

    produto.preco = preco

    db.add(
        HistoricoPreco(
            produto_id=produto.id,
            preco=preco,
        )
    )

    return "preco_alterado"


# ============================================================
# PROCESSAR LOJA
# ============================================================

def _processar_loja(
    page,
    context,
    db,
    loja_nome,
    loja_codigo,
    categorias,
    playwright,
    browser,
):

    print()
    print("=" * 70)
    print(
        f"LOJA: {loja_nome} "
        f"(codigo {loja_codigo})"
    )
    print("=" * 70)

    page, context, browser = _selecionar_loja(
        page=page,
        loja_codigo=loja_codigo,
        lat=LATITUDE,
        lng=LONGITUDE,
        playwright=playwright,
        browser=browser,
        context=context,
    )

    loja = (
        db.query(LojaExterna)
        .filter_by(nome=loja_nome)
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

    produtos_existentes = (
        _carregar_produtos_da_loja(
            db,
            loja.id,
        )
    )

    db.commit()

    contagem = Counter()

    for cgid in categorias:

        inicio, assinaturas, concluida = (
            ler_checkpoint(
                db,
                loja_codigo,
                cgid,
            )
        )

        db.commit()

        if concluida:

            print(
                f"[INFO] Categoria {cgid} "
                "ja concluida neste ciclo."
            )

            continue

        while True:

            if (
                inicio // TAMANHO_PAGINA
                >= MAX_PAGINAS_CATEGORIA
            ):

                raise RuntimeError(
                    f"Limite de paginas atingido "
                    f"em {cgid}."
                )

            _verificar_limite_posicao(inicio)

            produtos = _buscar_pagina(
                context,
                cgid,
                inicio,
            )

            assinatura = (
                assinatura_pagina(produtos)
                if produtos
                else None
            )

            if (
                assinatura
                and assinatura in assinaturas
            ):

                raise RuntimeError(
                    f"Pagina repetida em {cgid}, "
                    f"posicao {inicio}."
                )

            lote = Counter()

            for item in produtos:

                resultado = _salvar_produto(
                    db,
                    loja,
                    item,
                    produtos_existentes,
                    set(),
                    cgid,
                )

                lote[resultado] += 1

            if assinatura:

                assinaturas.add(assinatura)

            proxima = inicio + len(produtos)

            total = getattr(
                produtos,
                "total",
                None,
            )

            if (
                total is not None
                and total < proxima
            ):

                raise RuntimeError(
                    "Total do catalogo "
                    "inconsistente."
                )

            if (
                total is not None
                and not produtos
                and inicio < total
            ):

                raise RuntimeError(
                    "Pagina vazia antes "
                    "do total informado."
                )

            concluida = (
                proxima == total
                if total is not None
                else len(produtos) < min(
                    TAMANHO_PAGINA,
                    LIMITE_RESULTADOS - inicio,
                )
            )

            # Produtos e checkpoint sao gravados
            # na mesma transacao.

            salvar_checkpoint(
                db,
                loja_codigo,
                cgid,
                proxima,
                assinaturas,
                concluida,
            )

            db.commit()

            contagem.update(lote)

            print(
                f"[OK] Lote gravado: "
                f"loja {loja_codigo}, "
                f"{cgid}, posicao {inicio}, "
                f"{dict(lote)}"
            )

            if concluida:

                break

            inicio = proxima

            time.sleep(
                INTERVALO_ENTRE_REQUISICOES_SEGUNDOS
            )

        time.sleep(
            INTERVALO_ENTRE_CATEGORIAS_SEGUNDOS
        )

    # Reiniciar o ciclo somente quando todas
    # as categorias solicitadas forem concluidas.

    for cgid in categorias:

        db.execute(
            text("""
                DELETE FROM nagumo_coleta_checkpoint
                WHERE loja_codigo = :codigo
                AND categoria = :categoria
            """),
            {
                "codigo": loja_codigo,
                "categoria": cgid,
            },
        )

    db.commit()

    print(
        f"[OK] Loja {loja_codigo} finalizada. "
        f"Resultados: {dict(contagem)}"
    )

    return (
        sum(contagem.values()),
        page,
        context,
        browser,
    )


# ============================================================
# EXECUCAO PRINCIPAL
# ============================================================

def rodar(
    lojas,
    categorias=None,
    todos=False,
):

    playwright = None
    browser = None
    context = None
    db = None

    try:

        db = SessionLocal()
        db.expire_on_commit = False

        playwright = sync_playwright().start()

        browser, context = _criar_navegador(
            playwright
        )

        page = context.new_page()

        _abrir_nagumo(page)

        if todos:

            categorias_processar = (
                _descobrir_departamentos(page)
            )

        elif categorias:

            categorias_processar = categorias

        else:

            raise ValueError(
                "Informe --todos ou --categorias."
            )

        print(
            f"[INFO] Categorias: "
            f"{len(categorias_processar)}"
        )

        print(
            f"[INFO] Intervalo entre paginas: "
            f"{INTERVALO_ENTRE_REQUISICOES_SEGUNDOS}s"
        )

        print(
            f"[INFO] Intervalo entre categorias: "
            f"{INTERVALO_ENTRE_CATEGORIAS_SEGUNDOS}s"
        )

        total_geral = 0
        lojas_concluidas = 0

        for loja in lojas:

            print(
                "[INFO] Loja em processamento: "
                f"{loja['nome']} "
                f"(codigo {loja['codigo']})",
                flush=True,
            )

            total, page, context, browser = (
                _processar_loja(
                    page=page,
                    context=context,
                    db=db,
                    loja_nome=loja["nome"],
                    loja_codigo=loja["codigo"],
                    categorias=categorias_processar,
                    playwright=playwright,
                    browser=browser,
                )
            )

            total_geral += total
            lojas_concluidas += 1

        print()
        print("=" * 70)
        print("SCRAPER FINALIZADO")
        print("=" * 70)

        print(
            f"[OK] Produtos analisados: "
            f"{total_geral}"
        )

        print(
            f"[OK] Lojas concluidas: "
            f"{lojas_concluidas}/{len(lojas)}"
        )

        print(
            f"[OK] Categorias configuradas: "
            f"{len(categorias_processar)}"
        )

        print(
            "[OK] Banco protegido contra "
            "historicos desnecessarios."
        )

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
# ARGUMENTOS
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Scraper Nagumo para o Mercadez."
        )
    )

    parser.add_argument(
        "--loja",
        type=str,
    )

    parser.add_argument(
        "--loja-codigo",
        type=str,
    )

    parser.add_argument(
        "--todas-lojas",
        action="store_true",
    )

    parser.add_argument(
        "--todos",
        action="store_true",
    )

    parser.add_argument(
        "--categorias",
        nargs="+",
    )

    args = parser.parse_args()

    # ========================================================
    # ORDEM ORIGINAL DOS SUPERMERCADOS
    # ========================================================

    lojas_padrao = [

        # POA

        {
            "nome": "Nagumo Poa",
            "codigo": "22",
        },
        {
            "nome": "Nagumo Poa_Kemel",
            "codigo": "45",
        },

        # SUZANO

        {
            "nome": "Nagumo_Suzano_Dona_Benta",
            "codigo": "23",
        },
        {
            "nome": "Nagumo Suzano",
            "codigo": "27",
        },

        # ITAQUAQUECETUBA

        {
            "nome": "Nagumo Itaqua",
            "codigo": "30",
        },
        {
            "nome": "Nagumo_Itaqua_Vila_Zeferina",
            "codigo": "39",
        },

        # MOGI DAS CRUZES

        {
            "nome": "Nagumo_Mogi_Alto_Ipiranga",
            "codigo": "52",
        },

        # GUARULHOS

        {
            "nome": "Nagumo_Guarulhos_Merc_Bonsucesso",
            "codigo": "41",
        },
        {
            "nome": "Nagumo_Guarulhos_Cumbica",
            "codigo": "42",
        },
        {
            "nome": "Nagumo_Guarulhos_Shopping_Pimentas",
            "codigo": "49",
        },
        {
            "nome": "Nagumo_Guarulhos_Continental",
            "codigo": "51",
        },
        {
            "nome": "Nagumo_Guarulhos_Bonsucesso",
            "codigo": "55",
        },
        {
            "nome": "Nagumo_Guarulhos_Elenco",
            "codigo": "56",
        },
        {
            "nome": "Nagumo_Guarulhos_Anel_Viario",
            "codigo": "57",
        },
        {
            "nome": "Nagumo_Guarulhos_Alvorada",
            "codigo": "61",
        },
    ]

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
            "Informe --todas-lojas ou "
            "--loja junto com --loja-codigo."
        )

    if not args.todos and not args.categorias:

        raise SystemExit(
            "Informe --todos ou --categorias."
        )

    rodar(
        lojas=lojas,
        categorias=args.categorias,
        todos=args.todos,
    )


if __name__ == "__main__":

    try:

        main()

    except AcessoRecusado as erro:

        print(
            f"[ERRO] {erro}",
            flush=True,
        )

        raise SystemExit(1)
