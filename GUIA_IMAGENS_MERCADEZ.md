# Imagens de produtos - Mercadez

Esta versao guarda **URLs de fotos** recebidas no catalogo do Nagumo, nao baixa os arquivos.

## Preparacao

1. Use um backup e confirme que `DATABASE_URL` em seu `.env` aponta para o banco Neon correto.
2. Instale dependencias: `py -m pip install -r requirements.txt`.
3. Instale o navegador, se necessario: `py -m playwright install chromium`.
4. Confira a versao de migracao: `py -m alembic current`.
5. Aplique a migracao: `py -m alembic upgrade head`.

**Nao execute o scraper antes da migracao 0005.**

## Teste pequeno (grava no banco)

```powershell
py -m app.scripts.scraper_nagumo --loja Nagumo_Suzano_Dona_Benta --loja-codigo 23 --categorias hortifruti
```

Confirme antes que o ID 23 corresponde a loja esperada. Depois, execute o catalogo completo com `--todos`.
A coleta de listagem inclui somente as fotos que o endpoint de categoria realmente publica; outras fotos de paginas de detalhe exigiriam uma segunda etapa.

## API

As rotas `/produtos`, `/produtos/buscar`, `/produtos/comparar`, `/comparacao` e `/ofertas` passam a trazer:

- `imagemUrl`: URL principal, ou `null`.
- `imagensUrls`: lista de URLs disponiveis, ou `[]`.

O JSON mantem os campos existentes, para nao quebrar clientes antigos. Web e Android ainda precisam consumir os campos novos.

Exemplo web:

```jsx
<img src={produto.imagemUrl || '/sem-imagem.png'} alt={produto.nomeProduto} />
```

Exemplo Android Compose com biblioteca Coil (adicione a dependencia no app):

```kotlin
AsyncImage(model = produto.imagemUrl, contentDescription = produto.nomeProduto)
```

## Verificacao no PostgreSQL

```sql
SELECT id, nome_produto, imagem_url, imagens_urls
FROM produtos
WHERE loja_externa_id IS NOT NULL AND imagem_url IS NOT NULL
LIMIT 10;
```

Alguns produtos podem nao ter imagens no endpoint de listagem. A URL tambem pode deixar de funcionar se o Nagumo mover ou bloquear os arquivos. O acesso direto deve ser validado no mobile e web.
