# 0002 — Núcleo do pipeline sem LangChain/LlamaIndex

- **Status:** Aceito
- **Data:** 2026-10-09

## Contexto
O objetivo do projeto é demonstrar entendimento de RAG: chunking, recuperação, fusão de rankings, reranking, citações e avaliação. Frameworks de RAG resolvem essas etapas com poucas linhas, mas escondem justamente as decisões que o projeto quer mostrar e medir.

## Opções consideradas
1. **LangChain / LlamaIndex** — prototipagem rápida, muitos integradores prontos; abstrações pesadas, difícil controlar offsets e citações, e o código "mostra" pouco do que foi entendido.
2. **Implementação própria com interfaces pequenas** (`Protocol` por etapa) — mais código, mas cada etapa é explícita, testável e comparável.

## Decisão
Implementar o núcleo (parser, chunkers, retrievers, RRF, validação de citações, métricas) com bibliotecas de baixo nível (PyMuPDF, sentence-transformers, SQLAlchemy, SDK do provedor de LLM).

## Consequências
- Mais código para escrever e testar — compensado por entender e conseguir explicar cada parte.
- Bibliotecas de avaliação (ex.: RAGAS) podem ser usadas **como comparação** das métricas próprias, não como substituto.
- Se no futuro fizer sentido, um adaptador para framework pode ser adicionado por fora do núcleo.
