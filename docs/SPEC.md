# DocuMind — Especificação do Produto

> Documento vivo. Mudanças de escopo entram aqui primeiro, código depois.
> Versão 0.1 — out/2026

## 1. Problema

Conectar um PDF a um chatbot é trivial. O difícil é responder três perguntas que quase nenhum projeto de "RAG" responde:

1. **A resposta está certa?** — e como eu sei, sem ler o documento inteiro?
2. **De onde ela veio?** — dá pra apontar o trecho exato, com documento e página?
3. **Essa forma de recuperar documentos é melhor que outra?** — com número, não com achismo.

O DocuMind é uma aplicação de perguntas e respostas sobre documentos técnicos (PDFs, manuais) que responde em linguagem natural **citando trechos verificáveis**, e que vem com um **harness de avaliação** para comparar estratégias de chunking e recuperação de forma reprodutível.

## 2. Objetivos

| # | Objetivo | Como sei que cumpri |
|---|----------|---------------------|
| O1 | Responder perguntas sobre documentos ingeridos, em PT-BR | Endpoint `/query` funcionando ponta a ponta |
| O2 | Toda afirmação da resposta aponta para um trecho real do documento | Citação traz doc + página + citação literal, validada por código |
| O3 | Recusar quando os documentos não têm a resposta | Taxa de recusa correta medida em perguntas sem resposta |
| O4 | Comparar ≥ 4 estratégias de recuperação e ≥ 2 de chunking | Tabela de resultados gerada pelo harness, no README |
| O5 | Medir qualidade de recuperação **e** de geração separadamente | Métricas de EVALUATION.md implementadas e reportadas |
| O6 | Ser reprodutível por qualquer pessoa | `docker compose up` + `make eval` reproduzem os números |

### Objetivo de portfólio (meta)

Demonstrar para recrutadores competências de **AI Engineer**: desenho de pipeline RAG sem framework "mágico", banco vetorial em produção (pgvector), API bem definida, avaliação de LLM com rigor (baseline, split dev/test, juiz calibrado) e documentação de decisões.

## 3. Não-objetivos (fora do escopo, de propósito)

- Autenticação, multiusuário, multi-tenant.
- OCR de PDF escaneado (só PDFs com camada de texto no MVP).
- Fine-tuning de modelos.
- Frontend elaborado — no máximo uma UI de demonstração simples.
- Uso de LangChain/LlamaIndex no núcleo (ver [ADR 0002](adr/0002-nucleo-sem-framework-rag.md)).
- Deploy em nuvem com alta disponibilidade (deploy de demo é opcional, no fim).
- Chat com memória de múltiplos turnos (cada pergunta é independente no MVP).

## 4. Usuário e casos de uso

**Usuário-alvo:** alguém que precisa consultar documentação técnica longa (manuais, normas, leis, documentação de sistemas) e quer resposta rápida **com a fonte** para conferir.

| ID | Caso de uso |
|----|-------------|
| UC1 | Enviar um ou mais PDFs para a base |
| UC2 | Listar e remover documentos |
| UC3 | Fazer uma pergunta e receber resposta com citações (doc, página, trecho literal) |
| UC4 | Restringir a pergunta a documentos específicos |
| UC5 | Escolher a estratégia de recuperação na requisição (para comparar/demonstrar) |
| UC6 | Ver só o resultado da recuperação, sem gerar resposta (debug) |
| UC7 | Rodar a avaliação completa e obter um relatório comparativo |

## 5. Requisitos funcionais

### Ingestão
- **RF01** Aceitar upload de PDF via API. Rejeitar arquivo que não é PDF ou acima de 50 MB.
- **RF02** Deduplicar por hash SHA-256 do arquivo (mesmo arquivo = mesmo documento).
- **RF03** Extrair texto **preservando número da página e offsets de caractere** de cada trecho.
- **RF04** Dividir em chunks com pelo menos duas estratégias configuráveis (ver ARCHITECTURE §5).
- **RF05** Gerar embeddings e persistir chunks + vetores no PostgreSQL/pgvector.
- **RF06** Expor status da ingestão (`pending`, `processing`, `ready`, `failed` + motivo).

### Recuperação
- **RF07** Implementar as estratégias: denso, lexical, híbrido (RRF) e híbrido + reranking.
- **RF08** Estratégia, `top_k` e filtro por documento selecionáveis por requisição; padrão definido em config.
- **RF09** Endpoint de recuperação pura (sem LLM) retornando chunks e scores.

