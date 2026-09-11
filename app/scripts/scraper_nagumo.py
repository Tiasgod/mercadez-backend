"""
Scraper de preços do Nagumo (nagumo.com.br).

Fluxo:

1. Abre o Nagumo através de um Chromium real usando Playwright.
2. Seleciona a loja através de Stores-SelectStore.
3. Reutiliza a sessão do navegador para consultar Search-UpdateGrid.
4. Extrai os produtos e preços.
5. Salva/atualiza os produtos no PostgreSQL.

Exemplos:

    python -m app.scripts.scraper_nagumo ^
        --loja "Nagumo Poa" ^
        --loja-codigo 22 ^
        --categorias hortifruti

    python -m app.scripts.scraper_nagumo ^
        --loja "Nagumo Poa_Kemel" ^
        --loja-codigo 45 ^
        --categorias hortifruti
"""

from __future__ import annotations

import argparse
import json
import time
from decimal import Decimal
from urllib.parse import urlencode

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

INTERVALO_ENTRE_REQUISICOES_SEGUNDOS = 2.0

TAMANHO_PAGINA = 40

LATITUDE = "-23.5325875"

LONGITUDE = "-46.335124"


def _criar_navegador(
    playwright: Playwright,
):
    """
    Cria um Chromium real através do Playwright.
    """

    browser = playwright.chromium.launch(
        headless=True,
    )

    context = browser.new_context(
        locale="pt-BR",
        timezone_id="America/Sao_Paulo",
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/152.0.0.0 Safari/537.36"
        ),
        extra_http_headers={
            "Accept-Language": (
                "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
            ),
        },
    )

    return browser, context


def _abrir_nagumo(
    page: Page,
) -> None:
    """
    Abre a página inicial para criar a sessão
    do navegador antes da seleção da loja.
    """

    resposta = page.goto(
        BASE,
        wait_until="domcontentloaded",
        timeout=60000,
    )

    if resposta is None:
        raise RuntimeError(
            "O Nagumo não retornou resposta ao abrir a página inicial."
        )

    if resposta.status >= 400:
        raise RuntimeError(
            f"Nagumo retornou HTTP {resposta.status} "
            "ao abrir a página inicial."
        )

    print("[OK] Nagumo aberto no navegador.")


