from __future__ import annotations

import argparse
from pathlib import Path
import hashlib
from datetime import datetime, timezone
from collections import Counter
import json
import re
import time
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from urllib.parse import urlencode, urljoin, urlparse



BASE = "https://www.nagumo.com.br"

# Intervalo moderado entre páginas do catálogo.
INTERVALO_ENTRE_REQUISICOES_SEGUNDOS = 3.0

# Pausa entre categorias.
INTERVALO_ENTRE_CATEGORIAS_SEGUNDOS = 3.0

TAMANHO_PAGINA = 40

LATITUDE = "-23.5325875"
LONGITUDE = "-46.335124"



def carregar_catalogo(arquivo):
    dados = json.loads(Path(arquivo).read_text(encoding="utf-8"))
    mapa = {}
    for item in dados["categorias"]:
        partes = item["hierarquia"]
        if not partes or not all(re.fullmatch(r"[a-z0-9-]+", p) for p in partes):
            raise ValueError("Hierarquia invalida")
        chave = "/".join(partes)
        if chave in mapa:
            raise ValueError(f"Categoria duplicada: {chave}")
        mapa[chave] = item
    return mapa


def planejar_catalogo(mapa, departamentos=None):
    filtro = set(departamentos or [])
    selecionados = {k:v for k,v in mapa.items() if not filtro or k.split("/")[0] in filtro}
    if filtro - {k.split("/")[0] for k in selecionados}:
        raise ValueError("Departamento solicitado ausente do catalogo")
    folhas = [k for k in sorted(selecionados) if not any(x.startswith(k+"/") for x in selecionados)]
    return {"escopo": "planejamento, sem acesso ao site ou banco", "cobertura_confirmada": False,
            "categorias_observadas": len(selecionados), "folhas_candidatas": folhas,
            "identificadores_validados": sum(v.get("codigo_validado_em_api") is True and bool(v.get("codigo_confirmado")) for v in selecionados.values()),
            "departamentos_ausentes": sorted(set(DEPARTAMENTOS_ESPERADOS)-{k.split("/")[0] for k in mapa})}


DEPARTAMENTOS_ESPERADOS = "acougue basicos-e-matinais bazar bebidas frios-e-laticinios higiene-e-perfumaria hortifruti limpeza padaria peixaria pet-shop mercearia-doce mercearia-salgada".split()


def carregar_consultas_autorizadas(arquivo, mapa, lojas, departamentos):
    dados = json.loads(Path(arquivo).read_text(encoding="utf-8"))
    if not isinstance(dados.get("referencia_autorizacao"), str) or not dados["referencia_autorizacao"].strip():
        raise ValueError("Informe a referencia da autorizacao de coleta e dos limites de pesquisa")
    resultado = {}
    for loja in lojas:
        codigo = loja["codigo"]
        consultas = dados.get("filiais", {}).get(codigo, [])
        selecionadas = {}
        ids = set()
        for item in consultas:
            caminho = item["hierarquia"]
            if departamentos and caminho.split("/")[0] not in departamentos:
                continue
            if caminho not in mapa or item.get("validado") is not True or not str(item.get("evidencia") or "").strip():
                raise ValueError(f"Consulta nao validada: {codigo}/{caminho}")
            cgid = item.get("cgid")
            if not isinstance(cgid, str) or not cgid.strip():
                raise ValueError("Identificador interno ausente")
            if cgid in ids or caminho in selecionadas:
                raise ValueError("Consulta duplicada")
            ids.add(cgid)
            selecionadas[caminho] = cgid
        if not selecionadas:
            raise ValueError(f"Nenhuma consulta validada para filial {codigo}")
        resultado[codigo] = selecionadas
    return resultado


class AcessoRecusado(RuntimeError):
    """Uma recusa encerra as consultas nesta execução."""
    def __init__(self, status: int, etapa: str):
        self.status = status
        self.etapa = etapa
        super().__init__(f"HTTP {status} em {etapa}. Coleta suspensa.")


