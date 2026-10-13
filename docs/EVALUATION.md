# DocuMind — Plano de Avaliação

> Esta é a parte que separa o DocuMind de "mais um chatbot de PDF". Se faltar tempo, corte feature — não corte avaliação.

## 1. Princípios

1. **Baseline primeiro.** Nenhuma otimização antes de medir a configuração mais simples (`dense` + `fixed`).
2. **Recuperação e geração são medidas separadamente.** Resposta ruim pode ser culpa do retriever (não achou) ou do LLM (achou e ignorou). Sem separar, não dá para saber o que consertar.
3. **Split dev/test.** Toda calibração (limiar de recusa, `top_k`, prompt) é feita no **dev**. O **test** é rodado só para os números finais do README. Ajustar no test é *overfitting* no próprio benchmark.
4. **Dataset congelado.** Depois de criado, o golden set só muda por correção de erro de anotação — registrada no histórico do git com justificativa. Nunca para "melhorar o número".
5. **Tudo reprodutível.** Cada execução salva config completa, commit, modelos e semente.

## 2. Golden set

### Formato (`eval/datasets/golden.jsonl`, uma linha por pergunta)

```json
{
  "id": "q017",
  "split": "dev",
  "question": "Em quanto tempo o controlador deve responder ao titular?",
  "type": "paraphrase",
  "answerable": true,
  "reference_answer": "Em até 15 dias.",
  "evidence": [
    {"document": "lgpd.pdf", "page": 12, "text": "no prazo de até 15 (quinze) dias"}
  ]
}
```

- `evidence.text` é um **trecho literal** do PDF. Na hora de avaliar, o código localiza esse trecho no texto do documento e obtém os offsets — por isso a anotação vale para **qualquer** estratégia de chunking.
- Perguntas sem resposta têm `answerable: false` e `evidence: []`.

### Composição alvo (60–100 perguntas, ~70% dev / 30% test)

| Tipo | % aprox. | O que testa | Quem deve ir bem |
|------|----------|-------------|------------------|
| `factual` | 30% | fato direto, vocabulário parecido com o texto | todos |
| `paraphrase` | 20% | pergunta com palavras diferentes do texto | denso |
| `exact_term` | 15% | código, sigla, número de artigo, nome próprio | lexical |
| `multi_evidence` | 15% | resposta precisa de 2+ trechos | híbrido/rerank, chunk maior |
| `unanswerable` | 20% | assunto próximo, mas a resposta não está no corpus | testa recusa |

Esses tipos foram escolhidos de propósito para que **cada estratégia tenha onde ganhar e onde perder** — a análise por tipo é mais interessante que a média geral.

### Como construir
1. Ler os documentos e escrever perguntas **à mão** (pelo menos metade).
2. Opcional: gerar candidatas com LLM a partir de chunks e **revisar uma por uma** (descartar as triviais). Marcar no campo `"origin": "synthetic"` — perguntas sintéticas tendem a copiar o vocabulário do texto e favorecem busca lexical; isso precisa ser reportado.
3. Validar por script: todo `evidence.text` é encontrado no documento indicado.

## 3. Relevância (ponte entre anotação e chunks)

Um chunk recuperado é **relevante** para a pergunta se pertence ao mesmo documento **e** seu intervalo `[char_start, char_end)` se sobrepõe ao intervalo de algum trecho de evidência. Cada evidência conta como uma unidade a ser "coberta".

## 4. Métricas de recuperação (sem LLM — baratas, rodam a matriz inteira)

Calculadas só nas perguntas `answerable`, para k ∈ {1, 3, 5, 10}:

| Métrica | Definição |
|---------|-----------|
| **Hit@k** | fração das perguntas com ≥ 1 chunk relevante no top-k |
| **Recall@k** | média, por pergunta, de (evidências cobertas no top-k / total de evidências) |
| **MRR** | média de `1 / posição do primeiro chunk relevante` (0 se nenhum no top-10) |
| **nDCG@k** | opcional — penaliza relevante em posição baixa |
| **Latência** | p50 / p95 da recuperação |

Toda métrica é implementada à mão em `metrics_retrieval.py` e **testada com casos calculados no papel**. (Bibliotecas como RAGAS podem ser usadas como comparação, não como substituto — o ponto é mostrar que você entende a métrica.)

