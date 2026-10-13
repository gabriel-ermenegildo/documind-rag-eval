# DocuMind — Arquitetura

> Como o sistema é montado. O *o quê* está em [SPEC.md](SPEC.md); o *como medir* em [EVALUATION.md](EVALUATION.md).

## 1. Visão geral

```mermaid
flowchart LR
    subgraph Ingestão
        A[PDF] --> B[Parser<br/>PyMuPDF]
        B -->|texto + página + offsets| C[Chunker]
        C --> D[Embedder]
        D --> E[(PostgreSQL<br/>+ pgvector)]
    end

    subgraph Consulta
        Q[Pergunta] --> R[Retriever<br/>denso / lexical / híbrido / rerank]
        E --> R
        R -->|top-k chunks| G[Generator<br/>LLM + saída estruturada]
        G --> V[Validador de citações]
        V --> S[Resposta + citações verificadas]
    end

    subgraph Avaliação
        GS[Golden set<br/>dev / test] --> H[Harness]
        H --> R
        H --> G
        H --> RES[results/*.json + tabela .md]
    end
```

Princípio de projeto: **cada etapa é uma interface trocável**. Parser, chunker, embedder, retriever e LLM são classes que implementam um `Protocol`; a combinação usada vem de configuração. É isso que permite comparar estratégias sem duplicar código.

## 2. Stack

| Camada | Escolha | Por quê |
|--------|---------|---------|
| Linguagem | Python 3.12 | padrão do ecossistema de IA |
| Dependências | `uv` (+ `uv.lock`) | rápido, lockfile reprodutível |
| API | FastAPI + Pydantic v2 | contrato tipado, Swagger automático |
| Banco | PostgreSQL 16 + pgvector | vetores e dados relacionais no mesmo lugar ([ADR 0001](adr/0001-pgvector-como-vector-store.md)) |
| ORM / driver | SQLAlchemy 2 + psycopg 3 | maduro, suporte ao tipo `vector` via `pgvector-python` |
| Migrações | Alembic | schema versionado |
| PDF | PyMuPDF (`pymupdf`) | rápido, dá texto por página com posição |
| Embeddings | `sentence-transformers` (local) ou API | ver SPEC D2 |
| Reranker | cross-encoder multilíngue (ex.: `BAAI/bge-reranker-v2-m3`) | reranking local sem custo |
| LLM | Gemini via SDK `google-genai` | saída estruturada nativa, tier gratuito ([ADR 0003](adr/0003-gemini-como-llm.md)) |
| Testes / lint | pytest, ruff | — |
| Infra | Docker + docker compose; GitHub Actions | — |

## 3. Estrutura de pastas

```
documind/
├── README.md
├── pyproject.toml / uv.lock
├── docker-compose.yml
├── Dockerfile
├── Makefile
├── .env.example
├── alembic/                     # migrações
├── src/documind/
│   ├── config.py                # Settings (pydantic-settings, lê .env)
│   ├── api/
│   │   ├── main.py              # cria o app FastAPI
│   │   ├── deps.py              # injeção de dependências (sessão, retriever…)
│   │   └── routes/              # documents.py, query.py, search.py, health.py
│   ├── db/
│   │   ├── models.py            # tabelas SQLAlchemy
│   │   └── session.py
│   ├── ingestion/
│   │   ├── parser.py            # PDF -> páginas com offsets
│   │   ├── chunkers.py          # FixedSizeChunker, StructureAwareChunker
│   │   └── pipeline.py          # orquestra parse -> chunk -> embed -> save
│   ├── embeddings/
│   │   ├── base.py              # Protocol Embedder
│   │   └── local.py / api.py
│   ├── retrieval/
│   │   ├── base.py              # Protocol Retriever, dataclass RetrievedChunk
│   │   ├── dense.py
│   │   ├── lexical.py
│   │   ├── hybrid.py            # RRF
│   │   └── rerank.py            # wrapper que reordena qualquer Retriever
│   ├── generation/
│   │   ├── llm/                 # base.py (Protocol LLMClient), gemini.py, fake.py
│   │   ├── prompts.py
│   │   ├── schemas.py           # saída estruturada (Pydantic)
│   │   └── citations.py         # validação de citações
│   └── eval/
│       ├── dataset.py           # carrega/valida golden set
│       ├── relevance.py         # mapeia evidência anotada -> chunks relevantes
│       ├── metrics_retrieval.py
│       ├── metrics_generation.py
│       ├── judge.py             # LLM-as-judge
│       └── run.py               # CLI do harness
├── eval/
│   ├── datasets/golden.jsonl
│   ├── configs/*.yaml           # uma config por experimento
│   └── results/                 # saídas (JSON + .md), versionadas
├── data/corpus/                 # PDFs de demo (ou script de download)
├── scripts/                     # download_corpus.py, seed.py…
├── tests/
└── docs/
```