class FalhaHTTP(RuntimeError):
    def __init__(self, status, etapa):
        self.status = status
        super().__init__(f"HTTP {status} em {etapa}")


def verificar_acesso(status: int, etapa: str, headers=None) -> None:
    # Nunca imprime cookies, tokens, corpo ou todos os headers.
    headers = headers or {}
    seguros = {k: str(headers[k])[:160] for k in
               ("content-type", "retry-after", "x-request-id", "cf-ray") if headers.get(k) is not None}
    print(json.dumps({"evento": "http", "utc": datetime.now(timezone.utc).isoformat(),
                      "etapa": etapa, "status": status, "headers": seguros}, ensure_ascii=False))
    if status in (401, 403, 429):
        raise AcessoRecusado(status, etapa)
    if status != 200:
        raise FalhaHTTP(status, etapa)


def ler_checkpoint(db, codigo, categoria):
    row = db.execute(text("""SELECT proxima_posicao, assinaturas, concluida
        FROM nagumo_coleta_checkpoint WHERE loja_codigo=:codigo AND categoria=:categoria"""),
        {"codigo": codigo, "categoria": categoria}).first()
    return (row[0], set(json.loads(row[1]) if isinstance(row[1], str) else (row[1] or [])), bool(row[2])) if row else (0, set(), False)


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
                              "x-request-id": resposta.headers.get("x-request-id"),
                              "cf-ray": resposta.headers.get("cf-ray")}
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

    if not isinstance(dados, dict) or not dados.get("success"):

        return (
            False,
            "Nagumo não confirmou a seleção."
        )

    # Quando a resposta informa a filial explicitamente, confira o codigo.
    codigo_retornado = dados.get("storeId")
    if isinstance(codigo_retornado, (str, int)) and not isinstance(codigo_retornado, bool):
        informado = str(codigo_retornado).strip()
        if re.fullmatch(r"(?:M_)?[0-9]+", informado, re.I):
            if int(informado.split("_")[-1]) != int(loja_codigo):
                return False, "Codigo de filial retornado diverge do solicitado."
            print("[INFO] Codigo da filial confirmado pela resposta.")
    else:
        print("[INFO] Selecao aceita; resposta sem storeId escalar para verificacao independente.")
    return True, ""


# ============================================================
# SELECIONAR LOJA - SEM REPETICAO AUTOMATICA
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
    """Seleciona a loja uma vez; falhas interrompem a coleta."""
    print(f"[INFO] Selecionando loja {loja_codigo}...")
    sucesso, erro = _tentar_selecionar_loja(
        page=page, loja_codigo=loja_codigo, lat=lat, lng=lng,
    )
    if not sucesso:
        raise RuntimeError(f"Falha ao selecionar loja {loja_codigo}: {erro}")
    print(f"[OK] Loja {loja_codigo} selecionada no Nagumo.")
    return page, context, browser


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
    if len(set(valores)) > 1:
        raise RuntimeError("Metadados de total divergentes; categoria nao concluida.")
    return valores[0] if valores else None


def _validar_paginacao(produtos, inicio, assinaturas):
    """Valida antes de gravar; nao altera a assinatura dos checkpoints antigos."""
    if type(inicio) is not int or inicio < 0:
        raise RuntimeError("Checkpoint invalido.")
    if len(produtos) > TAMANHO_PAGINA:
        raise RuntimeError("Pagina maior que o tamanho solicitado.")
    assinatura = assinatura_pagina(produtos) if produtos else None
    if assinatura and assinatura in assinaturas:
        raise RuntimeError("Pagina repetida; categoria nao concluida.")
    proxima = inicio + len(produtos)
    total = getattr(produtos, "total", None)
    if total is not None:
        if proxima > total:
            raise RuntimeError("Total do catalogo inconsistente com a pagina recebida.")
        if not produtos and inicio < total:
            raise RuntimeError("Pagina vazia antes do total informado.")
        concluida = proxima == total
    else:
        # Sem total, a pagina curta e o criterio original do endpoint.
        concluida = len(produtos) < TAMANHO_PAGINA
    return proxima, assinatura, concluida


