# 0003 — Gemini como LLM de geração e de avaliação

- **Status:** Aceito
- **Data:** 2026-10-09

## Contexto
O LLM precisa: responder em português, devolver saída estruturada (JSON validado por schema) com afirmações, fontes e citações literais, e ser barato o bastante para rodar a avaliação várias vezes. Também precisamos de um LLM-juiz para a avaliação de geração.

## Opções consideradas
1. **LLM local (Ollama)** — sem custo nem limite de requisição; modelos pequenos erram mais em JSON estruturado e em português, e a máquina precisa de GPU/RAM.
2. **Outras APIs (Claude, OpenAI)** — boa qualidade; sem tier gratuito equivalente para uso contínuo.
3. **Gemini via API** — saída estruturada nativa por schema, bom português, tier gratuito; o autor já tem familiaridade com a API.

## Decisão
Gemini via SDK `google-genai`: um modelo da família Flash para geração e um da família Pro como juiz. Os nomes exatos dos modelos ficam no `.env`, não no código.

## Consequências
- O `LLMClient` continua sendo uma interface: trocar de provedor depois é implementar um novo cliente, sem mexer no resto.
- O tier gratuito tem limite de requisições: o cliente precisa de retry com backoff, e a avaliação precisa de cache de respostas.
- Gerador e juiz são da mesma família, então há risco de viés do juiz a favor do gerador. A calibração manual (EVALUATION §5) mitiga isso e o problema é citado como limitação.
- Modelos e cotas do Gemini mudam com o tempo: registrar no resultado de cada avaliação o nome exato do modelo usado.
