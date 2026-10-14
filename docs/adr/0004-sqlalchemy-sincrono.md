# 0004 — SQLAlchemy síncrono

- **Status:** Aceito
- **Data:** 2026-10-13

## Contexto
O FastAPI aceita rotas síncronas (`def`) e assíncronas (`async def`), e o SQLAlchemy 2 oferece `Session` e `AsyncSession`. A escolha atravessa o código inteiro — rotas, dependências, retrievers, pipeline de ingestão e testes — e por isso é cara de reverter depois.

Três fatos do projeto pesam na decisão:
- As interfaces da ARCHITECTURE (`Embedder`, `Retriever`, `LLMClient`) já são métodos `def`.
- Embedding e reranking rodam localmente e são limitados por CPU, não por espera de rede.
- O uso previsto é uma demo com um usuário por vez, desenvolvida em Windows.

## Opções consideradas
1. **Assíncrono** (`AsyncSession` + psycopg em modo async, rotas `async def`) — não ocupa uma thread enquanto espera o banco e escala melhor com muitas requisições simultâneas; mas obrigaria a tornar os Protocols assíncronos, o trabalho de CPU (embedding, rerank) teria de ir para threads de qualquer forma, os testes passariam a depender de `pytest-asyncio`, e no Windows o psycopg assíncrono não funciona com o event loop padrão (Proactor), exigindo configuração extra.
2. **Síncrono** (`Session` + psycopg 3, rotas `def`) — código linear, fácil de depurar e de testar; o FastAPI executa rotas `def` em um threadpool, então a API continua atendendo requisições em paralelo. O custo é que cada requisição em andamento ocupa uma thread e uma conexão.

## Decisão
SQLAlchemy síncrono: `Session` com psycopg 3, e rotas e dependências que acessam o banco declaradas com `def`.

## Consequências
- Toda rota ou dependência que usa a sessão é `def`. Uma rota `async def` chamando a sessão síncrona bloquearia o event loop e travaria as outras requisições.
- A concorrência fica limitada pelo threadpool do FastAPI (40 threads por padrão) e pelo pool de conexões do SQLAlchemy (5 conexões + 10 de overflow por padrão). É mais que suficiente para a demo; se virar gargalo, os dois limites são configuráveis antes de se pensar em migrar.
- Os Protocols da ARCHITECTURE ficam como estão, e os testes usam o `TestClient` síncrono, sem plugin de async.
- Rever esta decisão se entrar streaming da resposta do LLM (está em "Ideias para depois" no ROADMAP) ou se houver muitas consultas simultâneas esperando o banco ou o LLM. O psycopg 3 atende aos dois modos, então a migração não trocaria o driver.