def _preco_valido(valor):
    # Numeric(10,2); nao publicar preco zero, negativo, NaN ou fora do campo.
    try:
        preco = Decimal(str(valor))
        if not preco.is_finite() or preco <= 0 or preco > Decimal("99999999.99"):
            return None
        preco = preco.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return preco if preco > 0 else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def _identidade_original(item):
    for campo in ("productID", "productId", "id", "ean", "upc"):
        valor = item.get(campo)
        if isinstance(valor, (str, int)) and not isinstance(valor, bool) and str(valor).strip():
            return str(valor).strip()
    return None


def _conflitos_pagina(produtos):
    """Nao confundir variantes homonimas ou precos divergentes na mesma pagina."""
    vistos = {}
    conflitos = set()
    for item in produtos:
        nome = item.get("productName")
        if not isinstance(nome, str) or not nome.strip():
            continue
        chave = chave_produto(nome)
        price = item.get("price")
        sales = price.get("sales") if isinstance(price, dict) else None
        preco = _preco_valido(sales.get("value")) if isinstance(sales, dict) else None
        ident = _identidade_original(item)
        anterior = vistos.get(chave)
        if anterior is not None:
            id_ant, preco_ant = anterior
            if (ident and id_ant and ident != id_ant) or (preco is not None and preco_ant is not None and preco != preco_ant):
                conflitos.add(chave)
            vistos[chave] = (id_ant or ident, preco_ant if preco_ant is not None else preco)
        else:
            vistos[chave] = (ident, preco)
    return conflitos


