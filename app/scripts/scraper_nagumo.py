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
from playwright.sync_api import sync_playwright

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
LIMITE_RESULTADOS = 1000

LATITUDE = "-23.5325875"
LONGITUDE = "-46.335124"


# ============================================================
# SUPERMERCADOS
# ============================================================

LOJAS = [
    {"nome": "Nagumo Poa", "codigo": "22"},
    {"nome": "Nagumo Poa_Kemel", "codigo": "45"},
    {"nome": "Nagumo_Suzano_Dona_Benta", "codigo": "23"},
    {"nome": "Nagumo Suzano", "codigo": "27"},
    {"nome": "Nagumo Itaqua", "codigo": "30"},
    {"nome": "Nagumo_Itaqua_Vila_Zeferina", "codigo": "39"},
    {"nome": "Nagumo_Mogi_Alto_Ipiranga", "codigo": "52"},
    {"nome": "Nagumo_Guarulhos_Merc_Bonsucesso", "codigo": "41"},
    {"nome": "Nagumo_Guarulhos_Cumbica", "codigo": "42"},
    {"nome": "Nagumo_Guarulhos_Shopping_Pimentas", "codigo": "49"},
    {"nome": "Nagumo_Guarulhos_Continental", "codigo": "51"},
    {"nome": "Nagumo_Guarulhos_Bonsucesso", "codigo": "55"},
    {"nome": "Nagumo_Guarulhos_Elenco", "codigo": "56"},
    {"nome": "Nagumo_Guarulhos_Anel_Viario", "codigo": "57"},
    {"nome": "Nagumo_Guarulhos_Alvorada", "codigo": "61"},
]


# ============================================================
# DEPARTAMENTOS
# ============================================================

