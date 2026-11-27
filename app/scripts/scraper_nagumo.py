name: Mercadez - Nagumo Diagnostico

"on":
  workflow_dispatch:
    inputs:
      acesso_confirmado:
        description: "Acesso e limites confirmados com o fornecedor"
        type: boolean
        required: true
        default: false

permissions:
  contents: read

concurrency:
  group: mercadez-scraper-imagens
  cancel-in-progress: false

jobs:
  atualizar-catalogo:
    name: Coleta sequencial Nagumo
    if: ${{ inputs.acesso_confirmado && vars.NAGUMO_COLETA_AUTORIZADA == 'true' }}
    runs-on: ubuntu-latest
    timeout-minutes: 350
    env:
      PYTHONUNBUFFERED: "1"

    steps:
      - uses: actions/checkout@v6

      - uses: actions/setup-python@v6
        with:
          python-version: "3.12"
          cache: pip

      - name: Instalar dependencias
        run: |
          python -m pip install -r requirements.txt
          python -m pip install playwright
          python -m playwright install --with-deps chromium

      - name: Executar scraper
        id: coleta
        shell: bash
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
        run: |
          set -o pipefail
          mkdir -p diagnostico

          echo "Commit: $GITHUB_SHA"

          python --version
          python -m playwright --version
          date -u

          python -m app.scripts.scraper_nagumo --todas-lojas --todos 2>&1 | tee diagnostico/coleta.log

      - name: Resumo do diagnostico
        if: always()
        shell: bash
        run: |
          mkdir -p diagnostico

          python - <<'PY'
          import json, os
          from collections import Counter
          from pathlib import Path

          log = Path('diagnostico/coleta.log')
          eventos = []
          lotes = 0
          loja = 'Nao iniciada'

          if log.exists():
              for linha in log.read_text(errors='replace').splitlines():
                  if linha.startswith('[INFO] Loja em processamento:'):
                      loja = linha

                  if 'Lote gravado:' in linha:
                      lotes += 1

                  try:
                      evento = json.loads(linha)
                  except ValueError:
                      continue

                  if isinstance(evento, dict) and evento.get('evento') == 'http':
                      eventos.append(evento)

          contagem = Counter(e.get('status') for e in eventos)

          linhas = [
              loja,
              f'Lotes gravados: {lotes}',
              f'Eventos HTTP registrados: {len(eventos)}',
              f'Status: {dict(contagem)}',
              'Ultimos eventos HTTP:'
          ]

          for e in eventos[-5:]:
              linhas.append(json.dumps(e, ensure_ascii=False))

          texto = '\n'.join(linhas)

          print(texto)

          Path('diagnostico/relatorio.txt').write_text(texto)

          with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as f:
              f.write('## Diagnostico Nagumo\n\n```text\n' + texto + '\n```\n')
          PY

      - name: Salvar relatorio
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: diagnostico-nagumo
          path: diagnostico/relatorio.txt
          retention-days: 7
          if-no-files-found: warn
