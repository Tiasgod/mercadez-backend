from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urljoin, parse_qs, unquote
import json
import re
import unicodedata

BASE = 'https://www.nagumo.com.br'
URL = BASE + '/on/demandware.store/Sites-Nagumo-Site/pt_BR/Stores-AvailableStores'
HOSTS = {'www.nagumo.com.br', 'nagumo.com.br'}
CIDADES = {'suzano', 'mogi das cruzes', 'mogi', 'poa', 'itaquaquecetuba',
           'itaqua', 'ferraz de vasconcelos', 'ferraz', 'aruja', 'guarulhos',
           'guararema', 'santa isabel', 'biritiba mirim', 'salesopolis'}
DEPARTAMENTOS_ESPERADOS = {'acougue', 'basicos-e-matinais', 'bazar', 'bebidas',
    'frios-e-laticinios', 'higiene-e-perfumaria', 'hortifruti', 'limpeza',
    'padaria', 'peixaria', 'pet-shop', 'mercearia-doce', 'mercearia-salgada'}


def agora():
    return datetime.now(timezone.utc).isoformat()


def normalizar(texto):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFD', str(texto).lower())
                           if unicodedata.category(c) != 'Mn').split())


def salvar_json(nome, dados):
    destino = Path(nome)
    temp = destino.with_suffix(destino.suffix + '.tmp')
    temp.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(destino)
    print(f'[OK] {destino}')


def verificar_http(status, etapa):
    print(f'[HTTP {status}] {etapa}')
    if status in (401, 403, 429):
        raise RuntimeError(f'Acesso recusado em {etapa}; descoberta interrompida.')
    if status != 200:
        raise RuntimeError(f'HTTP {status} em {etapa}')


def filtrar_lojas(dados):
    if isinstance(dados, dict):
        dados = next((dados[k] for k in ('stores', 'storesResult', 'data')
                      if isinstance(dados.get(k), list)), None)
    if not isinstance(dados, list):
        raise ValueError('Formato inesperado na lista de lojas')
    lojas = [l for l in dados if isinstance(l, dict)
             and normalizar(l.get('city', '')) in CIDADES]
    return lojas, len(dados)


def descobrir_lojas(page):
    resposta = page.evaluate('''async url => {
        const r = await fetch(url, {credentials: 'include', headers: {
            'Accept': '*/*', 'X-Requested-With': 'XMLHttpRequest'}});
        return {status: r.status, texto: await r.text()};
    }''', URL)
    verificar_http(resposta['status'], 'Lojas')
    return filtrar_lojas(json.loads(resposta['texto']))


def extrair_links(page):
    return page.evaluate('''() => Array.from(document.querySelectorAll('a[href]')).map(a => ({
        href: a.href,
        texto: (a.innerText || a.textContent || a.getAttribute('aria-label') || '').trim(),
        atributos: Object.fromEntries(['data-cgid', 'data-category-id', 'data-categoryid']
            .filter(k => a.hasAttribute(k)).map(k => [k, a.getAttribute(k)]))
    }))''')


def identificar(link):
    p = urlparse(urljoin(BASE, link.get('href') or ''))
    if p.scheme not in ('http', 'https') or p.hostname not in HOSTS:
        return None, 'externo'
    partes = [unquote(x) for x in p.path.split('/') if x]
    if partes[:2] != ['categoria', 'departamentos'] or len(partes) < 3:
        return None, 'fora_da_hierarquia'
    h = partes[2:]
    if any(re.search(r'\.(?:html?|aspx|php)$', x, re.I) for x in h):
        return None, 'pagina_de_produto'
    if any(not re.fullmatch(r'[\w-]+', x) for x in h):
        return None, 'caminho_nao_reconhecido'
    evidencias = []
    for fonte, valor in link.get('atributos', {}).items():
        if fonte in ('data-cgid', 'data-category-id', 'data-categoryid') and valor and valor.strip():
            evidencias.append({'fonte': fonte, 'valor': valor.strip()})
    for valor in parse_qs(p.query).get('cgid', []):
        if valor.strip():
            evidencias.append({'fonte': 'query:cgid', 'valor': valor.strip()})
    nome = ' '.join((link.get('texto') or '').split())
    nome = re.sub(r'^ver tudo(?: em)?\s+', '', nome, flags=re.I)
    if not nome or normalizar(nome) in ('ver tudo', 'todos', 'ver mais'):
        nome = h[-1].replace('-', ' ').title()
    return {'nome': nome, 'departamento': h[0], 'slug': h[-1], 'nivel': len(h),
            'hierarquia': h, 'url': BASE + '/' + '/'.join(p.path.split('/')[1:]).rstrip('/') + '/',
            'evidencias_codigo': evidencias}, None