def _buscar_pagina(context: BrowserContext, cgid: str, inicio: int, loja_codigo: str | None = None) -> PaginaCatalogo:
    if inicio < 0:
        raise ValueError(f"Posição inválida: {inicio}")
    tamanho = TAMANHO_PAGINA
    print(f"[INFO] Consulta: categoria={cgid}, start={inicio}, sz={tamanho}")
    inicio_http = time.monotonic()
    parametros = urlencode({"cgid": cgid, "start": inicio, "sz": tamanho})
    url = (f"{BASE}/on/demandware.store/Sites-Nagumo-Site/pt_BR/Search-UpdateGrid?{parametros}")
    resposta = context.request.get(url, headers={"Accept": "*/*", "Referer": f"{BASE}/"}, timeout=60000)
    try:
        print(f"[INFO] Resposta recebida em {time.monotonic() - inicio_http:.2f}s")
        verificar_acesso(resposta.status, f"categoria {cgid}, posicao {inicio}", resposta.headers)
        bruto = resposta.text()
        produtos = _extrair_produtos_da_pagina(bruto)
        dados = json.loads(bruto)
        for objeto in (dados, dados.get("productSearch")):
            if not isinstance(objeto, dict):
                continue
            categoria_retornada = objeto.get("cgid") or objeto.get("categoryId")
            if isinstance(categoria_retornada, str) and categoria_retornada and categoria_retornada != cgid:
                raise RuntimeError("Categoria retornada diverge da solicitada.")
            codigo = objeto.get("storeId")
            if loja_codigo and isinstance(codigo, (str, int)) and not isinstance(codigo, bool):
                codigo = str(codigo).strip()
                if re.fullmatch(r"(?:M_)?[0-9]+", codigo, re.I) and int(codigo.split("_")[-1]) != int(loja_codigo):
                    raise RuntimeError("Filial retornada diverge da solicitada.")
        total = _total_informado(dados)
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

    nome_raw = produto_nagumo.get("productName")
    nome = nome_raw.strip() if isinstance(nome_raw, str) else ""
    price = produto_nagumo.get("price")
    sales = price.get("sales") if isinstance(price, dict) else None
    preco_raw = sales.get("value") if isinstance(sales, dict) else None

    if not nome:
        return "ignorado"

    if preco_raw is None:
        return "ignorado"

    preco = _preco_valido(preco_raw)
    if preco is None:
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
    principal = produto.imagem_url
    antigas = produto.imagens_urls if isinstance(produto.imagens_urls, list) else []
    mescladas = list(dict.fromkeys(v for v in [principal, *antigas, *imagens_urls]
                                  if isinstance(v, str) and v.strip()))
    if mescladas:
        if produto.imagens_urls != mescladas:
            produto.imagens_urls = mescladas
        if not isinstance(principal, str) or not principal.strip():
            produto.imagem_url = mescladas[0]

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
    contagem: Counter,
    progresso: dict,
    consultas: dict | None = None,
) -> None:

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
    unidades = consultas if consultas is not None else {c:c for c in categorias}
    chaves = {}
    assinaturas_outras = {}
    for caminho, cgid in unidades.items():
        chave = ("v5:" + hashlib.sha256(json.dumps([caminho,cgid], ensure_ascii=False).encode()).hexdigest()) if consultas is not None else cgid
        chaves[caminho] = chave
        progresso.update(categoria=caminho, posicao=None)
        inicio, assinaturas, concluida = ler_checkpoint(db, loja_codigo, chave)
        db.commit()
        progresso["posicao"] = inicio
        if concluida:
            print(f"[INFO] Categoria {cgid} ja concluida neste ciclo.")
            continue
        while True:
            progresso["posicao"] = inicio
            produtos = _buscar_pagina(context, cgid, inicio, loja_codigo)
            if consultas is not None and inicio == 0 and not produtos:
                raise RuntimeError(f"Subcategoria {cgid} vazia: identificador/cobertura inconclusivos; sem checkpoint novo.")
            proxima, assinatura, concluida = _validar_paginacao(produtos, inicio, assinaturas)
            if assinatura and consultas is not None:
                outra = assinaturas_outras.get(assinatura)
                if outra is not None and outra != caminho:
                    raise RuntimeError(f"Pagina identica em {outra} e {caminho}; verificar identificadores antes de prosseguir.")
                assinaturas_outras[assinatura] = caminho
            conflitos = _conflitos_pagina(produtos)
            lote = Counter()
            historicos_lote = set()
            for item in produtos:
                nome = item.get("productName")
                if isinstance(nome, str) and chave_produto(nome) in conflitos:
                    lote["ignorado_conflito"] += 1
                    continue
                resultado = _salvar_produto(db, loja, item, produtos_existentes, historicos_lote, caminho.split("/")[0])
                lote[resultado] += 1
            if assinatura:
                assinaturas.add(assinatura)
            print(f"[INFO] Paginacao validada: loja={loja_codigo}, categoria={cgid}, proxima={proxima}, concluida={concluida}")
            # Dados e checkpoint na mesma transacao: ambos gravados ou nenhum.
            salvar_checkpoint(db, loja_codigo, chave, proxima, assinaturas, concluida)
            db.commit()
            contagem.update(lote)
            progresso["posicao"] = proxima
            print(f"[OK] Lote gravado: loja {loja_codigo}, {cgid}, posicao {inicio}, {dict(lote)}")
            if concluida:
                break
            inicio = proxima
            time.sleep(INTERVALO_ENTRE_REQUISICOES_SEGUNDOS)
        time.sleep(INTERVALO_ENTRE_CATEGORIAS_SEGUNDOS)
    # Somente quando todas as categorias solicitadas terminam: novo ciclo na proxima execucao.
    for cgid in chaves.values():
        db.execute(text("DELETE FROM nagumo_coleta_checkpoint WHERE loja_codigo=:codigo AND categoria=:categoria"),
                   {"codigo": loja_codigo, "categoria": cgid})
    db.commit()
    print(f"[OK] Loja {loja_codigo} finalizada. Lotes desta execucao: {dict(contagem)}")
    return None


# ============================================================
# EXECUÇÃO PRINCIPAL
# ============================================================

