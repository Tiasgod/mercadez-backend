from playwright.sync_api import sync_playwright
import json
import unicodedata


URL = (
    "https://www.nagumo.com.br/"
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


def normalizar(texto):
    return "".join(
        caractere
        for caractere in unicodedata.normalize(
            "NFD", texto.lower()
        )
        if unicodedata.category(caractere) != "Mn"
    )


with sync_playwright() as playwright:

    browser = playwright.chromium.launch(
        headless=True
    )

    context = browser.new_context(
        locale="pt-BR",
        timezone_id="America/Sao_Paulo",
    )

    page = context.new_page()

    page.goto(
        "https://www.nagumo.com.br",
        wait_until="domcontentloaded",
        timeout=60000,
    )

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

    print("HTTP:", resposta["status"])

    if resposta["status"] != 200:
        browser.close()
        raise RuntimeError(
            "Erro ao consultar lojas do Nagumo."
        )

    dados = json.loads(resposta["texto"])

    if isinstance(dados, list):
        lojas = dados
    else:
        lojas = (
            dados.get("stores")
            or dados.get("storesResult")
            or dados.get("data")
            or []
        )

    lojas_encontradas = []

    print("\n" + "=" * 65)
    print("LOJAS NAGUMO - ALTO TIETE E REGIAO")
    print("=" * 65)

    for loja in lojas:

        texto = normalizar(
            json.dumps(
                loja,
                ensure_ascii=False,
            )
        )

        if any(cidade in texto for cidade in CIDADES):

            lojas_encontradas.append(loja)

            print(
                json.dumps(
                    loja,
                    ensure_ascii=False,
                    indent=2,
                )
            )

            print("-" * 65)

    print("\n" + "=" * 65)
    print("RESULTADO FINAL")
    print("=" * 65)

    print(f"Total de lojas consultadas: {len(lojas)}")
    print(f"Lojas da regiao: {len(lojas_encontradas)}")

    with open(
        "lojas_nagumo_regiao.json",
        "w",
        encoding="utf-8",
    ) as arquivo:

        json.dump(
            lojas_encontradas,
            arquivo,
            ensure_ascii=False,
            indent=2,
        )

    print("\n[OK] Arquivo lojas_nagumo_regiao.json criado.")

    browser.close()