def _selecionar_loja(
    page: Page,
    loja_codigo: str,
    lat: str,
    lng: str,
) -> None:
    """
    Seleciona a loja executando o fetch dentro da própria
    página do Nagumo.

    Dessa forma, a requisição utiliza a sessão real do
    Chromium, incluindo os cookies criados pelo site.
    """

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
                const resposta = await fetch(url, {
                    method: "GET",
                    credentials: "include",
                    headers: {
                        "Accept": "*/*",
                        "X-Requested-With": "XMLHttpRequest"
                    }
                });

                const texto = await resposta.text();

                return {
                    status: resposta.status,
                    texto: texto
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

    texto = resultado["texto"]

    if status != 200:
        raise RuntimeError(
            f"Nagumo retornou HTTP {status} "
            f"ao selecionar a loja {loja_codigo}.\n"
            f"Resposta: {texto[:1000]}"
        )

    try:
        dados = json.loads(texto)

    except json.JSONDecodeError as erro:
        raise RuntimeError(
            "Nagumo retornou uma resposta que não é JSON "
            f"ao selecionar a loja {loja_codigo}.\n"
            f"Resposta: {texto[:1000]}"
        ) from erro

    if not dados.get("success"):
        raise RuntimeError(
            f"Nagumo não confirmou a seleção da loja "
            f"{loja_codigo}: {dados}"
        )

    print(
        f"[OK] Loja {loja_codigo} selecionada no Nagumo."
    )


def _extrair_produtos_da_pagina(
    resposta_texto: str,
) -> list[dict]:
    """
    Extrai os produtos da resposta JSON do Search-UpdateGrid.

    O Nagumo retorna os produtos em:

        productsSearchResult
    """

    try:
        dados = json.loads(resposta_texto)

    except json.JSONDecodeError:
        return []

    produtos = dados.get(
        "productsSearchResult",
        [],
    )

    if not isinstance(produtos, list):
        return []

    return produtos


def _buscar_categoria(
    context: BrowserContext,
    cgid: str,
) -> list[dict]:
    """
    Pagina pelo Search-UpdateGrid até terminar os produtos.
    """

    todos: list[dict] = []

    inicio = 0

    while True:

        parametros = urlencode(
            {
                "cgid": cgid,
                "start": inicio,
                "sz": TAMANHO_PAGINA,
            }
        )

        url = (
            f"{BASE}/on/demandware.store/"
            "Sites-Nagumo-Site/"
            "pt_BR/"
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

        if resposta.status >= 400:
            raise RuntimeError(
                f"Nagumo retornou HTTP {resposta.status} "
                f"ao buscar a categoria '{cgid}'."
            )

        produtos_pagina = _extrair_produtos_da_pagina(
            resposta.text()
        )

        if not produtos_pagina:
            break

        todos.extend(produtos_pagina)

        print(
            f"[INFO] Categoria '{cgid}': "
            f"página iniciando em {inicio} "
            f"-> {len(produtos_pagina)} produtos."
        )

        if len(produtos_pagina) < TAMANHO_PAGINA:
            break

        inicio += TAMANHO_PAGINA

        time.sleep(
            INTERVALO_ENTRE_REQUISICOES_SEGUNDOS
        )

    return todos


def rodar(
    loja_nome: str,
    loja_codigo: str,
    categorias: list[str],
) -> None:
    """
    Executa o scraper para uma loja e suas categorias.
    """

    playwright = sync_playwright().start()

    browser = None

    db = None

    try:

        # -----------------------------------------------------
        # 1. Criar navegador
        # -----------------------------------------------------

        browser, context = _criar_navegador(
            playwright
        )

        page = context.new_page()

        # -----------------------------------------------------
        # 2. Abrir Nagumo
        # -----------------------------------------------------

        _abrir_nagumo(page)

        # -----------------------------------------------------
        # 3. Selecionar loja
        # -----------------------------------------------------

        _selecionar_loja(
            page=page,
            loja_codigo=loja_codigo,
            lat=LATITUDE,
            lng=LONGITUDE,
        )

        # -----------------------------------------------------
        # 4. Banco
        # -----------------------------------------------------

        db = SessionLocal()

        # -----------------------------------------------------
        # 5. Localizar/criar loja externa
        # -----------------------------------------------------

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

        # -----------------------------------------------------
        # 6. Buscar categorias
        # -----------------------------------------------------

        total_atualizados = 0

        for cgid in categorias:

            print(
                f"[INFO] Buscando categoria '{cgid}' "
                f"na loja {loja_codigo}..."
            )

            try:

                produtos_nagumo = _buscar_categoria(
                    context=context,
                    cgid=cgid,
                )

            except Exception as erro:

                print(
                    f"[ERRO] Falha buscando categoria "
                    f"'{cgid}': {erro}"
                )

                continue

            print(
                f"[INFO] Encontrados "
                f"{len(produtos_nagumo)} produtos "
                f"em '{cgid}'."
            )

            # -------------------------------------------------
            # 7. Processar produtos
            # -------------------------------------------------

            for produto_nagumo in produtos_nagumo:

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
                    continue

                try:

                    preco = Decimal(
                        str(preco_raw)
                    )

                except Exception:

                    print(
                        f"[AVISO] Preço inválido "
                        f"para '{nome}': "
                        f"{preco_raw}"
                    )

                    continue

                # -------------------------------------------------
                # 8. Procurar produto da loja
                # -------------------------------------------------

                produto = (
                    db.query(Produto)
                    .filter_by(
                        loja_externa_id=loja.id,
                        nome_produto=nome,
                    )
                    .one_or_none()
                )

                # -------------------------------------------------
                # 9. Criar produto
                # -------------------------------------------------

                if produto is None:

                    produto = Produto(
                        nome_produto=nome,
                        preco=preco,
                        quantidade=0,
                        origem="EXTERNO",
                        loja_externa_id=loja.id,
                    )

                    db.add(produto)

                    db.flush()

                    db.add(
                        HistoricoPreco(
                            produto_id=produto.id,
                            preco=preco,
                        )
                    )

                # -------------------------------------------------
                # 10. Atualizar preço
                # -------------------------------------------------

                elif produto.preco != preco:

                    produto.preco = preco

                    db.add(
                        HistoricoPreco(
                            produto_id=produto.id,
                            preco=preco,
                        )
                    )

                total_atualizados += 1

            time.sleep(
                INTERVALO_ENTRE_REQUISICOES_SEGUNDOS
            )

        # -----------------------------------------------------
        # 11. Commit
        # -----------------------------------------------------

        db.commit()

        print(
            f"[OK] {total_atualizados} produtos "
            f"atualizados de {loja_nome} "
            f"(loja {loja_codigo})."
        )

    except Exception:

        if db is not None:
            db.rollback()

        raise

    finally:

        if db is not None:
            db.close()

        if browser is not None:
            browser.close()

        playwright.stop()


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description=__doc__
    )

    parser.add_argument(
        "--loja",
        required=True,
        help=(
            "Nome para salvar a loja externa "
            "(ex: 'Nagumo Poa')"
        ),
    )

    parser.add_argument(
        "--loja-codigo",
        required=True,
        help=(
            "Código numérico da loja no Nagumo "
            "(ex: 22 ou 45)"
        ),
    )

    parser.add_argument(
        "--categorias",
        required=True,
        help=(
            "CGIDs separados por vírgula "
            "(ex: 'hortifruti,acougue,bebidas')"
        ),
    )

    args = parser.parse_args()

    categorias = [
        categoria.strip()
        for categoria in args.categorias.split(",")
        if categoria.strip()
    ]

    rodar(
        loja_nome=args.loja,
        loja_codigo=args.loja_codigo,
        categorias=categorias,
    )
