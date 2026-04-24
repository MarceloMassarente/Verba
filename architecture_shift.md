# Architecture Shift Proposal — Verba para Atas de Conselho

## Avaliação rápida das sugestões

As três sugestões fazem **total sentido técnico** para um pivot para governança corporativa:

1. **Parser estrutural antes do chunking** para preservar relação `Pauta -> Deliberação -> Votação`.
2. **Extração estrita de entidades jurídicas** para consultas auditáveis.
3. **Prompt de modo auditor** para reduzir inferência e aumentar literalidade.

A stack atual (Weaviate + multi-vector + filas) já suporta o volume e a recuperação; o gap principal é na **ingestão semântica jurídica** e na **política de resposta**.

---

## O que vale mudar agora (baixo risco / alto impacto)

### 1) Trocar chunking por tamanho puro para chunking por pauta

**Objetivo:** impedir separação de título e decisão.

Recomendação imediata:
- Adicionar um estágio de segmentação por headers típicos de atas:
  - `Pauta\s+\d+`
  - `Deliberação`
  - `Votação`
  - `Conselheiro(a)`
  - `Resultado`
- Cada chunk deve herdar `meta.section_title`, `meta.pauta_id`, `meta.section_path`.

### 2) Guard-rail de fronteira legal no chunker

**Objetivo:** nunca cortar no meio de bloco decisório.

Recomendação imediata:
- Se um chunk contiver marcador de decisão (`aprovado`, `rejeitado`, `abstenção`, `unanimidade`), expandir o chunk até o fim do bloco.
- Só permitir split em fronteiras "seguras" (quebra de pauta/seção).

### 3) Schema de entidades jurídicas versionado

**Objetivo:** consultas SQL/GraphQL auditáveis e estáveis.

Recomendação imediata:
- Persistir entidades normalizadas:
  - `meeting_date`
  - `agenda_item`
  - `decision_outcome`
  - `vote_type`
  - `board_member`
  - `dissenting_vote`
- Gravar `source_span_start/end` para rastreabilidade literal.

### 4) Prompt de resposta com contrato estrito

**Objetivo:** reduzir hallucination em ambiente jurídico.

Recomendação imediata:
- Modo "auditor" com regras:
  - Não inferir relação entre pautas.
  - Responder `Não consta` quando o dado não aparecer explicitamente.
  - Priorizar listas/tabulação sobre texto narrativo.
  - Sempre citar trecho-fonte.

---

## Plano em fases

### Fase 1 (1–2 sprints)
- Parser por pauta + metadados mínimos.
- Prompt auditor como feature flag (`governance_mode=true`).
- Testes com 20–30 atas reais anonimizadas.

### Fase 2
- NER jurídica com validação por regex + dicionário de cargos.
- Índice auxiliar para consultas por conselheiro/pauta/ano.

### Fase 3
- Score de confiança por decisão extraída.
- Painel de auditoria com trilha `pergunta -> chunk -> span`.

---

## Critério de sucesso

- **Recall de decisões por pauta** > 95%.
- **Erro de atribuição de voto** < 1%.
- **Taxa de "Não consta" correta** monitorada por amostragem jurídica.

---

## Resposta objetiva à pergunta

Sim — faz sentido alterar **agora** o fluxo de fatiamento de PDFs.

A mudança de maior ROI é: **segmentação estrutural por pauta + guard-rails de fronteira legal**, antes de qualquer investimento pesado em modelo novo. Isso preserva contexto decisório e melhora imediatamente a confiabilidade das respostas.
