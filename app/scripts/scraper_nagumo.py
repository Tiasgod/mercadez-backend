from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time

from collections import Counter
from datetime import datetime, timezone
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

TAMANHO_PAGINA = 40

INTERVALO_PAGINAS = 3.0
INTERVALO_CATEGORIAS = 3.0
INTERVALO_LOJAS = 5.0

LATITUDE = "-23.5325875"
LONGITUDE = "-46.335124"

LIMITE_PAGINACAO = int(
    os.getenv("NAGUMO_LIMITE_PAGINACAO", "0")
)


# ============================================================
# LOJAS
# ============================================================

LOJAS = [
    ("Nagumo Poa", "22"),
    ("Nagumo Poa_Kemel", "45"),
    ("Nagumo_Suzano_Dona_Benta", "23"),
    ("Nagumo Suzano", "27"),
    ("Nagumo Itaqua", "30"),
    ("Nagumo_Itaqua_Vila_Zeferina", "39"),
    ("Nagumo_Mogi_Alto_Ipiranga", "52"),
    ("Nagumo_Guarulhos_Merc_Bonsucesso", "41"),
    ("Nagumo_Guarulhos_Cumbica", "42"),
    ("Nagumo_Guarulhos_Shopping_Pimentas", "49"),
    ("Nagumo_Guarulhos_Continental", "51"),
    ("Nagumo_Guarulhos_Bonsucesso", "55"),
    ("Nagumo_Guarulhos_Elenco", "56"),
    ("Nagumo_Guarulhos_Anel_Viario", "57"),
    ("Nagumo_Guarulhos_Alvorada", "61"),
]


# ============================================================
# CATEGORIAS
# ============================================================

CATEGORIAS = [
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
            f"HTTP {status} em {etapa}"
        )


class FalhaColeta(RuntimeError):
    pass


# ============================================================
# LOGS
# ============================================================

def agora():

    return datetime.now(timezone.utc)


def evento(tipo, **dados):

    print(
        json.dumps(
            {
                "evento": tipo,
                "utc": agora().isoformat(),
                **dados,
            },
            ensure_ascii=False,
            default=str,
        ),
        flush=True,
    )


def verificar_http(status, etapa, headers=None):

    headers = headers or {}

    seguros = {
        chave: str(headers[chave])
        for chave in (
            "content-type",
            "retry-after",
            "cf-ray",
            "x-request-id",
        )
        if headers.get(chave) is not None
    }

    evento(
        "http",
        status=status,
        etapa=etapa,
        headers=seguros,
    )

    if status in (403, 429):

        raise AcessoRecusado(status, etapa)

    if status != 200:

        raise FalhaColeta(
            f"HTTP {status} em {etapa}"
        )


# ============================================================
# CHECKPOINTS
# ============================================================