def mapear(links):
    registros = {}
    descartes = defaultdict(set)
    for link in links:
        item, motivo = identificar(link)
        if motivo:
            descartes[motivo].add(link.get('href', ''))
            continue
        chave = tuple(item['hierarquia'])
        if chave in registros:
            anterior = registros[chave]
            for e in item['evidencias_codigo']:
                if e not in anterior['evidencias_codigo']:
                    anterior['evidencias_codigo'].append(e)
        else:
            registros[chave] = item
    categorias = [registros[k] for k in sorted(registros)]
    conflitos = []
    for item in categorias:
        valores = sorted({e['valor'] for e in item['evidencias_codigo']})
        item['codigo_confirmado'] = valores[0] if len(valores) == 1 else None
        item['codigo_validado_em_api'] = False
        if len(valores) > 1:
            conflitos.append({'hierarquia': item['hierarquia'], 'valores': valores})
    por_codigo = defaultdict(list)
    for item in categorias:
        if item['codigo_confirmado']:
            por_codigo[item['codigo_confirmado']].append(item)
    for codigo, itens in por_codigo.items():
        if len(itens) > 1:
            conflitos.append({'codigo_compartilhado': codigo, 'hierarquias': [i['hierarquia'] for i in itens]})
            for item in itens:
                item['codigo_confirmado'] = None
    arvore = {}
    for item in categorias:
        nivel = arvore
        for slug in item['hierarquia']:
            no = nivel.setdefault(slug, {'nome': slug.replace('-', ' ').title(), 'slug': slug,
                'url': None, 'codigo_confirmado': None, 'observado_no_menu': False, 'subcategorias': {}})
            nivel = no['subcategorias']
        no.update(nome=item['nome'], url=item['url'], codigo_confirmado=item['codigo_confirmado'], observado_no_menu=True)
    def converter(nos):
        return [dict(no, subcategorias=converter(no['subcategorias'])) for no in nos.values()]
    departamentos = {i['departamento'] for i in categorias}
    estatisticas = {'links_analisados': len(links), 'departamentos_encontrados': len(departamentos),
        'categorias_encontradas': len(categorias), 'subcategorias_encontradas': sum(i['nivel'] > 1 for i in categorias),
        'codigos_confirmados': sum(bool(i['codigo_confirmado']) for i in categorias),
        'codigos_validados_em_api': 0, 'categorias_por_nivel': dict(Counter(i['nivel'] for i in categorias)),
        'subcategorias_por_departamento': dict(Counter(i['departamento'] for i in categorias if i['nivel'] > 1)),
        'departamentos_ausentes': sorted(DEPARTAMENTOS_ESPERADOS - departamentos),
        'departamentos_novos': sorted(departamentos - DEPARTAMENTOS_ESPERADOS),
        'links_descartados_distintos': {k: len(v) for k, v in descartes.items()},
        'conflitos_codigo': len(conflitos)}
    return {'departamentos': converter(arvore), 'categorias': categorias, 'estatisticas': estatisticas,
            'conflitos_codigo': conflitos, 'cobertura_completa_confirmada': False,
            'catalogo_por_filial_verificado': False}


def main():
    from playwright.sync_api import sync_playwright
    relatorio = {'inicio': agora(), 'status': 'iniciado', 'versao': 2}
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(locale='pt-BR', timezone_id='America/Sao_Paulo')
            try:
                page = context.new_page()
                r = page.goto(BASE, wait_until='domcontentloaded', timeout=60000)
                verificar_http(r.status if r else 0, 'Pagina inicial')
                lojas, total = descobrir_lojas(page)
                salvar_json('lojas_nagumo_regiao.json', lojas)
                relatorio.update(total_lojas_consultadas=total, lojas_regiao=len(lojas))
                if not lojas:
                    raise RuntimeError('Nenhuma loja regional identificada')
                # Aguarda a renderização normal do menu, sem visitar outras páginas.
                page.wait_for_timeout(1500)
                catalogo = mapear(extrair_links(page))
                catalogo.update(data_mapeamento=agora(), fonte=BASE,
                    escopo='Menu publico da sessao atual; nao verificado por filial',
                    lojas_regiao=lojas, filiais=[{'storeId': l.get('storeId'), 'storeName': l.get('storeName'),
                        'catalogo_verificado': False} for l in lojas])
                relatorio.update(catalogo['estatisticas'])
                salvar_json('catalogo_nagumo.json', catalogo)
                if not catalogo['categorias']:
                    raise RuntimeError('Nenhuma categoria identificada no menu')
                for item in catalogo['categorias']:
                    print('    ' * (item['nivel'] - 1) + item['nome'] + ' | ' + str(item['codigo_confirmado'] or 'ID nao observado'))
                relatorio['status'] = 'mapeamento_parcial'
                print(json.dumps(relatorio, ensure_ascii=False, indent=2))
            finally:
                context.close()
                browser.close()
        return 0
    except Exception as erro:
        relatorio.update(status='falha', erro=str(erro))
        print(f'[ERRO] {erro}')
        return 1
    finally:
        relatorio['fim'] = agora()
        salvar_json('relatorio_descoberta.json', relatorio)


if __name__ == '__main__':
    raise SystemExit(main())
