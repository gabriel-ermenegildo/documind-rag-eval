# Architecture Decision Records (ADRs)

Cada decisão técnica relevante vira um arquivo curto aqui: `NNNN-titulo-em-kebab-case.md`.
Decisão relevante = difícil de reverter, afeta várias partes do código, ou alguém perguntaria "por que fizeram assim?" numa entrevista.

ADRs não são apagados. Se uma decisão mudar, crie um novo ADR e marque o antigo como `Substituído por NNNN`.

## Template

```markdown
# NNNN — Título

- **Status:** Proposto | Aceito | Substituído por NNNN
- **Data:** AAAA-MM-DD

## Contexto
Qual problema ou restrição forçou a decisão.

## Opções consideradas
1. Opção A — prós / contras
2. Opção B — prós / contras

## Decisão
O que foi escolhido, em uma frase.

## Consequências
O que fica mais fácil, o que fica mais difícil, o que precisa ser revisto se X mudar.
```

## Índice
- [0001 — pgvector como vector store](0001-pgvector-como-vector-store.md)
- [0002 — Núcleo sem framework de RAG](0002-nucleo-sem-framework-rag.md)
- [0003 — Gemini como LLM](0003-gemini-como-llm.md)