def ler_checkpoint(db, codigo, categoria):

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

    assinaturas = resultado[1]

    if isinstance(assinaturas, str):

        assinaturas = json.loads(assinaturas)

    return (
        int(resultado[0]),
        set(assinaturas or []),
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
                    EXCLUDED.proxima_posicao,
                assinaturas =
                    EXCLUDED.assinaturas,
                concluida =
                    EXCLUDED.concluida,
                atualizado_em =
                    EXCLUDED.atualizado_em
        """),
        {
            "codigo": codigo,
            "categoria": categoria,
            "posicao": posicao,
            "assinaturas": json.dumps(
                sorted(assinaturas)
            ),
            "concluida": concluida,
            "agora": agora(),
        },
    )


def limpar_checkpoints(db, codigo, categorias):

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
# IDENTIFICACAO DE PRODUTOS
# ============================================================

def chave_produto(nome):

    return " ".join(nome.split()).casefold()


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

            chave = "nome:" + chave_produto(
                str(produto.get("productName") or "")
            )

        identificadores.append(chave)

    conteudo = json.dumps(
        sorted(identificadores),
        ensure_ascii=False,
    )

    return hashlib.sha256(
        conteudo.encode("utf-8")
    ).hexdigest()


# ============================================================
# NAVEGADOR
# ============================================================

def abrir_nagumo(page):

    resposta = page.goto(
        BASE,
        wait_until="domcontentloaded",
        timeout=60000,
    )

    if resposta is None:

        raise FalhaColeta(
            "Nagumo nao retornou resposta."
        )

    verificar_http(
        resposta.status,
        "pagina inicial",
        resposta.headers,
    )

    print("[OK] Nagumo aberto.")


def selecionar_loja(page, codigo):

    resultado = page.evaluate(
        """
        async ({codigo, lat, lng}) => {

            const parametros = new URLSearchParams({
                storeId: codigo,
                method: "Retirada",
                lat: lat,
                lng: lng
            });

            const url =
                "/on/demandware.store/" +
                "Sites-Nagumo-Site/pt_BR/" +
                "Stores-SelectStore?" +
                parametros.toString();

            const resposta = await fetch(url, {
                method: "GET",
                credentials: "include",
                headers: {
                    "Accept": "*/*",
                    "X-Requested-With": "XMLHttpRequest"
                }
            });

            return {
                status: resposta.status,
                texto: await resposta.text(),
                headers: {
                    "content-type":
                        resposta.headers.get("content-type"),
                    "retry-after":
                        resposta.headers.get("retry-after"),
                    "cf-ray":
                        resposta.headers.get("cf-ray")
                }
            };
        }
        """,
        {
            "codigo": codigo,
            "lat": LATITUDE,
            "lng": LONGITUDE,
        },
    )

    verificar_http(
        resultado["status"],
        f"selecao da loja {codigo}",
        resultado.get("headers"),
    )

    dados = json.loads(resultado["texto"])

    if not isinstance(dados, dict):

        raise FalhaColeta(
            "Resposta de selecao invalida."
        )

    if not dados.get("success"):

        raise FalhaColeta(
            f"Nao foi possivel selecionar loja {codigo}"
        )

    print(f"[OK] Loja {codigo} selecionada.")


# ============================================================
# TOTAL DE PRODUTOS
# ============================================================

def total_informado(dados):

    totais = []

    objetos = [
        dados,
        dados.get("pagination"),
        dados.get("productSearch"),
    ]

    campos = [
        "total",
        "totalCount",
        "totalResults",
        "totalProducts",
        "totalHits",
    ]

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
# CONSULTAR PAGINA
# ============================================================

def buscar_pagina(context, codigo, categoria, inicio):

    restante = LIMITE_PAGINACAO - inicio

    if restante <= 0:

        raise FalhaColeta(
            f"Limite confirmado de paginacao "
            f"atingido na posicao {inicio}."
        )

    tamanho = min(TAMANHO_PAGINA, restante)

    parametros = urlencode({
        "cgid": categoria,
        "start": inicio,
        "sz": tamanho,
    })

    url = (
        f"{BASE}/on/demandware.store/"
        "Sites-Nagumo-Site/pt_BR/"
        f"Search-UpdateGrid?{parametros}"
    )

    print(
        f"[INFO] Loja={codigo} | "
        f"Categoria={categoria} | "
        f"Posicao={inicio}"
    )

    resposta = context.request.get(
        url,
        timeout=60000,
        headers={
            "Accept": "*/*",
            "Referer": BASE + "/",
        },
    )

    try:

        verificar_http(
            resposta.status,
            (
                f"loja {codigo}, "
                f"categoria {categoria}, "
                f"posicao {inicio}"
            ),
            resposta.headers,
        )

        try:

            dados = resposta.json()

        except Exception as erro:

            raise FalhaColeta(
                "Resposta do catalogo nao e JSON."
            ) from erro

        if not isinstance(dados, dict):

            raise FalhaColeta(
                "Formato de catalogo invalido."
            )

        produtos = dados.get(
            "productsSearchResult"
        )

        if not isinstance(produtos, list):

            raise FalhaColeta(
                "Lista de produtos nao encontrada."
            )

        if any(
            not isinstance(p, dict)
            for p in produtos
        ):

            raise FalhaColeta(
                "Produto com formato invalido."
            )

        if len(produtos) > tamanho:

            raise FalhaColeta(
                "Quantidade de produtos inconsistente."
            )

        total = total_informado(dados)

        print(
            f"[INFO] Produtos recebidos: "
            f"{len(produtos)}"
        )

        print(
            f"[INFO] Total informado: {total}"
        )

        return produtos, total, tamanho

    finally:

        resposta.dispose()


# ============================================================
# IMAGENS
# ============================================================

def normalizar_imagem(valor):

    if not isinstance(valor, str):

        return None

    if not valor.strip():

        return None

    url = urljoin(BASE + "/", valor.strip())

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

    if parsed.scheme not in ("http", "https"):

        return None

    if not parsed.hostname:

        return None

    if re.search(r"https?://", parsed.path, re.I):

        return None

    if len(url) > 2048:

        return None

    if any(c.isspace() for c in url):

        return None

    if not re.search(
        r"\.(webp|png|jpe?g|gif|avif)$",
        parsed.path,
        re.I,
    ):

        return None

    arquivo = parsed.path.rsplit("/", 1)[-1].lower()

    if arquivo in {
        "meunagumo.png",
        "noimage.png",
        "placeholder.png",
    }:

        return None

    return url


def extrair_imagens(produto):

    imagens = []

    campos = {
        "image",
        "images",
        "imagegroups",
        "imageurl",
        "productimage",
        "productimages",
        "thumbnail",
        "thumbnailurl",
        "largeimage",
        "primaryimage",
        "variationimages",
    }

    def percorrer(valor, contexto=False, nivel=0):

        if nivel > 10:

            return

        if isinstance(valor, str):

            if contexto:

                url = normalizar_imagem(valor)

                if url and url not in imagens:

                    imagens.append(url)

        elif isinstance(valor, list):

            for item in valor:

                percorrer(
                    item,
                    contexto,
                    nivel + 1,
                )

        elif isinstance(valor, dict):

            for chave, item in valor.items():

                nome = (
                    chave.lower()
                    .replace("_", "")
                    .replace("-", "")
                )

                imagem = (
                    contexto
                    or nome in campos
                    or nome.startswith("image")
                    or nome.endswith("image")
                )

                percorrer(
                    item,
                    imagem,
                    nivel + 1,
                )

    percorrer(produto)

    return imagens


# ============================================================
# CARREGAR PRODUTOS
# ============================================================

def carregar_produtos(db, loja_id):

    produtos = (
        db.query(Produto)
        .filter(
            Produto.loja_externa_id == loja_id
        )
        .all()
    )

    existentes = {}

    for produto in produtos:

        nome = (
            produto.nome_produto or ""
        ).strip()

        if not nome:

            continue

        chave = chave_produto(nome)

        if chave in existentes:

            existentes[chave] = None

        else:

            existentes[chave] = produto

    print(
        f"[OK] {len(existentes)} "
        "chaves carregadas."
    )

    return existentes


# ============================================================
# SALVAR PRODUTO
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

    try:

        preco = Decimal(
            str(venda.get("value"))
        )

    except Exception:

        return "ignorado"

    if not preco.is_finite() or preco < 0:

        return "ignorado"

    chave = chave_produto(nome)

    imagens = extrair_imagens(dados)

    if chave in existentes and existentes[chave] is None:

        return "ignorado"

    produto = existentes.get(chave)

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
                imagens[0] if imagens else None
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

    # CATEGORIA

    if categoria and not produto.tags:

        produto.tags = categoria

    # PRESERVAR IMAGENS

    antigas = (
        produto.imagens_urls
        if isinstance(produto.imagens_urls, list)
        else []
    )

    mescladas = list(
        dict.fromkeys(
            url
            for url in [
                produto.imagem_url,
                *antigas,
                *imagens,
            ]
            if isinstance(url, str) and url.strip()
        )
    )

    if mescladas != antigas:

        produto.imagens_urls = mescladas

    if not produto.imagem_url and mescladas:

        produto.imagem_url = mescladas[0]

    # PRECO

    if produto.preco == preco:

        return "sem_alteracao"

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
    contagem,
    progresso,
):

    inicio, assinaturas, concluida = ler_checkpoint(
        db,
        codigo,
        categoria,
    )

    db.commit()

    progresso["categoria"] = categoria
    progresso["posicao"] = inicio

    if concluida:

        print(
            f"[INFO] {categoria} ja concluida."
        )

        return

    while True:

        progresso["posicao"] = inicio

        produtos, total, tamanho = buscar_pagina(
            context,
            codigo,
            categoria,
            inicio,
        )

        assinatura = (
            assinatura_pagina(produtos)
            if produtos
            else None
        )

        if assinatura and assinatura in assinaturas:

            raise FalhaColeta(
                f"Pagina repetida na posicao {inicio}"
            )

        proxima = inicio + len(produtos)

        if total is not None and total < proxima:

            raise FalhaColeta(
                "Total de produtos inconsistente."
            )

        if total is not None and not produtos and inicio < total:

            raise FalhaColeta(
                "Pagina vazia antes do total informado."
            )

        lote = Counter()

        for dados in produtos:

            resultado = salvar_produto(
                db,
                loja,
                dados,
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

        progresso["posicao"] = proxima

        print(
            f"[OK] Lote gravado: "
            f"loja={codigo}, "
            f"categoria={categoria}, "
            f"posicao={inicio}, "
            f"{dict(lote)}",
            flush=True,
        )

        if concluida:

            print(
                f"[OK] Categoria {categoria} concluida."
            )

            return

        inicio = proxima

        time.sleep(INTERVALO_PAGINAS)


# ============================================================
# PROCESSAR LOJA
# ============================================================

def processar_loja(
    db,
    page,
    context,
    nome,
    codigo,
    categorias,
    contagem,
    progresso,
):

    print("=" * 70)
    print(f"LOJA: {nome} (codigo {codigo})")
    print("=" * 70)

    selecionar_loja(page, codigo)

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

    existentes = carregar_produtos(
        db,
        loja.id,
    )

    db.commit()

    for categoria in categorias:

        processar_categoria(
            db,
            context,
            loja,
            codigo,
            categoria,
            existentes,
            contagem,
            progresso,
        )

        time.sleep(INTERVALO_CATEGORIAS)

    limpar_checkpoints(
        db,
        codigo,
        categorias,
    )

    print(
        f"[OK] Loja {nome} concluida."
    )


# ============================================================
# RELATORIO FINAL
# ============================================================

def gerar_relatorio(
    lojas,
    resultados,
    erros,
    contagem,
    inicio,
):

    processadas = len(resultados)

    concluidas = sum(
        r["status"] == "concluida"
        for r in resultados
    )

    falhas = processadas - concluidas

    relatorio = {
        "lojas_programadas": len(lojas),
        "lojas_processadas": processadas,
        "lojas_concluidas": concluidas,
        "lojas_com_falhas": falhas,
        "lojas_nao_processadas": (
            len(lojas) - processadas
        ),
        "produtos_analisados": sum(
            contagem.values()
        ),
        "produtos_novos": contagem["novo"],
        "precos_alterados": contagem[
            "preco_alterado"
        ],
        "sem_alteracao": contagem[
            "sem_alteracao"
        ],
        "ignorados": contagem["ignorado"],
        "duracao_segundos": round(
            time.monotonic() - inicio,
            2,
        ),
        "resultados": resultados,
        "erros": erros,
    }

    print()
    print("=" * 70)
    print("MERCADEZ - RELATORIO FINAL")
    print("=" * 70)

    for chave, valor in relatorio.items():

        if chave not in ("resultados", "erros"):

            print(f"{chave}: {valor}")

    print()
    print("DETALHAMENTO DAS FALHAS")
    print("=" * 70)

    if not erros:

        print("Nenhuma falha registrada.")

    for erro in erros:

        print()
        print(f"Loja: {erro['loja']}")
        print(f"Codigo: {erro['codigo']}")
        print(f"Categoria: {erro['categoria']}")
        print(f"Posicao: {erro['posicao']}")
        print(f"Tipo: {erro['tipo']}")
        print(f"Mensagem: {erro['mensagem']}")
        print(f"HTTP: {erro['status_http']}")
        print(f"Horario: {erro['horario']}")

    os.makedirs(
        "diagnostico",
        exist_ok=True,
    )

    with open(
        "diagnostico/relatorio_scraper.json",
        "w",
        encoding="utf-8",
    ) as arquivo:

        json.dump(
            relatorio,
            arquivo,
            ensure_ascii=False,
            indent=2,
        )

    evento(
        "resultado_coleta",
        **relatorio,
    )


# ============================================================
# EXECUCAO
# ============================================================

def rodar(lojas, categorias):

    inicio = time.monotonic()

    erros = []
    resultados = []
    contagem = Counter()

    acesso_recusado = False

    try:

        if LIMITE_PAGINACAO <= 0:

            raise FalhaColeta(
                "Configure NAGUMO_LIMITE_PAGINACAO "
                "com o limite confirmado pelo fornecedor."
            )

        with sync_playwright() as playwright:

            browser = playwright.chromium.launch(
                headless=True
            )

            context = browser.new_context(
                locale="pt-BR",
                timezone_id="America/Sao_Paulo",
            )

            try:

                page = context.new_page()

                abrir_nagumo(page)

                for nome, codigo in lojas:

                    print(
                        "[INFO] Loja em processamento: "
                        f"{nome} (codigo {codigo})"
                    )

                    db = SessionLocal()
                    db.expire_on_commit = False

                    progresso = {
                        "categoria": None,
                        "posicao": None,
                    }

                    status_loja = "concluida"

                    try:

                        processar_loja(
                            db,
                            page,
                            context,
                            nome,
                            codigo,
                            categorias,
                            contagem,
                            progresso,
                        )

                    except Exception as erro:

                        db.rollback()

                        status_loja = "falha"

                        registro = {
                            "loja": nome,
                            "codigo": codigo,
                            "categoria": progresso[
                                "categoria"
                            ],
                            "posicao": progresso[
                                "posicao"
                            ],
                            "tipo": type(erro).__name__,
                            "mensagem": str(erro),
                            "status_http": getattr(
                                erro,
                                "status",
                                None,
                            ),
                            "horario": agora().isoformat(),
                        }

                        erros.append(registro)

                        evento(
                            "erro_loja",
                            **registro,
                        )

                        if isinstance(
                            erro,
                            AcessoRecusado,
                        ):

                            acesso_recusado = True

                            print(
                                "[ERRO] Acesso recusado. "
                                "Consultas interrompidas."
                            )

                        else:

                            print(
                                "[AVISO] Falha tecnica "
                                f"na loja {nome}."
                            )

                            print(
                                "[INFO] Lotes anteriores "
                                "preservados."
                            )

                            print(
                                "[INFO] Avancando para "
                                "a proxima loja."
                            )

                    finally:

                        db.close()

                        resultados.append({
                            "loja": nome,
                            "codigo": codigo,
                            "status": status_loja,
                        })

                    if acesso_recusado:

                        break

                    time.sleep(INTERVALO_LOJAS)

            finally:

                try:

                    context.close()

                finally:

                    browser.close()

    except Exception as erro:

        erros.append({
            "loja": "Execucao geral",
            "codigo": None,
            "categoria": None,
            "posicao": None,
            "tipo": type(erro).__name__,
            "mensagem": str(erro),
            "status_http": getattr(
                erro,
                "status",
                None,
            ),
            "horario": agora().isoformat(),
        })

    finally:

        gerar_relatorio(
            lojas,
            resultados,
            erros,
            contagem,
            inicio,
        )

    return 1 if erros else 0


# ============================================================
# ARGUMENTOS
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description="Scraper Nagumo - Mercadez"
    )

    parser.add_argument("--loja")

    parser.add_argument("--loja-codigo")

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

    if args.todas_lojas:

        lojas = LOJAS

    elif args.loja and args.loja_codigo:

        lojas = [
            (args.loja, args.loja_codigo)
        ]

    else:

        parser.error(
            "Informe --todas-lojas ou "
            "--loja e --loja-codigo."
        )

    if args.todos:

        categorias = CATEGORIAS

    elif args.categorias:

        categorias = list(
            dict.fromkeys(args.categorias)
        )

        invalidas = [
            c for c in categorias
            if c not in CATEGORIAS
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

    return rodar(lojas, categorias)


if __name__ == "__main__":

    raise SystemExit(main())
