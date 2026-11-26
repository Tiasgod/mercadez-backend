"""Job exclusivo de imagens ausentes. Não cria produtos nem altera preços."""
import argparse
import os
import time
from collections import defaultdict
from sqlalchemy import select, update, or_, func
from app.core.database import SessionLocal
from app.models import Produto, LojaExterna
from app.scripts import scraper_nagumo as nagumo

LOJAS = {
    'Nagumo Poa': '22', 'Nagumo Poa_Kemel': '45', 'Nagumo Itaqua': '30',
    'Nagumo Suzano': '23',  # código usado na coleta histórica; mesma unidade Dona Benta
    'Nagumo_Suzano_Dona_Benta': '23', 'Nagumo_Mogi_Alto_Ipiranga': '52',
}

def ausente():
    return or_(Produto.imagem_url.is_(None), func.trim(Produto.imagem_url) == '')

def pendentes(nome):
    with SessionLocal() as db:
        rows = db.execute(select(Produto.id, Produto.nome_produto, Produto.imagens_urls)
            .join(LojaExterna, Produto.loja_externa_id == LojaExterna.id)
            .where(LojaExterna.nome == nome, ausente())).all()
    mapa = defaultdict(list)
    for row in rows:
        mapa[row.nome_produto.strip()].append((row.id, row.imagens_urls))
    return mapa

def salvar(mapa, encontrados, simular=False):
    total = 0
    with SessionLocal() as db:
        for nome, urls in encontrados.items():
            for id_, antigas in mapa.get(nome, []):
                imagens = list(dict.fromkeys(urls + [u for v in (antigas if isinstance(antigas, list) else []) if (u := nagumo.normalizar_url_imagem(v))]))
                if simular:
                    total += 1
                else:
                    result = db.execute(update(Produto).where(Produto.id == id_, ausente())
                        .values(imagem_url=imagens[0], imagens_urls=imagens))
                    total += result.rowcount
        if not simular:
            db.commit()
    for nome in encontrados:
        mapa.pop(nome, None)
    return total

def rodar(simular=False):
    if not os.environ.get('DATABASE_URL') and not os.path.isfile('.env'):
        raise RuntimeError('Configure DATABASE_URL antes de executar.')
    executar(simular)

def executar(simular):
    falhas = 0
    total = 0
    with nagumo.sync_playwright() as pw:
        for nome, codigo in LOJAS.items():
            mapa = pendentes(nome)
            print(f'[INFO] {nome}: {sum(map(len, mapa.values()))} produtos sem imagem', flush=True)
            if not mapa:
                continue
            browser = context = None
            try:
                browser, context = nagumo._criar_navegador(pw)
                page = context.new_page()
                nagumo._abrir_nagumo(page)
                page, context, browser = nagumo._selecionar_loja(page, codigo, nagumo.LATITUDE, nagumo.LONGITUDE, pw, browser, context)
                for categoria in nagumo._descobrir_departamentos(page):
                    if not mapa: break
                    try:
                        encontrados = {}
                        for item in nagumo._buscar_categoria(context, categoria):
                            nome_produto = (item.get('productName') or '').strip()
                            if nome_produto in mapa:
                                urls = nagumo._extrair_imagens(item)
                                if urls: encontrados.setdefault(nome_produto, urls)
                        n = salvar(mapa, encontrados, simular)
                        total += n
                        print(f'[OK] {nome} / {categoria}: {n} imagens', flush=True)
                    except Exception as exc:
                        falhas += 1
                        print(f'[ERRO] {nome} / {categoria}: {type(exc).__name__}', flush=True)
                    time.sleep(nagumo.INTERVALO_ENTRE_CATEGORIAS_SEGUNDOS)
                print(f'[INFO] {nome}: {sum(map(len, mapa.values()))} ainda sem correspondência', flush=True)
            except Exception as exc:
                falhas += 1
                print(f'[ERRO] {nome}: {type(exc).__name__}', flush=True)
            finally:
                if browser is not None: browser.close()
    print(f'[FIM] Imagens {"simuladas" if simular else "gravadas"}: {total}; falhas: {falhas}', flush=True)
    if falhas: raise SystemExit(1)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simular', action='store_true')
    rodar(parser.parse_args().simular)