## 4. Modelo de dados

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE documents (
    id          UUID PRIMARY KEY,
    filename    TEXT NOT NULL,
    sha256      CHAR(64) NOT NULL UNIQUE,      -- deduplicação (RF02)
    title       TEXT,
    num_pages   INT,
    status      TEXT NOT NULL,                 -- pending | processing | ready | failed
    error       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE chunks (
    id                 UUID PRIMARY KEY,
    document_id        UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunking_strategy  TEXT NOT NULL,          -- ex.: 'fixed_512_64', 'structure'
    chunk_index        INT  NOT NULL,
    content            TEXT NOT NULL,
    page_start         INT  NOT NULL,
    page_end           INT  NOT NULL,
    char_start         INT  NOT NULL,          -- offset no texto completo do documento
    char_end           INT  NOT NULL,
    token_count        INT,
    embedding          vector(768),            -- dimensão depende do modelo (SPEC D2)
    tsv                tsvector GENERATED ALWAYS AS (to_tsvector('portuguese', content)) STORED,
    metadata           JSONB NOT NULL DEFAULT '{}',
    UNIQUE (document_id, chunking_strategy, chunk_index)
);

CREATE INDEX chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX chunks_tsv_gin        ON chunks USING gin (tsv);
CREATE INDEX chunks_strategy_idx   ON chunks (chunking_strategy);

CREATE TABLE query_logs (                      -- observabilidade (RF18)
    id             UUID PRIMARY KEY,
    question       TEXT NOT NULL,
    config         JSONB NOT NULL,              -- estratégia, top_k, modelos
    retrieved_ids  UUID[] NOT NULL,
    answer         JSONB,
    latency_ms     JSONB NOT NULL,              -- {"retrieval": .., "rerank": .., "llm": ..}
    tokens         JSONB,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**Decisões e armadilhas:**
- **Várias estratégias de chunking convivem na mesma tabela**, separadas por `chunking_strategy`. Toda consulta filtra por ela.
- **Offsets de caractere** (`char_start/char_end`) são a ponte entre a anotação do golden set e os chunks — é o que torna a avaliação independente da estratégia de chunking (EVALUATION §3).
- **Dimensão do vetor é fixa por coluna.** Comparar modelos de embedding diferentes exige outra coluna/tabela — fora do MVP; registrar em ADR se for feito.
- **Índice HNSW + filtro** pode devolver menos de `k` resultados. Com corpus de demo (milhares de chunks) busca exata é rápida o suficiente; se precisar, usar índices parciais por estratégia ou as varreduras iterativas do pgvector ≥ 0.8.
- **`ts_rank_cd` não é BM25.** É um baseline lexical honesto; BM25 de verdade é decisão D4 da SPEC.

## 5. Ingestão

### Parser
Entrada: bytes do PDF. Saída: lista de páginas `(page_number, text, char_start, char_end)` sobre o **texto completo concatenado** do documento. PDFs sem camada de texto → status `failed` com motivo claro (sem OCR, ver SPEC §3).

### Estratégias de chunking

| Nome | Como funciona | Hipótese |
|------|---------------|----------|
| `fixed_<size>_<overlap>` | janelas de N tokens com sobreposição | baseline simples |
| `structure` | quebra por títulos/seções/parágrafos, junta pedaços pequenos até um teto de tokens | preserva contexto semântico, melhora resposta |
| (opcional) `semantic` | quebra quando a similaridade entre sentenças vizinhas cai | só se sobrar tempo |

Todo chunk guarda página inicial/final e offsets. Chunk que atravessa página tem `page_start ≠ page_end`.

### Embeddings
Interface:
```python
class Embedder(Protocol):
    dimension: int
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...
```
Separar `embed_documents` de `embed_query` não é capricho: modelos da família E5 exigem prefixos diferentes (`passage:` / `query:`), e esquecer isso derruba a qualidade silenciosamente.

## 6. Recuperação

```python
@dataclass
class RetrievedChunk:
    chunk_id: UUID
    document_id: UUID
    content: str
    page_start: int
    page_end: int
    score: float
    rank: int

class Retriever(Protocol):
    def retrieve(self, query: str, top_k: int, filters: RetrievalFilters) -> list[RetrievedChunk]: ...
```

| Estratégia | Implementação | Ponto forte esperado |
|------------|---------------|----------------------|
| `dense` | `ORDER BY embedding <=> :q_vec LIMIT k` (distância de cosseno) | perguntas parafraseadas, vocabulário diferente do texto |
| `lexical` | `websearch_to_tsquery('portuguese', :q)` + `ts_rank_cd` | termos exatos, códigos, números de artigo |
| `hybrid` | roda denso e lexical (ex.: top 50 cada) e funde com **RRF**: `score = Σ 1/(60 + rank)` | robustez nos dois tipos |
| `hybrid_rerank` | `hybrid` com top 50 → cross-encoder reordena → top k | precisão no topo do ranking |

O reranker é um *decorator*: `RerankRetriever(base=HybridRetriever(...))`. Assim dá para testar `dense_rerank` também sem código novo.

Extensões possíveis depois do M5 (só se a avaliação justificar): reescrita de consulta, HyDE, multi-query.

## 7. Geração e citações

### Contrato de saída do LLM (saída estruturada, validada por Pydantic)

```json
{
  "answerable": true,
  "answer": "O prazo é de 15 dias [S2], prorrogável uma vez [S3].",
  "claims": [
    {"text": "O prazo é de 15 dias", "source_ids": ["S2"], "quote": "no prazo de até 15 (quinze) dias"},
    {"text": "prorrogável uma vez", "source_ids": ["S3"], "quote": "podendo ser prorrogado uma única vez"}
  ]
}
```

O prompt apresenta o contexto como blocos numerados `[S1] … [Sk]`, com documento e página, e instrui: usar só o contexto; toda afirmação cita ≥ 1 fonte; `quote` é cópia literal curta; se não houver evidência, `answerable: false`.

### Validação (`citations.py`) — o coração do diferencial
1. Todo `source_id` existe no contexto enviado.
2. Todo `quote` existe no chunk citado — comparação após normalizar espaços e hifenização de quebra de linha; tolerância fuzzy pequena e **registrada**.
3. Cada citação válida é mapeada para `documento + página + offset`, usando o offset do `quote` dentro do chunk.
4. Falhou? A citação volta marcada como `verified: false` (nunca é exibida como válida). Opcional: uma nova tentativa com o erro no prompt.

### Recusa
Recusa se: (a) o melhor score da recuperação fica abaixo de um limiar **calibrado no split dev**, ou (b) o LLM retorna `answerable: false`, ou (c) nenhuma citação sobrevive à validação.

```python
class LLMClient(Protocol):
    def generate_structured(self, messages: list[Message], schema: type[BaseModel]) -> GenerationResult: ...
    # GenerationResult inclui o objeto validado + tokens de entrada/saída + latência
```

## 8. API

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/health` | status da API e do banco |
| `POST` | `/documents` | upload multipart de PDF → `202` + `{id, status}` |
| `GET` | `/documents` | lista documentos |
| `GET` | `/documents/{id}` | detalhes + status de ingestão |
| `DELETE` | `/documents/{id}` | remove documento e chunks |
| `POST` | `/search` | só recuperação (debug, RF09) |
| `POST` | `/query` | recuperação + geração + citações |

Exemplo `POST /query`:
```json
// request
{"question": "Qual o prazo para resposta ao titular?", "strategy": "hybrid_rerank", "top_k": 5, "document_ids": null}

// response
{
  "answerable": true,
  "answer": "O prazo é de 15 dias [1].",
  "citations": [
    {"id": 1, "document": "lgpd.pdf", "page": 12, "quote": "no prazo de até 15 (quinze) dias", "chunk_id": "…", "verified": true}
  ],
  "retrieval": {"strategy": "hybrid_rerank", "chunking": "structure", "chunks": [{"chunk_id": "…", "score": 0.91, "page": 12}]},
  "usage": {"latency_ms": {"retrieval": 42, "rerank": 180, "llm": 2100}, "tokens": {"input": 1830, "output": 96}}
}
```
Erros seguem formato único: `{"error": {"code": "...", "message": "..."}}`.

Ingestão no MVP pode ser síncrona dentro de `BackgroundTasks` do FastAPI; fila de verdade (Celery/RQ) só se virar gargalo.

## 9. Configuração (`.env`)

| Variável | Exemplo | Uso |
|----------|---------|-----|
| `DATABASE_URL` | `postgresql+psycopg://documind:documind@localhost:5432/documind` | conexão |
| `EMBEDDING_PROVIDER` / `EMBEDDING_MODEL` | `local` / `intfloat/multilingual-e5-base` | embeddings |
| `EMBEDDING_DIM` | `768` | precisa bater com a coluna |
| `LLM_PROVIDER` / `LLM_MODEL` | `gemini` / *(modelo da família Flash vigente)* | geração |
| `JUDGE_MODEL` | *(modelo da família Pro vigente)* | LLM-juiz da avaliação |
| `GEMINI_API_KEY` | — | chave do Google AI Studio |
| `LLM_CACHE_DIR` | `.cache/llm` | cache de respostas na avaliação |
| `RERANKER_MODEL` | `BAAI/bge-reranker-v2-m3` | rerank |
| `DEFAULT_STRATEGY` / `DEFAULT_CHUNKING` / `DEFAULT_TOP_K` | `hybrid_rerank` / `structure` / `5` | padrões |
| `REFUSAL_SCORE_THRESHOLD` | calibrado no dev | recusa |

## 10. Testes

- **Unitários:** chunkers (offsets corretos, páginas corretas, sem perder texto), RRF, validação de citações (casos com quote inexistente, espaços quebrados, hifenização), métricas de avaliação (com exemplos calculados à mão).
- **Integração:** ingestão + busca contra Postgres real em container (pytest + docker compose); LLM substituído por um *fake* determinístico.
- Testes **nunca** chamam API paga.