def rodar(lojas: list[dict], categorias: list[str] | None = None,
          todos: bool = False, consultas_por_filial=None) -> int:
    global text, sync_playwright, SessionLocal, HistoricoPreco, LojaExterna, Produto
    from sqlalchemy import text
    from playwright.sync_api import sync_playwright
    from app.core.database import SessionLocal
    from app.models.historico_preco import HistoricoPreco
    from app.models.loja_externa import LojaExterna
    from app.models.produto import Produto
    inicio = time.monotonic()
    contagem = Counter()
    resultados, erros = [], []

    def registrar_erro(erro, loja=None, progresso=None):
        registro = {"loja": loja["nome"] if loja else None,
                    "codigo": loja["codigo"] if loja else None,
                    "categoria": (progresso or {}).get("categoria"),
                    "posicao": (progresso or {}).get("posicao"),
                    "tipo": type(erro).__name__,
                    "mensagem": str(erro)[:500] if not type(erro).__module__.startswith("sqlalchemy") else "Falha de banco; detalhes sensíveis omitidos.",
                    "status_http": getattr(erro, "status", None),
                    "horario": datetime.now(timezone.utc).isoformat()}
        erros.append(registro)
        print(json.dumps({"evento": "erro_coleta", **registro}, ensure_ascii=False), flush=True)

    try:
        with sync_playwright() as playwright:
            browser, context = _criar_navegador(playwright)
            try:
                page = context.new_page()
                _abrir_nagumo(page)
                categorias_processar = list(dict.fromkeys(categorias or [])) if consultas_por_filial is not None else (_descobrir_departamentos(page) if todos else list(dict.fromkeys(categorias or [])))
                if not categorias_processar and consultas_por_filial is None:
                    raise ValueError("Nenhuma categoria selecionada.")
                for loja in lojas:
                    print(f"[INFO] Loja em processamento: {loja['nome']} (codigo {loja['codigo']})", flush=True)
                    progresso = {"categoria": None, "posicao": None}
                    status = "falha"
                    db = None
                    parar = False
                    try:
                        db = SessionLocal()
                        db.expire_on_commit = False
                        _processar_loja(page, context, db, loja["nome"], loja["codigo"],
                                        categorias_processar, playwright, browser, contagem, progresso,
                                        consultas=(consultas_por_filial or {}).get(loja["codigo"]))
                        status = "consultas_concluidas" if consultas_por_filial is not None else "concluida"
                    except Exception as erro:
                        registrar_erro(erro, loja, progresso)
                        parar = isinstance(erro, AcessoRecusado) or consultas_por_filial is not None
                        if db is not None:
                            db.rollback()
                        print("[INFO] Lotes anteriores preservados.", flush=True)
                        if parar:
                            print("[ERRO] Falha na coleta; consultas encerradas.", flush=True)
                        else:
                            print("[INFO] Falha técnica; próxima loja.", flush=True)
                    finally:
                        resultados.append({**loja, "status": status})
                        if db is not None:
                            db.close()
                    if parar:
                        break
                    time.sleep(INTERVALO_ENTRE_CATEGORIAS_SEGUNDOS)
            finally:
                try:
                    context.close()
                finally:
                    browser.close()
    except Exception as erro:
        registrar_erro(erro)
    finally:
        processadas = {r["codigo"] for r in resultados}
        pendentes = [l for l in lojas if l["codigo"] not in processadas]
        concluidas = sum(r["status"] in ("concluida", "consultas_concluidas") for r in resultados)
        relatorio = {"escopo": "subcategorias do catalogo, cobertura integral nao comprovada" if consultas_por_filial is not None else "departamentos originais", "identificadores_e_filiais_independentemente_validados": False, "lojas_programadas": len(lojas), "lojas_processadas": len(resultados),
                     "lojas_concluidas": concluidas, "lojas_com_falhas": len(resultados)-concluidas,
                     "lojas_nao_processadas": len(pendentes), "pendentes": pendentes,
                     "produtos_analisados": sum(contagem.values()), "produtos": dict(contagem),
                     "resultados": resultados, "erros": erros,
                     "duracao_segundos": round(time.monotonic()-inicio, 2)}
        pasta = Path("diagnostico")
        pasta.mkdir(exist_ok=True)
        (pasta / "relatorio_scraper.json").write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
        print("\nMERCADEZ - RELATORIO FINAL", flush=True)
        print(json.dumps({"evento": "resultado_coleta", **relatorio}, ensure_ascii=False), flush=True)
    return 1 if erros or len(resultados) != len(lojas) else 0