## 5. Métricas de geração (com LLM — caras, só nas melhores configs)

| Métrica | Como mede | Tipo |
|---------|-----------|------|
| **Quote validity** | % de `quote` que existem literalmente no chunk citado | determinística |
| **Citation coverage** | % de afirmações (`claims`) com ≥ 1 citação válida | determinística |
| **Faithfulness** | % de afirmações sustentadas pelos chunks citados | LLM-juiz |
| **Correctness** | resposta equivale à `reference_answer`? (0 / 0.5 / 1) | LLM-juiz |
| **Refusal precision / recall** | nas `unanswerable`: recusou? nas `answerable`: deixou de recusar à toa? | determinística |
| **Custo e latência** | tokens de entrada/saída e latência do LLM, p50/p95 | determinística |

### LLM-as-judge com calibração
- Rubrica escrita em `eval/judge_rubric.md`, com exemplos de nota.
- Juiz usa temperatura 0 e um modelo **mais forte** que o gerador (gerador Gemini Flash, juiz Gemini Pro). Como os dois são da mesma família, há risco de o juiz favorecer o estilo do gerador — por isso a calibração manual abaixo é obrigatória, e isso vai citado como limitação no README.
- Respostas do gerador e do juiz ficam em cache (chave = hash do prompt + modelo), para que rodar a avaliação de novo não gaste cota da API.
- **Calibração:** anotar à mão ~30 respostas, comparar com o juiz e reportar a concordância (% de acordo e kappa de Cohen). Se a concordância for baixa, ajustar a rubrica **no dev** antes de confiar no juiz.
- Reportar no README que parte das métricas usa juiz automático e qual foi a concordância medida.

## 6. Matriz de experimentos

**Fase A — recuperação (barata, matriz completa):**

| | `dense` | `lexical` | `hybrid` | `hybrid_rerank` |
|---|---|---|---|---|
| `fixed_512_64` | baseline | ✓ | ✓ | ✓ |
| `structure` | ✓ | ✓ | ✓ | ✓ |

= 8 configs × métricas de §4, quebradas por tipo de pergunta.

**Fase B — geração:** as 2–3 melhores configs da Fase A + o baseline, com as métricas de §5.

**Fase C (opcional):** variar `top_k` de contexto (3 × 5 × 8) na melhor config — mais contexto ajuda ou confunde o LLM?

## 7. Saídas e reprodutibilidade

Cada experimento é um YAML em `eval/configs/`:
```yaml
name: hybrid_rerank__structure
chunking: structure
strategy: hybrid_rerank
top_k: 5
candidates: 50
embedding_model: intfloat/multilingual-e5-base
reranker_model: BAAI/bge-reranker-v2-m3
llm: null          # null = só métricas de recuperação
split: dev
seed: 42
```

Comando: `make eval CONFIG=eval/configs/hybrid_rerank__structure.yaml` (ou `make eval-matrix`).

Saída em `eval/results/<data>_<nome>.json`: config completa, hash do commit, versão do dataset, métricas agregadas, métricas por tipo e resultado por pergunta (para análise de erros). Um script gera `eval/results/SUMMARY.md` com a tabela comparativa que vai para o README.

## 8. Análise de erros (o que mais impressiona em entrevista)

Para a melhor e a pior config, pegar ~10 falhas e classificar:
- não recuperou a evidência (problema de retrieval)
- recuperou mas fora do top-k enviado ao LLM
- recuperou e o LLM ignorou / alucinou
- recusou sem necessidade / respondeu quando devia recusar
- erro de anotação no dataset (corrigir e registrar)

Documentar em `docs/RESULTS.md` com exemplos concretos. Uma tabela com números + três parágrafos explicando **por que** os números são esses vale mais do que qualquer feature extra.

## 9. Armadilhas conhecidas

- Avaliar no mesmo split usado para ajustar → números inflados.
- Perguntas sintéticas copiando o texto → favorecem lexical injustamente.
- Juiz igual ao gerador → tende a aprovar as próprias respostas.
- Médias escondem tudo → sempre quebrar por tipo de pergunta.
- Dataset pequeno → diferenças de 1–2 p.p. podem ser ruído; mencionar isso ao comparar (opcional: intervalo de confiança por bootstrap).
