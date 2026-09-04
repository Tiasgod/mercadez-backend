# Mercadez Backend (Python)

API REST do projeto **Mercadez** — plataforma de comparação de preços entre mercados.
Migrado de **Spring Boot (Java)** para **FastAPI (Python)**, mantendo compatibilidade
total com o frontend existente.

## Sobre esta migração

Este backend substitui o backend Java original (`mercadez-backend-main`), mantendo:

- As mesmas rotas, métodos HTTP e formatos de request/response (incluindo o campo
  `nome_proprietario` em snake_case no recurso de afiliados, preservado por
  compatibilidade com o frontend).
- O mesmo formato de erro (`{status, erro, mensagem, timestamp}`).
- Os mesmos status HTTP (200, 201, 204, 400, 401, 404, 500).

E corrige/adiciona em relação ao original:

- **Autorização de fato imposta.** No backend Java, `SecurityConfig` liberava
  `anyRequest().permitAll()` e a lista de rotas protegidas do `JwtAuthFilter` nunca
  era usada — a "proteção" das rotas de afiliado dependia só do controller extrair
  o ID do token, o que gerava `NullPointerException` (HTTP 500) em vez de 401 quando
  não havia token. Aqui, as dependências (`app/deps.py`) bloqueiam explicitamente
  com 401 (sem token/token inválido) e 403 (perfil errado).
- **`/listas` implementado de verdade.** O frontend (`listas.html`) já chamava
  `GET /listas` e `DELETE /listas/{id}`, mas o endpoint nunca existiu no backend
  Java — a página falhava silenciosamente. Agora existe (`GET`, `POST`, `DELETE`),
  representando a lista de compras pessoal de cada usuário.
- **Migrations versionadas com Alembic**, em vez de `ddl-auto=update` (Hibernate
  criando/alterando o schema automaticamente, sem histórico).

## Stack

| Camada       | Tecnologia                          |
|--------------|--------------------------------------|
| Framework    | FastAPI                              |
| Banco        | PostgreSQL                           |
| ORM          | SQLAlchemy 2.0                       |
| Migrations   | Alembic                              |
| Auth         | JWT (PyJWT) + bcrypt (passlib)       |
| Validação    | Pydantic v2                          |
| Testes       | Pytest + HTTPX (TestClient) + SQLite em memória |

## Endpoints

### Usuários
| Método | Rota | Auth | Descrição |
|--------|------|------|-----------|
| POST | `/usuarios/cadastro` | ✗ | Cadastro de cliente |
| POST | `/usuarios/login` | ✗ | Login → retorna JWT |
| GET | `/usuarios/me` | ✓ (usuário) | Dados do usuário logado |

### Afiliados (lojistas)
| Método | Rota | Auth | Descrição |
|--------|------|------|-----------|
| POST | `/afiliados` | ✗ | Cadastro de lojista |
| POST | `/afiliados/login` | ✗ | Login → retorna JWT |
| GET | `/afiliados/me` | ✓ (afiliado) | Dados do afiliado logado |

### Produtos
| Método | Rota | Auth | Descrição |
|--------|------|------|-----------|
| GET | `/produtos` (+ `?afiliado=<id>`) | ✗ | Lista produtos ativos |
| GET | `/produtos/buscar?q=<termo>` | ✗ | Busca por nome ou tag |
| GET | `/produtos/comparar?nome=<>` | ✗ | Comparação de preços entre afiliados |
| POST | `/produtos` | ✓ (afiliado) | Cadastra produto |
| PUT | `/produtos/{id}` | ✓ (afiliado, dono) | Atualiza produto |
| DELETE | `/produtos/{id}` | ✓ (afiliado, dono) | Remove produto (soft-delete) |

### Listas (NOVO — implementado nesta migração)
| Método | Rota | Auth | Descrição |
|--------|------|------|-----------|
| GET | `/listas` | ✓ (usuário) | Itens da lista de compras do usuário |
| POST | `/listas` | ✓ (usuário) | Adiciona um produto à lista |
| DELETE | `/listas/{id}` | ✓ (usuário) | Remove um item da lista |

### Contato
| Método | Rota | Auth | Descrição |
|--------|------|------|-----------|
| POST | `/contato` | ✗ | Formulário "Fale Conosco" |

Documentação interativa (gerada automaticamente pelo FastAPI):
- Swagger: `/docs`
- ReDoc: `/redoc`
- OpenAPI JSON: `/openapi.json`