### Geração e citações
- **RF10** Gerar resposta em PT-BR usando **apenas** o contexto recuperado.
- **RF11** Cada afirmação da resposta referencia ≥ 1 fonte e traz uma citação literal curta.
- **RF12** Validar por código que cada citação literal **existe** no chunk citado; citações inválidas são marcadas (e não exibidas como válidas).
- **RF13** Recusar com mensagem padrão quando não houver evidência suficiente.
- **RF14** O provedor de LLM e de embeddings é trocável via configuração, sem mudar código de domínio.

### Avaliação
- **RF15** Dataset anotado versionado no repositório, com split dev/test.
- **RF16** Comando único que roda uma configuração (ou uma matriz) e salva resultados em JSON + tabela Markdown.
- **RF17** Métricas de recuperação e de geração conforme [EVALUATION.md](EVALUATION.md).

### Observabilidade
- **RF18** Registrar cada consulta: pergunta, estratégia, ids recuperados, latência por etapa, tokens usados.

## 6. Requisitos não funcionais

- **RNF01 Reprodutibilidade:** `docker compose up` sobe banco + API; versões de dependências travadas (`uv.lock`); resultados de avaliação registram config completa e commit.
- **RNF02 Custo:** custo zero ou próximo de zero: embeddings e reranker locais, Gemini no tier gratuito. O pipeline de avaliação respeita limites de requisição (retry com backoff) e guarda em cache as respostas do LLM para não repetir chamadas.
- **RNF03 Qualidade de código:** type hints, `ruff` sem erros, testes com `pytest`; CI no GitHub Actions rodando lint + testes.
- **RNF04 Latência (referência, não meta rígida):** recuperação < 500 ms em corpus de demo; resposta completa depende do LLM e é medida, não prometida.
- **RNF05 Segurança básica:** segredos só em `.env` (nunca commitado); `.env.example` documenta tudo.
- **RNF06 Documentação:** toda decisão técnica relevante vira um ADR em `docs/adr/`.

## 7. Corpus de demonstração

Requisitos do corpus:
- 5–15 PDFs técnicos **em português**, com texto selecionável.
- **Públicos e redistribuíveis** (ou baixados por script, sem commitar o PDF).
- Variedade: texto corrido, tabelas, listas numeradas, termos técnicos/códigos.

Candidatos (decidir no M4): textos de leis federais (ex.: LGPD — texto de lei não tem proteção de direito autoral no Brasil), manuais e guias públicos do gov.br, documentação de software open source com licença permissiva.

## 8. Critérios de sucesso

Metas numéricas **não** são definidas antes do baseline — isso seria chute. O processo é:

1. Medir baseline (denso + chunking fixo) no split **dev**.
2. Definir metas relativas ao baseline (ex.: "híbrido + rerank melhora Recall@5 em ≥ X p.p.").
3. Reportar os números finais **uma única vez** no split **test**.

Critérios qualitativos fixos:
- 100% das citações exibidas como válidas passam na verificação literal (RF12).
- README mostra a tabela comparativa e explica **por que** cada estratégia ganha ou perde.

## 9. Decisões em aberto

| # | Decisão | Opções | Quando decidir |
|---|---------|--------|----------------|
| ~~D1~~ | ~~LLM padrão~~ | **Decidido: Gemini via API** ([ADR 0003](adr/0003-gemini-como-llm.md)) | — |
| D2 | Modelo de embeddings | `multilingual-e5` (base/large) × `bge-m3` × API | M1 |
| D3 | Corpus final | ver §7 | M4 |
| D4 | Lexical: FTS do Postgres × BM25 real (`pg_search`/ParadeDB ou `rank_bm25`) | começar com FTS | M5 |
| D5 | UI de demo | Streamlit × página HTML simples servida pelo FastAPI | M7 |

## 10. Glossário

- **Chunk:** pedaço de texto de um documento, unidade de recuperação.
- **Denso:** busca por similaridade de embeddings (semântica).
- **Lexical:** busca por termos (full-text / BM25).
- **RRF (Reciprocal Rank Fusion):** combina rankings somando `1/(k + posição)`.
- **Reranker (cross-encoder):** modelo que reordena candidatos lendo pergunta + chunk juntos.
- **Faithfulness:** quanto da resposta é sustentado pelo contexto recuperado.
- **Golden set:** dataset de perguntas com resposta e evidência anotadas à mão.