DEPARTAMENTOS = [
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


# ============================================================
# EXCECOES
# ============================================================

class AcessoRecusado(RuntimeError):

    def __init__(self, status, etapa):

        self.status = status
        self.etapa = etapa

        super().__init__(
            f"HTTP {status} em {etapa}. "
            "Execucao interrompida."
        )


class LimitePaginacaoAtingido(RuntimeError):
    pass


# ============================================================
# DIAGNOSTICO
# ============================================================

def agora_utc():

    return datetime.now(timezone.utc)


def registrar_evento(evento, **dados):

    print(
        json.dumps(
            {
                "evento": evento,
                "utc": agora_utc().isoformat(),
                **dados,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


def verificar_acesso(
    status,
    etapa,
    headers=None,
):

    headers = headers or {}

    headers_seguros = {
        chave: str(headers[chave])[:160]
        for chave in (
            "content-type",
            "retry-after",
            "x-request-id",
            "cf-ray",
            "cf-mitigated",
        )
        if chave in headers
        and headers[chave] is not None
    }

    registrar_evento(
        "http",
        etapa=etapa,
        status=status,
        headers=headers_seguros,
    )

    if status in (403, 429):

        raise AcessoRecusado(
            status,
            etapa,
        )

    if status >= 400:

        raise RuntimeError(
            f"HTTP {status} em {etapa}"
        )


# ============================================================
# CHECKPOINTS
# ============================================================

def ler_checkpoint(
    db,
    codigo,
    categoria,
):

    resultado = db.execute(
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

    if resultado is None:

        return 0, set(), False

    return (
        resultado[0],
        set(json.loads(resultado[1])),
        bool(resultado[2]),
    )


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
            "agora": agora_utc(),
        },
    )


def limpar_checkpoints_concluidos(
    db,
    codigo,
    categorias,
):

    for categoria in categorias:

        db.execute(
            text("""
                DELETE FROM nagumo_coleta_checkpoint
                WHERE loja_codigo = :codigo
                AND categoria = :categoria
                AND concluida = true
            """),
            {
                "codigo": codigo,
                "categoria": categoria,
            },
        )

    db.commit()


# ============================================================
# IDENTIFICACAO DOS PRODUTOS
# ============================================================

def chave_produto(nome):

    return " ".join(
        nome.split()
    ).casefold()


def assinatura_pagina(produtos):

    identificadores = []

    for produto in produtos:

        identificador = (
            produto.get("productID")
            or produto.get("productId")
            or produto.get("id")
            or produto.get("ean")
        )

        if identificador:

            chave = "id:" + str(identificador)

        else:

            chave = (
                "nome:"
                + chave_produto(
                    str(
                        produto.get("productName")
                        or ""
                    )
                )
            )

        identificadores.append(chave)

    conteudo = json.dumps(
        sorted(identificadores),
        ensure_ascii=False,
    )

    return hashlib.sha256(
        conteudo.encode()
    ).hexdigest()


# ============================================================
# NAVEGADOR
# ============================================================

def criar_navegador(playwright):

    browser = playwright.chromium.launch(
        headless=True,
    )

    context = browser.new_context(
        locale="pt-BR",
        timezone_id="America/Sao_Paulo",
        extra_http_headers={
            "Accept-Language": (
                "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
            )
        },
    )

    return browser, context


# ============================================================
# ABRIR NAGUMO
# ============================================================

def abrir_nagumo(page):

    resposta = page.goto(
        BASE,
        wait_until="domcontentloaded",
        timeout=60000,
    )

    if resposta is None:

        raise RuntimeError(
            "Nagumo nao retornou resposta."
        )

    verificar_acesso(
        resposta.status,
        "pagina inicial",
        resposta.headers,
    )

    print(
        "[OK] Nagumo aberto no navegador.",
        flush=True,
    )


# ============================================================
# SELECIONAR SUPERMERCADO
# ============================================================

def selecionar_loja(
    page,
    codigo,
):

    print(
        f"[INFO] Selecionando loja {codigo}..."
    )

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
                "Sites-Nagumo-Site/pt_BR/" +
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

                return {
                    status: resposta.status,
                    texto: await resposta.text(),
                    headers: {
                        "content-type":
                            resposta.headers.get("content-type"),
                        "retry-after":
                            resposta.headers.get("retry-after"),
                        "x-request-id":
                            resposta.headers.get("x-request-id"),
                        "cf-ray":
                            resposta.headers.get("cf-ray")
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
            "storeId": codigo,
            "lat": LATITUDE,
            "lng": LONGITUDE,
        },
    )

    status = resultado["status"]

    verificar_acesso(
        status,
        f"selecao da loja {codigo}",
        resultado.get("headers"),
    )

    if status != 200:

        raise RuntimeError(
            f"Falha na selecao da loja "
            f"{codigo}: HTTP {status}"
        )

    try:

        dados = json.loads(
            resultado["texto"]
        )

    except json.JSONDecodeError as erro:

        raise RuntimeError(
            "Resposta de selecao nao e JSON."
        ) from erro

    if (
        not isinstance(dados, dict)
        or not dados.get("success")
    ):

        raise RuntimeError(
            f"Nagumo nao confirmou a loja {codigo}."
        )

    print(
        f"[OK] Loja {codigo} selecionada."
    )


# ============================================================
# TOTAL DE RESULTADOS
# ============================================================

def total_informado(dados):

    if not isinstance(dados, dict):

        return None

    totais = []

    objetos = (
        dados,
        dados.get("pagination"),
        dados.get("productSearch"),
    )

    campos = (
        "total",
        "totalCount",
        "totalResults",
        "totalProducts",
        "totalHits",
    )

    for objeto in objetos:

        if not isinstance(objeto, dict):

            continue

        for campo in campos:

            valor = objeto.get(campo)

            if type(valor) is int and valor >= 0:

                totais.append(valor)

            elif (
                isinstance(valor, str)
                and valor.isascii()
                and valor.isdecimal()
                and len(valor) <= 12
            ):

                totais.append(int(valor))

    if totais and len(set(totais)) == 1:

        return totais[0]

    return None


# ============================================================
# VALIDAR PAGINACAO
# ============================================================

def verificar_limite_posicao(
    inicio,
    codigo=None,
    categoria=None,
):

    if inicio < 0:

        raise ValueError(
            f"Posicao invalida: {inicio}"
        )

    if inicio >= LIMITE_RESULTADOS:

        registrar_evento(
            "limite_paginacao",
            loja_codigo=codigo,
            categoria=categoria,
            posicao=inicio,
            limite=LIMITE_RESULTADOS,
            checkpoint_preservado=True,
            nova_recusa_http=False,
        )

        raise LimitePaginacaoAtingido(
            f"Limite interno atingido na "
            f"posicao {inicio}. "
            "Checkpoint preservado."
        )


# ============================================================
# CONSULTAR PAGINA
# ============================================================

def buscar_pagina(
    context,
    categoria,
    inicio,
    codigo,
):

    verificar_limite_posicao(
        inicio,
        codigo,
        categoria,
    )

    tamanho = min(
        TAMANHO_PAGINA,
        LIMITE_RESULTADOS - inicio,
    )

    parametros = urlencode(
        {
            "cgid": categoria,
            "start": inicio,
            "sz": tamanho,
        }
    )

    url = (
        f"{BASE}/on/demandware.store/"
        "Sites-Nagumo-Site/pt_BR/"
        f"Search-UpdateGrid?{parametros}"
    )

    print(
        f"[INFO] Loja={codigo} | "
        f"Categoria={categoria} | "
        f"Posicao={inicio} | "
        f"Tamanho={tamanho}"
    )

    inicio_http = time.monotonic()

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

        verificar_acesso(
            resposta.status,
            (
                f"loja {codigo}, "
                f"categoria {categoria}, "
                f"posicao {inicio}"
            ),
            resposta.headers,
        )

        print(
            f"[INFO] Tempo da resposta: "
            f"{duracao:.2f}s"
        )

        try:

            dados = resposta.json()

        except Exception as erro:

            raise RuntimeError(
                "Resposta do catalogo nao e JSON."
            ) from erro

        if not isinstance(dados, dict):

            raise RuntimeError(
                "Formato inesperado do catalogo."
            )

        produtos = dados.get(
            "productsSearchResult"
        )

        if (
            not isinstance(produtos, list)
            or any(
                not isinstance(p, dict)
                for p in produtos
            )
        ):

            raise RuntimeError(
                "Lista de produtos invalida."
            )

        if len(produtos) > tamanho:

            raise RuntimeError(
                "Pagina retornou mais produtos "
                "que o solicitado."
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
                "Pagina sem identificacao "
                "dos produtos."
            )

        total = total_informado(dados)

        print(
            f"[INFO] Categoria '{categoria}': "
            f"posicao {inicio} -> "
            f"{len(produtos)} produtos."
        )

        print(
            "[INFO] Total informado pelo servidor: "
            f"{total if total is not None else 'indisponivel'}"
        )

        return produtos, total, tamanho

    finally:

        resposta.dispose()


# ============================================================
# CARREGAR PRODUTOS EXISTENTES
# ============================================================

def carregar_produtos(
    db,
    loja_id,
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
        produto is None
        for produto in mapa.values()
    )

    if ambiguos:

        print(
            f"[AVISO] {ambiguos} nomes ambiguos. "
            "Registros preservados."
        )

    print(
        f"[OK] {len(mapa)} produtos "
        "carregados em memoria."
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
        r"\.(webp|png|jpe?g|gif|avif)$",
        parsed.path,
        re.I,
    ):

        return None

    arquivo = (
        parsed.path
        .rsplit("/", 1)[-1]
        .lower()
    )

    if arquivo in {
        "meunagumo.png",
        "noimage.png",
        "placeholder.png",
    }:

        return None

    return url


# ============================================================
# EXTRAIR IMAGENS DO PRODUTO
# ============================================================

def extrair_imagens(produto):

    imagens = []
    vistos = set()

    campos_imagem = {
        "image",
        "images",
        "imagegroups",
        "imagegroup",
        "productimage",
        "productimages",
        "imageurl",
        "thumbnail",
        "thumbnailurl",
        "largeimage",
        "smallimage",
        "mediumimage",
        "primaryimage",
        "variationimages",
    }

    campos_url = {
        "url",
        "src",
        "link",
        "absurl",
        "absoluteurl",
        "href",
        "large",
        "medium",
        "small",
        "hires",
        "desktop",
        "mobile",
    }

    def guardar(valor):

        url = normalizar_url_imagem(valor)

        if not url or url in vistos:

            return

        vistos.add(url)

        imagens.append(url)

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
                    or isinstance(
                        item,
                        (list, dict),
                    )
                ):

                    percorrer(
                        item,
                        True,
                        profundidade + 1,
                    )

    percorrer(produto)

    return imagens


# ============================================================
# SALVAR OU ATUALIZAR PRODUTO
# ============================================================

def salvar_produto(
    db,
    loja,
    dados,
    existentes,
    categoria,
):

    nome = dados.get("productName")

    if not isinstance(nome, str):

        return "ignorado"

    nome = nome.strip()

    if not nome:

        return "ignorado"

    preco_dados = dados.get("price") or {}

    if not isinstance(preco_dados, dict):

        return "ignorado"

    venda = preco_dados.get("sales") or {}

    if not isinstance(venda, dict):

        return "ignorado"

    preco_raw = venda.get("value")

    if preco_raw is None:

        return "ignorado"

    try:

        preco = Decimal(str(preco_raw))

    except Exception:

        return "ignorado"

    if not preco.is_finite() or preco < 0:

        return "ignorado"

    imagens = extrair_imagens(dados)

    chave = chave_produto(nome)

    if (
        chave in existentes
        and existentes[chave] is None
    ):

        return "ignorado"

    produto = existentes.get(chave)

    # --------------------------------------------------------
    # PRODUTO NOVO
    # --------------------------------------------------------

    if produto is None:

        produto = Produto(
            nome_produto=nome,
            tags=categoria,
            preco=preco,
            quantidade=0,
            origem="EXTERNO",
            loja_externa_id=loja.id,
            imagem_url=(
                imagens[0]
                if imagens
                else None
            ),
            imagens_urls=imagens,
        )

        db.add(produto)

        db.flush()

        db.add(
            HistoricoPreco(
                produto_id=produto.id,
                preco=preco,
            )
        )

        existentes[chave] = produto

        return "novo"

    # --------------------------------------------------------
    # CATEGORIA
    # --------------------------------------------------------

    if categoria and not produto.tags:

        produto.tags = categoria

    # --------------------------------------------------------
    # PRESERVAR IMAGENS EXISTENTES
    # --------------------------------------------------------

    principal = normalizar_url_imagem(
        produto.imagem_url
    )

    imagens_antigas = (
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
                *imagens_antigas,
                *imagens,
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

        nova_principal = (
            principal or mescladas[0]
        )

        if produto.imagem_url != nova_principal:

            produto.imagem_url = nova_principal

    # --------------------------------------------------------
    # PRECO SEM ALTERACAO
    # --------------------------------------------------------

    if produto.preco == preco:

        return "sem_alteracao"

    # --------------------------------------------------------
    # PRECO ALTERADO
    # --------------------------------------------------------

    produto.preco = preco

    db.add(
        HistoricoPreco(
            produto_id=produto.id,
            preco=preco,
        )
    )

    return "preco_alterado"


# ============================================================
# PROCESSAR CATEGORIA
# ============================================================

def processar_categoria(
    db,
    context,
    loja,
    codigo,
    categoria,
    existentes,
):

    inicio, assinaturas, concluida = (
        ler_checkpoint(
            db,
            codigo,
            categoria,
        )
    )

    db.commit()

    contagem = Counter()

    print(
        f"[INFO] Categoria: {categoria}"
    )

    if concluida:

        print(
            "[INFO] Categoria ja concluida "
            "neste ciclo."
        )

        return contagem

    print(
        f"[INFO] Checkpoint encontrado: "
        f"posicao {inicio}"
    )

    # --------------------------------------------------------
    # VALIDACAO ANTES DE NOVAS CONSULTAS
    # --------------------------------------------------------

    verificar_limite_posicao(
        inicio,
        codigo,
        categoria,
    )

    # --------------------------------------------------------
    # PAGINACAO
    # --------------------------------------------------------

    while True:

        produtos, total, tamanho = buscar_pagina(
            context,
            categoria,
            inicio,
            codigo,
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

            registrar_evento(
                "pagina_repetida",
                loja_codigo=codigo,
                categoria=categoria,
                posicao=inicio,
            )

            raise RuntimeError(
                f"Pagina repetida em {categoria}, "
                f"posicao {inicio}."
            )

        proxima = inicio + len(produtos)

        # ----------------------------------------------------
        # VALIDAR CONSISTENCIA
        # ----------------------------------------------------

        if total is not None and total < proxima:

            raise RuntimeError(
                "Total informado pelo servidor "
                "e inconsistente."
            )

        if (
            total is not None
            and not produtos
            and inicio < total
        ):

            raise RuntimeError(
                "Pagina vazia antes do "
                "total informado."
            )

        # ----------------------------------------------------
        # PROCESSAR PRODUTOS
        # ----------------------------------------------------

        lote = Counter()

        for produto in produtos:

            resultado = salvar_produto(
                db,
                loja,
                produto,
                existentes,
                categoria,
            )

            lote[resultado] += 1

        if assinatura:

            assinaturas.add(assinatura)

        if total is not None:

            concluida = proxima == total

        else:

            concluida = len(produtos) < tamanho

        # ----------------------------------------------------
        # GRAVAR PRODUTOS E CHECKPOINT
        # ----------------------------------------------------

        salvar_checkpoint(
            db,
            codigo,
            categoria,
            proxima,
            assinaturas,
            concluida,
        )

        db.commit()

        contagem.update(lote)

        print(
            f"[OK] Lote gravado: "
            f"loja {codigo}, "
            f"{categoria}, "
            f"posicao {inicio}, "
            f"{dict(lote)}",
            flush=True,
        )

        if concluida:

            print(
                f"[OK] Categoria {categoria} "
                "concluida."
            )

            break

        inicio = proxima

        verificar_limite_posicao(
            inicio,
            codigo,
            categoria,
        )

        time.sleep(
            INTERVALO_ENTRE_REQUISICOES_SEGUNDOS
        )

    return contagem


# ============================================================
# PROCESSAR SUPERMERCADO
# ============================================================

def processar_loja(
    db,
    page,
    context,
    nome,
    codigo,
    categorias,
):

    print()
    print("=" * 70)
    print(
        f"LOJA: {nome} (codigo {codigo})"
    )
    print("=" * 70)

    selecionar_loja(
        page,
        codigo,
    )

    loja = (
        db.query(LojaExterna)
        .filter_by(nome=nome)
        .one_or_none()
    )

    if loja is None:

        loja = LojaExterna(
            nome=nome,
            dominio="www.nagumo.com.br",
            plataforma="SFCC",
        )

        db.add(loja)

        db.flush()

        print(
            f"[OK] Loja externa criada: {nome}"
        )

    else:

        print(
            f"[OK] Loja externa encontrada: {nome}"
        )

    existentes = carregar_produtos(
        db,
        loja.id,
    )

    db.commit()

    contagem = Counter()

    inicio_loja = time.monotonic()

    for indice, categoria in enumerate(
        categorias,
        start=1,
    ):

        print()
        print(
            f"[INFO] Categoria "
            f"{indice}/{len(categorias)}: "
            f"{categoria}"
        )

        resultado = processar_categoria(
            db,
            context,
            loja,
            codigo,
            categoria,
            existentes,
        )

        contagem.update(resultado)

        time.sleep(
            INTERVALO_ENTRE_CATEGORIAS_SEGUNDOS
        )

    limpar_checkpoints_concluidos(
        db,
        codigo,
        categorias,
    )

    duracao = (
        time.monotonic() - inicio_loja
    )

    print()
    print("=" * 70)
    print(
        f"[OK] Loja {codigo} finalizada."
    )
    print(
        f"[INFO] Produtos novos: "
        f"{contagem['novo']}"
    )
    print(
        f"[INFO] Precos alterados: "
        f"{contagem['preco_alterado']}"
    )
    print(
        f"[INFO] Sem alteracao: "
        f"{contagem['sem_alteracao']}"
    )
    print(
        f"[INFO] Ignorados: "
        f"{contagem['ignorado']}"
    )
    print(
        f"[INFO] Duracao: {duracao:.2f}s"
    )
    print("=" * 70)

    return contagem


# ============================================================
# EXECUCAO PRINCIPAL
# ============================================================

def rodar(
    lojas,
    categorias,
):

    db = None
    browser = None
    context = None

    inicio_execucao = time.monotonic()

    contagem_geral = Counter()

    lojas_concluidas = 0

    try:

        db = SessionLocal()

        db.expire_on_commit = False

        with sync_playwright() as playwright:

            browser, context = criar_navegador(
                playwright
            )

            try:

                page = context.new_page()

                abrir_nagumo(page)

                print(
                    f"[OK] {len(categorias)} "
                    "departamentos configurados."
                )

                for categoria in categorias:

                    print(f"       - {categoria}")

                print(
                    f"[INFO] Total de lojas: "
                    f"{len(lojas)}"
                )

                print(
                    f"[INFO] Intervalo entre paginas: "
                    f"{INTERVALO_ENTRE_REQUISICOES_SEGUNDOS}s"
                )

                print(
                    f"[INFO] Intervalo entre categorias: "
                    f"{INTERVALO_ENTRE_CATEGORIAS_SEGUNDOS}s"
                )

                for loja in lojas:

                    print(
                        "[INFO] Loja em processamento: "
                        f"{loja['nome']} "
                        f"(codigo {loja['codigo']})",
                        flush=True,
                    )

                    contagem = processar_loja(
                        db,
                        page,
                        context,
                        loja["nome"],
                        loja["codigo"],
                        categorias,
                    )

                    contagem_geral.update(
                        contagem
                    )

                    lojas_concluidas += 1

            finally:

                try:

                    if context is not None:

                        context.close()

                finally:

                    if browser is not None:

                        browser.close()

        print()
        print("=" * 70)
        print("SCRAPER FINALIZADO")
        print("=" * 70)

        print(
            f"[OK] Lojas concluidas: "
            f"{lojas_concluidas}/{len(lojas)}"
        )

        print(
            f"[OK] Produtos analisados: "
            f"{sum(contagem_geral.values())}"
        )

        print(
            f"[OK] Produtos novos: "
            f"{contagem_geral['novo']}"
        )

        print(
            f"[OK] Precos alterados: "
            f"{contagem_geral['preco_alterado']}"
        )

        print(
            f"[OK] Sem alteracao: "
            f"{contagem_geral['sem_alteracao']}"
        )

        print(
            f"[OK] Ignorados: "
            f"{contagem_geral['ignorado']}"
        )

    except Exception:

        if db is not None:

            db.rollback()

        raise

    finally:

        if db is not None:

            db.close()

        duracao = (
            time.monotonic() - inicio_execucao
        )

        registrar_evento(
            "fim_execucao",
            lojas_concluidas=lojas_concluidas,
            total_lojas=len(lojas),
            duracao_segundos=round(duracao, 2),
        )


# ============================================================
# ARGUMENTOS
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description="Scraper Nagumo - Mercadez"
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

    # --------------------------------------------------------
    # DEFINIR LOJAS
    # --------------------------------------------------------

    if args.todas_lojas:

        lojas = LOJAS

    elif args.loja and args.loja_codigo:

        lojas = [
            {
                "nome": args.loja,
                "codigo": args.loja_codigo,
            }
        ]

    else:

        parser.error(
            "Informe --todas-lojas ou "
            "--loja e --loja-codigo."
        )

    # --------------------------------------------------------
    # DEFINIR CATEGORIAS
    # --------------------------------------------------------

    if args.todos:

        categorias = DEPARTAMENTOS

    elif args.categorias:

        categorias = list(
            dict.fromkeys(
                args.categorias
            )
        )

        invalidas = [
            categoria
            for categoria in categorias
            if categoria not in DEPARTAMENTOS
        ]

        if invalidas:

            parser.error(
                "Categorias invalidas: "
                + ", ".join(invalidas)
            )

    else:

        parser.error(
            "Informe --todos ou --categorias."
        )

    rodar(
        lojas,
        categorias,
    )


# ============================================================
# TRATAMENTO FINAL DE ERROS
# ============================================================

if __name__ == "__main__":

    try:

        main()

    except LimitePaginacaoAtingido as erro:

        print(
            f"[AVISO] {erro}",
            flush=True,
        )

        print(
            "[INFO] Nenhuma nova recusa HTTP "
            "foi registrada neste limite.",
            flush=True,
        )

        print(
            "[INFO] Produtos e checkpoints "
            "preservados.",
            flush=True,
        )

        raise SystemExit(2)

    except AcessoRecusado as erro:

        registrar_evento(
            "acesso_recusado",
            status=erro.status,
            etapa=erro.etapa,
        )

        print(
            f"[ERRO HTTP] {erro}",
            flush=True,
        )

        raise SystemExit(1)

    except Exception as erro:

        registrar_evento(
            "erro_execucao",
            tipo=type(erro).__name__,
        )

        raise
