# Mercadez Backend

API REST do projeto **Mercadez** — plataforma de comparação de preços entre mercados.  
Construída com **Spring Boot 3.3 + PostgreSQL + JWT**, pronta para deploy no **Render (plano gratuito)**.

---

## Stack

| Camada       | Tecnologia                          |
|--------------|-------------------------------------|
| Framework    | Spring Boot 3.3 (Java 17)           |
| Banco        | PostgreSQL (Render Free Tier)       |
| Auth         | JWT (jjwt 0.12.6) + Spring Security |
| Validação    | Jakarta Bean Validation             |
| Testes       | JUnit 5 + MockMvc + H2 in-memory    |
| Build        | Maven                               |

---

## Endpoints

### Usuários
| Método | Rota               | Auth | Descrição                 |
|--------|--------------------|------|---------------------------|
| POST   | `/usuarios/cadastro` | ✗   | Cadastro de cliente       |
| POST   | `/usuarios/login`    | ✗   | Login → retorna JWT       |
| GET    | `/usuarios/me`       | ✓   | Dados do usuário logado   |

### Afiliados (Lojistas)
| Método | Rota               | Auth | Descrição                  |
|--------|--------------------|------|----------------------------|
| POST   | `/afiliados`         | ✗   | Cadastro de lojista        |
| POST   | `/afiliados/login`   | ✗   | Login → retorna JWT        |
| GET    | `/afiliados/me`      | ✓   | Dados do afiliado logado   |

### Produtos
| Método | Rota                        | Auth      | Descrição                         |
|--------|-----------------------------|-----------|-----------------------------------|
| GET    | `/produtos`                 | ✗         | Lista todos os produtos ativos    |
| GET    | `/produtos?afiliado=<id>`   | ✗         | Filtra por loja                   |
| GET    | `/produtos/buscar?q=<termo>`| ✗         | Busca por nome ou tag             |
| GET    | `/produtos/comparar?nome=<>`| ✗         | Comparação de preços entre lojas  |
| POST   | `/produtos`                 | AFILIADO  | Cadastra produto                  |
| PUT    | `/produtos/{id}`            | AFILIADO  | Atualiza produto                  |
| DELETE | `/produtos/{id}`            | AFILIADO  | Remove produto (soft-delete)      |

### Contato
| Método | Rota       | Auth | Descrição              |
|--------|------------|------|------------------------|
| POST   | `/contato` | ✗    | Formulário Fale Conosco|

---

## Estrutura do Projeto

```
src/main/java/com/mercadez/
├── MercadezApplication.java
├── config/
│   └── SecurityConfig.java       # CORS, JWT filter, rotas protegidas
├── controller/
│   ├── UsuarioController.java
│   ├── AfiliadoController.java
│   ├── ProdutoController.java
│   └── ContatoController.java
├── dto/                           # Request/Response objects
├── exception/                     # Erros customizados + handler global
├── model/                         # Entidades JPA
├── repository/                    # Spring Data JPA
├── security/
│   ├── JwtService.java            # Geração/validação de tokens
│   └── JwtAuthFilter.java         # Filtro que lê o Bearer token
└── service/                       # Regras de negócio
```
