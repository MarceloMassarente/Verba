# 📊 Resumo Rápido: Verba vs RAG 2.0

## ✅ O Que o Verba JÁ Faz (Similar ao RAG 2.0)

| Feature | Status | Implementação |
|---------|--------|---------------|
| **Query Rewrite** | ✅ Parcial | `QueryRewriterPlugin` + `QueryBuilderPlugin` - usa LLM para expandir queries |
| **Decomposição** | ✅ Parcial | `Two-Phase Search` - busca em duas fases (documentos → chunks) |
| **Query Expansion** | ✅ Sim | Gera múltiplas variações da query |
| **Reranking** | ✅ Sim | `CrossEncoderRanker` para melhorar ordenação |
| **Hybrid Search** | ✅ Sim | Combina BM25 + Vector Search com alpha dinâmico |
| **Entity-Aware** | ✅ Sim | Filtra por entidades antes da busca semântica |

## ❌ O Que o Verba NÃO Faz (Gaps do RAG 2.0)

| Feature | Gap | Impacto |
|---------|-----|---------|
| **Treinamento End-to-End** | ❌ Não há | Retriever não aprende a servir gerador específico |
| **Busca Iterativa** | ❌ Não há | Não busca durante geração (apenas antes) |
| **Adaptação Vetorial** | ❌ Não há | Query rewrite é linguístico, não vetorial |
| **Token `<SEARCH>`** | ❌ Não há | Modelo não decide quando buscar mais dados |
| **Fine-tuning RAG** | ❌ Não há | Modelos genéricos, não fine-tunados para RAG |

## 🎯 Comparação Direta

### Query Rewrite

**RAG 2.0:** Adaptação vetorial no espaço latente (treinada)
```
Query → Encoder Vetorial (treinado) → Vetor que "atrai" documentos corretos
```

**Verba:** Reescrita textual via LLM (prompt-based)
```
Query → LLM (prompt) → Query expandida → Busca
```

### Decomposição

**RAG 2.0:** Iterativa durante geração
```
Gerar → [Entropia alta] → <SEARCH> → Buscar → Continuar gerando
```

**Verba:** Estática antes da geração
```
Query → Two-Phase Search → Context → Gerar (sem interrupção)
```

### Treinamento

**RAG 2.0:** End-to-end (RA-DIT)
```
Loss = -log P(resposta | query, Retrieve(query))
Gradientes: Gerador → Retriever
```

**Verba:** Sem treinamento
```
Retriever (frozen) + Gerador (frozen) = Sem aprendizado conjunto
```

## 📈 Nível de Implementação

```
RAG Tradicional  ████░░░░░░ 40%
Verba (Atual)    ████████░░ 80%  ← Você está aqui
RAG 2.0          ██████████ 100%
```

**Conclusão:** Verba está em **~80% do caminho** para RAG 2.0. Falta principalmente:
1. Treinamento end-to-end
2. Busca iterativa durante geração

---

📄 **Documento Completo:** `COMPARACAO_VERBA_VS_RAG2_CONTEXTUAL.md`



