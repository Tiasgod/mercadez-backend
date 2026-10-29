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

# Intervalo reduzido para acelerar a coleta.
# Mantém uma pequena pausa entre as requisições.
INTERVALO_ENTRE_REQUISICOES_SEGUNDOS = 0.7

# Pausa entre categorias.
INTERVALO_ENTRE_CATEGORIAS_SEGUNDOS = 0.7

# Número de tentativas para selecionar uma loja.
MAX_TENTATIVAS_SELECAO_LOJA = 3

# Tempo de espera entre tentativas de seleção.
INTERVALO_RETRY_LOJA_SEGUNDOS = 3.0

TAMANHO_PAGINA = 40

LATITUDE = "-23.5325875"
LONGITUDE = "-46.335124"


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

        return (
            False,
            f"HTTP {status}. Resposta: {texto[:1000]}"
        )

    try:

        dados = json.loads(texto)

    except json.JSONDecodeError:

        return (
            False,
            "Nagumo retornou uma resposta que não é JSON. "
            f"Resposta: {texto[:1000]}"
        )

    if not dados.get("success"):

        return (
            False,
            f"Nagumo não confirmou a seleção: {dados}"
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
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 "
                        "(KHTML, like Gecko) "
                        "Chrome/152.0.0.0 Safari/537.36"
                    ),
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

def _extrair_produtos_da_pagina(
    resposta_texto: str,
) -> list[dict]:

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


# ============================================================
# BUSCAR UMA CATEGORIA COMPLETA
# ============================================================

def _buscar_categoria(
    context: BrowserContext,
    cgid: str,
) -> list[dict]:

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

        todos.extend(
            produtos_pagina
        )

        print(
            f"[INFO] Categoria '{cgid}': "
            f"posição {inicio} -> "
            f"{len(produtos_pagina)} produtos."
        )

        if len(produtos_pagina) < TAMANHO_PAGINA:
            break

        inicio += TAMANHO_PAGINA

        time.sleep(
            INTERVALO_ENTRE_REQUISICOES_SEGUNDOS
        )

    return todos


# ============================================================
# CARREGAR PRODUTOS DA LOJA EM MEMÓRIA
# ============================================================

def _carregar_produtos_da_loja(
    db,
    loja_id: int,
) -> dict[str, Produto]:

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

    mapa: dict[str, Produto] = {}

    for produto in produtos:

        nome = (
            produto.nome_produto or ""
        ).strip()

        if not nome:
            continue

        mapa[nome] = produto

    print(
        f"[OK] {len(mapa)} produtos existentes "
        "carregados em memória."
    )

    return mapa


# ============================================================
# SALVAR / ATUALIZAR PRODUTO
# ============================================================

