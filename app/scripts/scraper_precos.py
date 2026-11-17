"""
Scraper de precos via API publica de catalogo da VTEX.

Varias redes grandes do Brasil (Carrefour confirmado; outras a checar)
rodam na plataforma VTEX, que expoe uma API de busca publica, sem login
nem chave, usada pelo proprio site para a busca de produtos:

    GET https://{dominio}/api/catalog_system/pub/products/search?ft={termo}

Este script NAO roda dentro do ciclo de request do FastAPI — e um job
que deve ser executado periodicamente (cron, GitHub Actions, etc), fora
do horario de pico, com um intervalo educado entre requisicoes.

IMPORTANTE (leia antes de rodar contra um site de verdade):
  1. Confira o robots.txt do dominio antes de apontar o scraper pra ele.
  2. So testamos a API confirmada no Carrefour (migrou pra VTEX em 2020).
     Pra Pao de Acucar (e qualquer outra loja), rode primeiro
     `python -m app.scripts.scraper_precos --verificar <dominio>` — se
     a loja nao for VTEX, o script avisa em vez de inventar dado.
  3. Isso NAO foi testado contra um site real a partir deste ambiente —
     a rede daqui nao alcança dominios de varejo. Teste localmente antes
     de agendar em producao.
  4. Uso e so para comparacao de preco pessoal/academica — respeite os
     termos de uso do site.

Uso:
    python -m app.scripts.scraper_precos --verificar www.carrefour.com.br
    python -m app.scripts.scraper_precos --loja "Carrefour" --termos "arroz,feijao,acucar"
"""
from __future__ import annotations

import argparse
import sys
import time
from decimal import Decimal

import httpx

from app.core.database import SessionLocal
from app.models.historico_preco import HistoricoPreco
from app.models.loja_externa import LojaExterna
from app.models.produto import Produto

INTERVALO_ENTRE_REQUISICOES_SEGUNDOS = 1.5


def verificar_e_vtex(dominio: str) -> bool:
    """Testa se um dominio expoe a API publica de catalogo da VTEX.
    Roda isso ANTES de cadastrar uma loja nova no scraper."""
    url = f"https://{dominio}/api/catalog_system/pub/products/search?ft=arroz&_from=0&_to=0"
    try:
        resp = httpx.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0 (Mercadez price-check)"})
    except httpx.HTTPError as e:
        print(f"[ERRO] Nao consegui conectar em {dominio}: {e}")
        return False

    if resp.status_code == 200 and isinstance(resp.json(), list):
        print(f"[OK] {dominio} responde como VTEX. {len(resp.json())} resultado(s) de teste.")
        return True

    print(f"[NAO E VTEX] {dominio} respondeu {resp.status_code} ou formato inesperado — "
          f"precisa de um adaptador diferente (ver docstring do modulo).")
    return False


def _buscar_produtos_vtex(dominio: str, termo: str) -> list[dict]:
    url = f"https://{dominio}/api/catalog_system/pub/products/search"
    resp = httpx.get(
        url,
        params={"ft": termo, "_from": 0, "_to": 19},
        timeout=15,
        headers={"User-Agent": "Mozilla/5.0 (Mercadez price-check)"},
    )
    resp.raise_for_status()
    return resp.json()


def _extrair_preco(produto_vtex: dict) -> Decimal | None:
    """A VTEX guarda o preco dentro de items[].sellers[].commertialOffer.Price —
    pega o primeiro seller/oferta disponivel."""
    for item in produto_vtex.get("items", []):
        for seller in item.get("sellers", []):
            oferta = seller.get("commertialOffer", {})
            preco = oferta.get("Price")
            if preco:
                return Decimal(str(preco))
    return None


def rodar(loja_nome: str, dominio: str, termos: list[str]) -> None:
    db = SessionLocal()
    try:
        loja = db.query(LojaExterna).filter_by(nome=loja_nome).one_or_none()
        if loja is None:
            loja = LojaExterna(nome=loja_nome, dominio=dominio, plataforma="VTEX")
            db.add(loja)
            db.flush()

        total_atualizados = 0
        for termo in termos:
            try:
                resultados = _buscar_produtos_vtex(dominio, termo)
            except httpx.HTTPError as e:
                print(f"[ERRO] Falha buscando '{termo}' em {dominio}: {e}")
                time.sleep(INTERVALO_ENTRE_REQUISICOES_SEGUNDOS)
                continue

            for item_vtex in resultados:
                nome = item_vtex.get("productName")
                preco = _extrair_preco(item_vtex)
                if not nome or preco is None:
                    continue

                produto = (
                    db.query(Produto)
                    .filter_by(loja_externa_id=loja.id, nome_produto=nome)
                    .one_or_none()
                )
                if produto is None:
                    produto = Produto(
                        nome_produto=nome,
                        preco=preco,
                        quantidade=0,  # loja externa nao tem estoque nosso
                        origem="EXTERNO",
                        loja_externa_id=loja.id,
                    )
                    db.add(produto)
                    db.flush()
                    db.add(HistoricoPreco(produto_id=produto.id, preco=preco))
                elif produto.preco != preco:
                    produto.preco = preco
                    db.add(HistoricoPreco(produto_id=produto.id, preco=preco))

                total_atualizados += 1

            time.sleep(INTERVALO_ENTRE_REQUISICOES_SEGUNDOS)

        db.commit()
        print(f"[OK] {total_atualizados} produtos atualizados de {loja_nome}.")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verificar", metavar="DOMINIO", help="So testa se o dominio e VTEX, nao grava nada")
    parser.add_argument("--loja", help="Nome da loja externa (ex: 'Carrefour')")
    parser.add_argument("--dominio", help="Dominio da loja (ex: www.carrefour.com.br)")
    parser.add_argument("--termos", help="Termos de busca separados por virgula (ex: 'arroz,feijao')")
    args = parser.parse_args()

    if args.verificar:
        sys.exit(0 if verificar_e_vtex(args.verificar) else 1)

    if not (args.loja and args.dominio and args.termos):
        parser.error("--loja, --dominio e --termos sao obrigatorios (ou use --verificar)")

    rodar(args.loja, args.dominio, [t.strip() for t in args.termos.split(",") if t.strip()])