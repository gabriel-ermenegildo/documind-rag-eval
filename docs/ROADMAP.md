# DocuMind — Roadmap

> Um marco por vez. Cada marco termina com testes passando, docs atualizadas e um commit que funciona sozinho.

**Definição de pronto (vale para todo marco):**
- `make lint` e `make test` passando (e CI verde)
- Critérios de aceite do marco verificados
- README/docs atualizados se algo mudou
- Decisão técnica relevante registrada em `docs/adr/`
- Gabriel consegue explicar e justificar cada decisão

---

## M0 — Fundação
- [x] Projeto `uv` com `src/documind`, `pyproject.toml`, ruff e pytest configurados
- [x] `docker-compose.yml` com Postgres 16 + pgvector (imagem `pgvector/pgvector`)
- [x] `config.py` com pydantic-settings + `.env.example`
- [x] FastAPI com `GET /health` checando o banco
- [x] Alembic inicial com as tabelas de ARCHITECTURE §4
- [x] `Makefile` (`up`, `down`, `dev`, `test`, `lint`, `migrate`)
- [x] GitHub Actions: lint + testes

**Aceite:** `make up && make migrate && make dev` → `/health` retorna `{"status": "ok", "db": "ok"}`; CI verde.

## M1 — Ingestão
- [x] Parser PyMuPDF retornando páginas com offsets
- [x] `FixedSizeChunker` com overlap, preservando página e offsets
- [ ] `Embedder` local (decidir SPEC D2 → ADR)
- [ ] Pipeline parse → chunk → embed → save, com dedupe por SHA-256
- [ ] Rotas `POST/GET/DELETE /documents`
- [ ] Testes: offsets reconstroem o texto original; páginas corretas; PDF sem texto falha com mensagem clara

**Aceite:** subir 3 PDFs pela API e ver os chunks no banco com página certa.

## M2 — Recuperação densa
- [ ] `Retriever` Protocol + `DenseRetriever` (pgvector, cosseno)
- [ ] `POST /search`
- [ ] Teste de integração com Postgres real

**Aceite:** `/search` retorna chunks coerentes para 5 perguntas manuais.

## M3 — Geração com citações verificadas
- [ ] `LLMClient` Protocol + `GeminiClient` (saída estruturada, retry com backoff) + cliente *fake* para testes
- [ ] Prompt + schema de saída estruturada
- [ ] `citations.py`: validação literal de quotes + mapeamento para página
- [ ] Lógica de recusa (limiar provisório)
- [ ] `POST /query` + `query_logs`

**Aceite:** pergunta respondível → resposta com citações `verified: true`; pergunta fora do corpus → recusa.

## M4 — Golden set e harness de recuperação ⚠️ antes de otimizar qualquer coisa
- [ ] Escolher corpus final (SPEC D3) + `scripts/download_corpus.py`
- [ ] Golden set com 60–100 perguntas, tipos de EVALUATION §2, split dev/test
- [ ] Script que valida o dataset (toda evidência é encontrada no PDF)
- [ ] `relevance.py` + métricas Hit@k, Recall@k, MRR (testadas com casos à mão)
- [ ] CLI `make eval` com config YAML → JSON + `SUMMARY.md`
- [ ] **Medir o baseline** `dense` + `fixed_512_64` no dev

**Aceite:** número do baseline registrado em `eval/results/`.

## M5 — Estratégias de recuperação e chunking
- [ ] `LexicalRetriever` (FTS português)
- [ ] `HybridRetriever` com RRF (teste unitário da fusão)
- [ ] `RerankRetriever` (cross-encoder)
- [ ] `StructureAwareChunker` + reingestão com a segunda estratégia
- [ ] Rodar a matriz da Fase A (8 configs) no dev
- [ ] Análise por tipo de pergunta

**Aceite:** tabela comparativa com as 8 configs, quebrada por tipo.

## M6 — Avaliação de geração
- [ ] Métricas determinísticas (quote validity, citation coverage, recusa)
- [ ] LLM-juiz com rubrica (`faithfulness`, `correctness`)
- [ ] Calibração do juiz com ~30 anotações manuais (concordância reportada)
- [ ] Calibrar limiar de recusa no dev
- [ ] Rodar Fase B
- [ ] **Rodar test uma única vez** nas configs finais

**Aceite:** `docs/RESULTS.md` com tabelas finais (test) e análise de erros.

## M7 — Polimento para portfólio
- [ ] UI de demo simples (SPEC D5): pergunta → resposta com citações clicáveis mostrando o trecho
- [ ] README final: GIF da demo, diagrama, tabela de resultados, "como rodar em 3 comandos", decisões e limitações
- [ ] Dockerfile da API e `docker compose up` subindo tudo
- [ ] Revisão geral: código morto, TODOs, docstrings
- [ ] Escolher a licença do repositório, compatível com a AGPL-3.0 do PyMuPDF
- [ ] (opcional) Deploy de demo

**Aceite:** alguém clona o repo, roda 3 comandos e reproduz a demo e a tabela.

---

## Ideias para depois (não fazer antes do M7)
- Reescrita de consulta / HyDE / multi-query (com avaliação)
- Comparar 2 modelos de embedding
- BM25 de verdade (SPEC D4)
- OCR para PDFs escaneados
- Chat com histórico
- Streaming da resposta