## Estrutura do projeto

```
backend/
├── app/
│   ├── main.py              # app FastAPI, CORS, exception handlers
│   ├── deps.py               # get_db, autenticação (extração/validação de JWT)
│   ├── exceptions.py         # exceções de negócio customizadas
│   ├── core/
│   │   ├── config.py         # Settings (variáveis de ambiente)
│   │   ├── database.py       # engine, SessionLocal, Base
│   │   └── security.py       # hash de senha (bcrypt) + JWT
│   ├── models/                # SQLAlchemy (usuario, afiliado, produto, contato, lista)
│   ├── schemas/                # Pydantic (request/response)
│   ├── routers/                 # endpoints por recurso
│   └── services/                 # regra de negócio
├── alembic/                       # migrations versionadas
├── tests/                          # Pytest (21 testes, SQLite em memória)
├── .env.example
├── requirements.txt
└── alembic.ini
```

## Instalação (Windows / PowerShell)

```powershell
# Criar ambiente virtual
python -m venv venv

# Ativar (se der erro de política de execução, rode antes:
# Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser)
.\venv\Scripts\Activate.ps1

# Instalar dependências
pip install -r requirements.txt

# Copiar e preencher as variáveis de ambiente
copy .env.example .env

# Rodar as migrations
alembic upgrade head

# Executar o servidor
uvicorn app.main:app --reload
```

## Instalação (Linux / macOS)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

## Banco de dados

1. Crie um banco PostgreSQL local (ou use um serviço gerenciado).
2. Preencha `DATABASE_URL` no `.env`, no formato:
   `postgresql+psycopg2://usuario:senha@host:porta/nome_do_banco`
3. Rode as migrations: `alembic upgrade head`
4. Para gerar uma nova migration depois de alterar um model:
   `alembic revision --autogenerate -m "descricao da mudanca"`
5. Para verificar a conexão, acesse `/docs` — se o Swagger carregar, a app subiu;
   qualquer chamada que toque o banco (ex: `POST /usuarios/cadastro`) confirma a conexão.

## Variáveis de ambiente (`.env`)

```
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/mercadez
SECRET_KEY=troque-esta-chave-em-producao
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
CORS_ORIGINS=https://mercadez-ten.vercel.app,http://localhost:5500,http://127.0.0.1:5500
```

`.env` nunca deve ser commitado (já está no `.gitignore`); `.env.example` documenta
as chaves sem valores reais.

## Testes

```bash
pytest
```

21 testes cobrindo cadastro, login, autenticação, autorização (incluindo os casos
negativos — token de usuário em rota de afiliado e vice-versa), CRUD de produtos,
contato e o novo recurso `/listas`.

## Testando manualmente via Swagger

1. Suba o servidor (`uvicorn app.main:app --reload`) e abra `http://localhost:8000/docs`.
2. `POST /usuarios/cadastro` — crie um usuário.
3. `POST /usuarios/login` — copie o `token` retornado.
4. Clique em **Authorize** no Swagger e cole `Bearer <token>`.
5. `GET /usuarios/me` — confirme que retorna os dados do usuário.
6. Repita 2-4 com `POST /afiliados` e `POST /afiliados/login` para testar o fluxo
   de lojista.
7. Com o token de afiliado, `POST /produtos` para cadastrar um produto.
8. Com o token de usuário, `POST /listas` (informando o `produtoId` cadastrado)
   e depois `GET /listas` para conferir.

## Integração com o frontend

Nenhuma mudança é necessária no frontend (`API_URL` em `js/api.js` continua
apontando para a mesma URL base) — **exceto** que agora `/listas` responde de
verdade, então `listas.html` passa a funcionar em vez de mostrar sempre "lista vazia".

## Deploy

Pensando em plataformas como Render, Railway ou Fly.io:

- Configure `DATABASE_URL`, `SECRET_KEY` e `CORS_ORIGINS` como variáveis de ambiente
  da plataforma (nunca no código).
- Comando de build: `pip install -r requirements.txt`
- Comando de start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Rode `alembic upgrade head` como parte do processo de deploy (ou manualmente na
  primeira vez), antes de a aplicação começar a receber tráfego.
- HTTPS é fornecido pela própria plataforma (Render/Railway/Fly.io terminam TLS).
- Configure `CORS_ORIGINS` com o domínio real do frontend em produção.