# Subcategorias observadas no catalogo; slugs ainda nao validados como cgid.
ACOUGUE_CANDIDATOS = (
    "ave/ave-congelada", "ave/ave-refrigerada", "ave/iqf",
    "bovino/bovino-congelado", "bovino/bovino-manipulado", "bovino/bovino-vacuo",
    "caprino/caprino-e-cordeiro", "defumado-e-charqueado/carne-seca",
    "defumado-e-charqueado/suino-defumado", "suino/suino-congelado",
    "suino/suino-refrigerado",
)


def consultas_catalogo(mapa, lojas, departamentos):
    """Mapeia folhas observadas. Slugs sao candidatos, nao IDs comprovados."""
    plano = planejar_catalogo(mapa, departamentos)
    folhas = plano["folhas_candidatas"]
    if not folhas:
        raise ValueError("Nenhuma subcategoria mapeada.")
    if departamentos == ["acougue"]:
        esperadas = {"acougue/" + p for p in ACOUGUE_CANDIDATOS}
        if set(folhas) != esperadas:
            raise ValueError("Catalogo do acougue diverge das 11 folhas observadas.")
    consultas = {}
    usados = set()
    for caminho in folhas:
        item = mapa[caminho]
        confirmado = item.get("codigo_validado_em_api") is True
        cgid = item.get("codigo_confirmado") if confirmado else item.get("slug")
        if not isinstance(cgid, str) or not cgid.strip():
            raise ValueError(f"Identificador ausente: {caminho}")
        if cgid in usados:
            raise ValueError(f"Identificador ambiguo no catalogo: {cgid}")
        usados.add(cgid)
        consultas[caminho] = cgid
        print(f"[CATALOGO] {caminho} => {cgid} ({'validado' if confirmado else 'slug candidato'})", flush=True)
    print(f"[INFO] {len(consultas)} subcategorias selecionadas. Cobertura integral nao comprovada.")
    return {loja["codigo"]: dict(consultas) for loja in lojas}


def main() -> int:

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

    parser.add_argument("--planejar", action="store_true", help="Planejamento offline")
    parser.add_argument("--catalogo", default="catalogo_nagumo.json")
    parser.add_argument("--consultas-autorizadas", help="JSON de consultas validadas por filial")
    args = parser.parse_args()
    if args.planejar:
        plano = planejar_catalogo(carregar_catalogo(args.catalogo), args.categorias)
        Path("diagnostico").mkdir(exist_ok=True)
        Path("diagnostico/plano_catalogo.json").write_text(json.dumps(plano, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(plano, ensure_ascii=False, indent=2))
        return 0

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

    mapa = carregar_catalogo(args.catalogo)
    departamentos = DEPARTAMENTOS_ESPERADOS if args.todos else args.categorias
    if args.consultas_autorizadas:
        consultas = carregar_consultas_autorizadas(
            args.consultas_autorizadas, mapa, lojas, departamentos
        )
    else:
        consultas = consultas_catalogo(mapa, lojas, departamentos)
    print("[INFO] COLETA REAL: consulta HTTP e persistencia no PostgreSQL.", flush=True)
    print("[AVISO] Selecionar apenas filiais e categorias permitidas; slugs nao equivalem a IDs comprovados.", flush=True)
    return rodar(
        consultas_por_filial=consultas,
        lojas=lojas,
        categorias=args.categorias,
        todos=args.todos,
    )


if __name__ == "__main__":
    raise SystemExit(main())