def _salvar_produto(
    db,
    loja: LojaExterna,
    produto_nagumo: dict,
    produtos_existentes: dict[str, Produto],
    historicos_criados: set[tuple[int, Decimal]],
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

    # ========================================================
    # PRODUTO NOVO
    # ========================================================

    produto = produtos_existentes.get(nome)

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

        produtos_existentes[nome] = produto

        historicos_criados.add(
            (produto.id, preco)
        )

        return "novo"

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

    if chave_historico not in historicos_criados:

        db.add(
            HistoricoPreco(
                produto_id=produto.id,
                preco=preco,
            )
        )

        historicos_criados.add(
            chave_historico
        )

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

    historicos_criados: set[
        tuple[int, Decimal]
    ] = set()

    total_processados = 0
    total_novos = 0
    total_precos_alterados = 0
    total_sem_alteracao = 0
    total_ignorados = 0
    total_categorias = 0

    # --------------------------------------------------------
    # Percorrer categorias
    # --------------------------------------------------------

    for numero_categoria, cgid in enumerate(
        categorias,
        start=1,
    ):

        print()
        print(
            f"[INFO] Categoria "
            f"{numero_categoria}/{len(categorias)}: "
            f"'{cgid}'"
        )

        try:

            produtos_nagumo = _buscar_categoria(
                context=context,
                cgid=cgid,
            )

        except Exception as erro:

            print(
                f"[ERRO] Falha na categoria "
                f"'{cgid}': {erro}"
            )

            db.rollback()

            # ------------------------------------------------
            # Importante:
            # o mapa em memória pode conter objetos que foram
            # descartados pelo rollback. Recarregamos para
            # manter o estado consistente.
            # ------------------------------------------------

            produtos_existentes = (
                _carregar_produtos_da_loja(
                    db=db,
                    loja_id=loja.id,
                )
            )

            continue

        total_categorias += 1

        print(
            f"[INFO] Encontrados "
            f"{len(produtos_nagumo)} produtos "
            f"em '{cgid}'."
        )

        novos_categoria = 0
        alterados_categoria = 0
        iguais_categoria = 0
        ignorados_categoria = 0

        # ----------------------------------------------------
        # Salvar produtos
        # ----------------------------------------------------

        for produto_nagumo in produtos_nagumo:

            resultado = _salvar_produto(
                db=db,
                loja=loja,
                produto_nagumo=produto_nagumo,
                produtos_existentes=produtos_existentes,
                historicos_criados=historicos_criados,
            )

            total_processados += 1

            if resultado == "novo":

                total_novos += 1
                novos_categoria += 1

            elif resultado == "preco_alterado":

                total_precos_alterados += 1
                alterados_categoria += 1

            elif resultado == "sem_alteracao":

                total_sem_alteracao += 1
                iguais_categoria += 1

            else:

                total_ignorados += 1
                ignorados_categoria += 1

        # ----------------------------------------------------
        # Commit por categoria
        # ----------------------------------------------------

        try:

            db.commit()

        except Exception as erro:

            db.rollback()

            print(
                f"[ERRO] Falha ao salvar categoria "
                f"'{cgid}': {erro}"
            )

            produtos_existentes = (
                _carregar_produtos_da_loja(
                    db=db,
                    loja_id=loja.id,
                )
            )

            continue

        print(
            f"[OK] Categoria '{cgid}' salva."
        )

        print(
            f"     Novos: {novos_categoria}"
        )

        print(
            f"     Preços alterados: "
            f"{alterados_categoria}"
        )

        print(
            f"     Sem alteração: "
            f"{iguais_categoria}"
        )

        print(
            f"     Ignorados: "
            f"{ignorados_categoria}"
        )

        # Pequena pausa entre categorias.
        time.sleep(
            INTERVALO_ENTRE_CATEGORIAS_SEGUNDOS
        )

    # --------------------------------------------------------
    # Resultado da loja
    # --------------------------------------------------------

    print()
    print(
        f"[OK] Loja {loja_codigo} finalizada."
    )

    print(
        f"[INFO] Categorias processadas: "
        f"{total_categorias}/{len(categorias)}"
    )

    print(
        f"[INFO] Produtos analisados: "
        f"{total_processados}"
    )

    print(
        f"[INFO] Produtos novos: "
        f"{total_novos}"
    )

    print(
        f"[INFO] Preços alterados: "
        f"{total_precos_alterados}"
    )

    print(
        f"[INFO] Preços sem alteração: "
        f"{total_sem_alteracao}"
    )

    print(
        f"[INFO] Produtos ignorados: "
        f"{total_ignorados}"
    )

    return (
        total_processados,
        page,
        context,
        browser,
    )


# ============================================================
# EXECUÇÃO PRINCIPAL
# ============================================================

def rodar(
    lojas: list[dict],
    categorias: list[str] | None = None,
    todos: bool = False,
) -> None:

    playwright = sync_playwright().start()

    browser = None
    context = None
    db = None

    try:

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

        db = SessionLocal()

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

            except Exception as erro:

                lojas_com_erro += 1

                print()
                print(
                    "=" * 70
                )
                print(
                    f"[ERRO] Não foi possível processar "
                    f"a loja {loja['nome']} "
                    f"(código {loja['codigo']})."
                )
                print(
                    f"[ERRO] {erro}"
                )
                print(
                    "[INFO] Continuando para a próxima loja..."
                )
                print(
                    "=" * 70
                )

                # ------------------------------------------------
                # Tenta limpar a sessão para a próxima loja.
                # ------------------------------------------------

                try:

                    if context is not None:
                        context.close()

                except Exception:
                    pass

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
                            "pt-BR,pt;q=0.9,"
                            "en-US;q=0.8,en;q=0.7"
                        ),
                    },
                )

                page = context.new_page()

                try:

                    _abrir_nagumo(page)

                except Exception as erro:

                    print(
                        "[AVISO] Não foi possível "
                        "reabrir o Nagumo: "
                        f"{erro}"
                    )

                continue

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
            "as três lojas configuradas."
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
        {
            "nome": "Nagumo Poa",
            "codigo": "22",
        },
        {
            "nome": "Nagumo Poa_Kemel",
            "codigo": "45",
        },
        {
            "nome": "Nagumo Itaqua",
            "codigo": "30",
        },
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
    main()

