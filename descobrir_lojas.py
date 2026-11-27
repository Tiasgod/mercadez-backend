from playwright.sync_api import sync_playwright
from urllib.parse import urljoin, urlparse, parse_qs
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter

import json
import unicodedata
import re


BASE = "https://www.nagumo.com.br"

URL = (
    f"{BASE}/"
    "on/demandware.store/"
    "Sites-Nagumo-Site/"
    "pt_BR/"
    "Stores-AvailableStores"
)


CIDADES = [
    "suzano",
    "mogi das cruzes",
    "mogi",
    "poa",
    "itaquaquecetuba",
    "itaqua",
    "ferraz de vasconcelos",
    "ferraz",
    "aruja",
    "guarulhos",
    "guararema",
    "santa isabel",
    "biritiba mirim",
    "salesopolis",
]


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
# FUNÇÕES AUXILIARES
# ============================================================

def normalizar(texto):

    return "".join(
        caractere
        for caractere in unicodedata.normalize(
            "NFD", str(texto).lower()
        )
        if unicodedata.category(caractere) != "Mn"
    )


def agora():

    return datetime.now(timezone.utc).isoformat()


def salvar_json(nome, dados):

    destino = Path(nome)

    temporario = destino.with_suffix(
        destino.suffix + ".tmp"
    )

    temporario.write_text(
        json.dumps(
            dados,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    temporario.replace(destino)

    print(f"[OK] Arquivo criado: {destino}")


def verificar_http(status, etapa):

    print(f"[HTTP {status}] {etapa}")

    if status in (401, 403, 429):

        raise RuntimeError(
            f"Acesso recusado em {etapa}. "
            "Mapeamento interrompido."
        )

    if status != 200:

        raise RuntimeError(
            f"Erro HTTP {status} em {etapa}."
        )


# ============================================================
# DESCOBRIR LOJAS
# ============================================================

def descobrir_lojas(page):

    resposta = page.evaluate(
        """
        async (url) => {

            const response = await fetch(url, {
                method: "GET",
                credentials: "include",
                headers: {
                    "Accept": "*/*",
                    "X-Requested-With": "XMLHttpRequest"
                }
            });

            return {
                status: response.status,
                texto: await response.text()
            };
        }
        """,
        URL,
    )

    verificar_http(
        resposta["status"],
        "Consulta de lojas"
    )

    dados = json.loads(resposta["texto"])

    if isinstance(dados, list):

        lojas = dados

    elif isinstance(dados, dict):

        lojas = (
            dados.get("stores")
            or dados.get("storesResult")
            or dados.get("data")
            or []
        )

    else:

        raise RuntimeError(
            "Formato inesperado na resposta de lojas."
        )

    if not isinstance(lojas, list):

        raise RuntimeError(
            "A resposta não contém uma lista de lojas."
        )

    encontradas = []

    print("\n" + "=" * 65)
    print("LOJAS NAGUMO - ALTO TIETE E REGIAO")
    print("=" * 65)

    for loja in lojas:

        if not isinstance(loja, dict):
            continue

        texto = normalizar(
            json.dumps(
                loja,
                ensure_ascii=False,
            )
        )

        pertence_regiao = any(
            re.search(
                rf"(?<!\w){re.escape(cidade)}(?!\w)",
                texto,
            )
            for cidade in CIDADES
        )

        if pertence_regiao:

            encontradas.append(loja)

            print(
                json.dumps(
                    loja,
                    ensure_ascii=False,
                    indent=2,
                )
            )

            print("-" * 65)

    print(f"[INFO] Lojas consultadas: {len(lojas)}")
    print(f"[INFO] Lojas da região: {len(encontradas)}")

    return encontradas, len(lojas)


# ============================================================
# EXTRAIR LINKS PÚBLICOS DO CATÁLOGO
# ============================================================

def extrair_links(page):

    links = page.evaluate(
        """
        () => {

            return Array.from(
                document.querySelectorAll("a[href]")
            ).map(link => ({

                texto: (
                    link.innerText ||
                    link.textContent ||
                    link.getAttribute("aria-label") ||
                    link.getAttribute("title") ||
                    ""
                ).trim(),

                href: link.href,

                categoria_id:
                    link.getAttribute("data-cgid") ||
                    link.getAttribute("data-category-id") ||
                    null

            }));

        }
        """
    )

    print(
        f"[INFO] Total de links encontrados: "
        f"{len(links)}"
    )

    return links


# ============================================================
# IDENTIFICAR A HIERARQUIA
# ============================================================

def identificar_categoria(link):

    href = link.get("href")

    if not href:

        return None

    url = urljoin(BASE, href)
    parsed = urlparse(url)

    # Somente páginas do domínio oficial.

    if parsed.hostname not in (
        "www.nagumo.com.br",
        "nagumo.com.br",
    ):

        return None

    partes = [
        parte
        for parte in parsed.path.split("/")
        if parte
    ]

    # Estrutura pública de categorias.

    if len(partes) < 3:

        return None

    if partes[:2] != [
        "categoria",
        "departamentos",
    ]:

        return None

    hierarquia = partes[2:]

    departamento = hierarquia[0]

    if departamento not in DEPARTAMENTOS:

        return None

    parametros = parse_qs(parsed.query)

    codigo = (
        link.get("categoria_id")
        or parametros.get("cgid", [None])[0]
    )

    nome = link.get("texto", "").strip()

    if not nome:

        nome = (
            hierarquia[-1]
            .replace("-", " ")
            .title()
        )

    return {
        "nome": nome,
        "departamento": departamento,
        "slug": hierarquia[-1],
        "codigo_confirmado": codigo,
        "nivel": len(hierarquia),
        "hierarquia": hierarquia,
        "url": (
            f"{BASE}/"
            + "/".join(partes)
            + "/"
        ),
    }


# ============================================================
# CONSTRUIR ÁRVORE DE DEPARTAMENTOS
# ============================================================

def construir_arvore(categorias):

    departamentos = {}

    for categoria in categorias:

        hierarquia = categoria["hierarquia"]

        nivel_atual = departamentos

        for indice, slug in enumerate(hierarquia):

            if slug not in nivel_atual:

                nivel_atual[slug] = {
                    "nome": slug.replace("-", " ").title(),
                    "slug": slug,
                    "codigo_confirmado": None,
                    "url": None,
                    "observado_no_menu": False,
                    "subcategorias": {},
                }

            no = nivel_atual[slug]

            if indice == len(hierarquia) - 1:

                no["nome"] = categoria["nome"]

                no["url"] = categoria["url"]

                no["codigo_confirmado"] = (
                    categoria["codigo_confirmado"]
                )

                no["observado_no_menu"] = True

            nivel_atual = no["subcategorias"]

    def converter(nos):

        resultado = []

        for no in nos.values():

            resultado.append({
                "nome": no["nome"],
                "slug": no["slug"],
                "codigo_confirmado": no["codigo_confirmado"],
                "url": no["url"],
                "observado_no_menu": no["observado_no_menu"],
                "subcategorias": converter(
                    no["subcategorias"]
                ),
            })

        return resultado

    return converter(departamentos)


# ============================================================
# DESCOBRIR CATÁLOGO
# ============================================================

def descobrir_catalogo(page):

    print("\n" + "=" * 65)
    print("DESCOBRINDO DEPARTAMENTOS E SUBCATEGORIAS")
    print("=" * 65)

    links = extrair_links(page)

    categorias = {}

    for link in links:

        categoria = identificar_categoria(link)

        if categoria is None:

            continue

        chave = tuple(categoria["hierarquia"])

        anterior = categorias.get(chave)

        if (
            anterior
            and anterior["codigo_confirmado"]
            and categoria["codigo_confirmado"]
            and anterior["codigo_confirmado"]
            != categoria["codigo_confirmado"]
        ):

            raise RuntimeError(
                f"Identificadores conflitantes: {chave}"
            )

        if anterior:

            if not anterior["codigo_confirmado"]:

                anterior["codigo_confirmado"] = (
                    categoria["codigo_confirmado"]
                )

            continue

        categorias[chave] = categoria

    resultado = sorted(
        categorias.values(),
        key=lambda item: item["hierarquia"],
    )

    for categoria in resultado:

        recuo = "    " * (
            categoria["nivel"] - 1
        )

        codigo = (
            categoria["codigo_confirmado"]
            or "não informado"
        )

        print(
            f"{recuo}- {categoria['nome']} "
            f"| Código: {codigo}"
        )

    arvore = construir_arvore(resultado)

    contagem_niveis = Counter(
        categoria["nivel"]
        for categoria in resultado
    )

    departamentos_encontrados = sorted({
        categoria["departamento"]
        for categoria in resultado
    })

    departamentos_ausentes = sorted(
        set(DEPARTAMENTOS)
        - set(departamentos_encontrados)
    )

    estatisticas = {
        "links_analisados": len(links),

        "departamentos_encontrados":
            len(departamentos_encontrados),

        "categorias_encontradas":
            len(resultado),

        "subcategorias_encontradas":
            sum(
                c["nivel"] > 1
                for c in resultado
            ),

        "codigos_confirmados":
            sum(
                bool(c["codigo_confirmado"])
                for c in resultado
            ),

        "categorias_por_nivel":
            dict(contagem_niveis),

        "departamentos_ausentes":
            departamentos_ausentes,
    }

    if not resultado:

        print(
            "[AVISO] Nenhuma categoria encontrada. "
            "O menu pode utilizar carregamento dinâmico "
            "ou outra estrutura HTML."
        )

    return {
        "departamentos": arvore,
        "categorias": resultado,
        "estatisticas": estatisticas,
        "cobertura_completa_confirmada": False,
    }


# ============================================================
# EXECUÇÃO PRINCIPAL
# ============================================================

def main():

    inicio = agora()

    relatorio = {
        "inicio": inicio,
        "status": "iniciado",
    }

    try:

        with sync_playwright() as playwright:

            browser = playwright.chromium.launch(
                headless=True,
            )

            context = browser.new_context(
                locale="pt-BR",
                timezone_id="America/Sao_Paulo",
            )

            try:

                page = context.new_page()

                print("=" * 65)
                print("MERCADEZ - MAPEAMENTO DO NAGUMO")
                print("=" * 65)

                resposta = page.goto(
                    BASE,
                    wait_until="domcontentloaded",
                    timeout=60000,
                )

                if resposta is None:

                    raise RuntimeError(
                        "Nenhuma resposta da página inicial."
                    )

                verificar_http(
                    resposta.status,
                    "Página inicial",
                )

                # ETAPA 1: LOJAS

                lojas, total_lojas = descobrir_lojas(
                    page
                )

                salvar_json(
                    "lojas_nagumo_regiao.json",
                    lojas,
                )

                relatorio["total_lojas_consultadas"] = (
                    total_lojas
                )

                relatorio["lojas_regiao"] = len(lojas)

                # ETAPA 2: CATÁLOGO PÚBLICO

                catalogo = descobrir_catalogo(page)

                catalogo["data_mapeamento"] = agora()

                catalogo["fonte"] = BASE

                catalogo["escopo"] = (
                    "Menu público da sessão atual"
                )

                catalogo["lojas_regiao"] = lojas

                catalogo["catalogo_por_filial_verificado"] = (
                    False
                )

                relatorio.update(
                    catalogo["estatisticas"]
                )

                if not catalogo["categorias"]:

                    raise RuntimeError(
                        "Não foi possível identificar "
                        "a estrutura pública do catálogo."
                    )

                salvar_json(
                    "catalogo_nagumo.json",
                    catalogo,
                )

                relatorio["status"] = (
                    "mapeamento_parcial"
                )

                print("\n" + "=" * 65)
                print("RESULTADO FINAL")
                print("=" * 65)

                for chave, valor in (
                    catalogo["estatisticas"].items()
                ):

                    print(f"{chave}: {valor}")

            finally:

                context.close()
                browser.close()

        return 0

    except Exception as erro:

        relatorio["status"] = "falha"

        relatorio["erro"] = str(erro)

        print(f"[ERRO] {erro}")

        return 1

    finally:

        relatorio["fim"] = agora()

        salvar_json(
            "relatorio_descoberta.json",
            relatorio,
        )


if __name__ == "__main__":

    raise SystemExit(main())
