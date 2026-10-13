# 0001 — PostgreSQL + pgvector como vector store

- **Status:** Aceito
- **Data:** 2026-10-09

## Contexto
O sistema guarda documentos, chunks, metadados (página, offsets, estratégia), logs de consulta e vetores. Também precisa de busca lexical para comparar com a busca densa.

## Opções consideradas
1. **Banco vetorial dedicado (Chroma, Qdrant, Weaviate)** — feito para vetores, APIs simples; mas os dados relacionais e a busca lexical ficariam em outro lugar, exigindo sincronizar dois sistemas.
2. **PostgreSQL + pgvector** — vetores, relacional, full-text search e transações no mesmo banco; muito usado em produção; menos recursos específicos de busca vetorial.

## Decisão
PostgreSQL 16 com pgvector, índice HNSW para vetores e `tsvector` + GIN para busca lexical.

## Consequências
- Busca densa, lexical e híbrida usam o mesmo banco e os mesmos filtros (documento, estratégia de chunking) em SQL.
- Remover um documento remove chunks em cascata, sem inconsistência entre sistemas.
- A dimensão do vetor fica fixa na coluna: trocar de modelo de embedding exige migração.
- `ts_rank_cd` não é BM25; se a avaliação mostrar que isso importa, rever (SPEC D4).
