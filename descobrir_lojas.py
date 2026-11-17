from playwright.sync_api import sync_playwright
import json


URL = (
    "https://www.nagumo.com.br/"
    "on/demandware.store/"
    "Sites-Nagumo-Site/"
    "pt_BR/"
    "Stores-AvailableStores"
)


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)

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

    dados = json.loads(resposta["texto"])

    print("\\nLOJAS DE ITAQUAQUECETUBA:\\n")

    if isinstance(dados, list):
        lojas = dados
    else:
        lojas = (
            dados.get("stores")
            or dados.get("storesResult")
            or dados.get("data")
            or []
        )

    for loja in lojas:
        texto = json.dumps(
            loja,
            ensure_ascii=False,
        ).lower()

        if "itaqua" in texto:
            print(
                json.dumps(
                    loja,
                    ensure_ascii=False,
                    indent=2,
                )
            )

    browser.close()