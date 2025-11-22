# O Que Faz o Flag "Enable Query Rewriting"?

## 🎯 Resposta Direta

O flag **"Enable Query Rewriting"** controla apenas o **QueryRewriter** (fallback), **NÃO o QueryBuilder**.

**Fluxo real:**
1. **QueryBuilder** é sempre tentado primeiro (independente do flag)
2. Se QueryBuilder falhar, **então** verifica o flag
3. Se flag estiver ligado, usa **QueryRewriter** como fallback

---

## 🔍 Como Funciona no Código

### Fluxo Completo

```python
# verba_extensions/plugins/entity_aware_retriever.py (linha ~663)

# 0. QUERY BUILDING (antes de parsing)
rewritten_query = query
rewritten_alpha = alpha

# 1. TENTA QueryBuilder PRIMEIRO (SEMPRE, independente do flag)
try:
    from verba_extensions.plugins.query_builder import QueryBuilderPlugin
    builder = QueryBuilderPlugin(cache_ttl_seconds=cache_ttl)
    
    # Obtém schema e constrói query
    strategy = await builder.build_query(
        user_query=query,
        client=client,
        collection_name=collection_name,
        rag_config=rag_config
    )
    
    rewritten_query = strategy.get("semantic_query", query)
    # ✅ QueryBuilder funcionou!
    
except ImportError:
    # 2. FALLBACK: Se QueryBuilder não disponível, verifica flag
    if enable_query_rewriting:  # ← FLAG AQUI!
        try:
            from verba_extensions.plugins.query_rewriter import QueryRewriterPlugin
            rewriter = QueryRewriterPlugin(cache_ttl_seconds=cache_ttl)
            strategy = await rewriter.rewrite_query(query, use_cache=True)
            
            rewritten_query = strategy.get("semantic_query", query)
            # ✅ QueryRewriter funcionou (fallback)
            
except Exception as e:
    # 3. FALLBACK: Se QueryBuilder falhar com outro erro, também verifica flag
    if enable_query_rewriting:  # ← FLAG AQUI TAMBÉM!
        try:
            from verba_extensions.plugins.query_rewriter import QueryRewriterPlugin
            rewriter = QueryRewriterPlugin(cache_ttl_seconds=cache_ttl)
            strategy = await rewriter.rewrite_query(query, use_cache=True)
            rewritten_query = strategy.get("semantic_query", query)
```

---

## 📊 Tabela de Comportamento

| Flag "Enable Query Rewriting" | QueryBuilder | QueryRewriter |
|-------------------------------|--------------|--------------|
| **Ligado (True)** | ✅ Sempre tenta primeiro | ✅ Usado como fallback se QueryBuilder falhar |
| **Desligado (False)** | ✅ Sempre tenta primeiro | ❌ NÃO usado (mesmo se QueryBuilder falhar) |

---

## 🎯 O Que Isso Significa?

### Se Flag Estiver Ligado (True)

1. **QueryBuilder tenta primeiro** (sempre)
   - Se funcionar: usa QueryBuilder ✅
   - Se falhar: vai para passo 2

2. **QueryRewriter como fallback** (se flag ligado)
   - Se QueryBuilder falhar: usa QueryRewriter ✅
   - Se QueryRewriter também falhar: usa query original

### Se Flag Estiver Desligado (False)

1. **QueryBuilder tenta primeiro** (sempre)
   - Se funcionar: usa QueryBuilder ✅
   - Se falhar: vai para passo 2

2. **QueryRewriter NÃO é usado** (flag desligado)
   - Se QueryBuilder falhar: usa query original diretamente ❌
   - QueryRewriter é ignorado completamente

---

## ⚠️ Comportamento Atual (Pode Ser Confuso)

### Problema

O flag se chama **"Enable Query Rewriting"**, mas:
- ✅ Controla QueryRewriter (correto)
- ❌ NÃO controla QueryBuilder (QueryBuilder sempre tenta, independente do flag)

### Por Que É Assim?

1. **QueryBuilder é mais novo** - foi adicionado depois
2. **Flag é mais antigo** - foi criado para QueryRewriter
3. **Compatibilidade** - manter comportamento antigo funcionando

### Nome Mais Preciso Seria

- ❌ "Enable Query Rewriting" (atual - confuso)
- ✅ "Enable Query Rewriter Fallback" (mais claro)
- ✅ "Enable Query Rewriting (Fallback Only)" (mais descritivo)

---

## 🔧 Recomendações

### Para Usuários

1. **Deixe o flag ligado** (True):
   - Garante fallback se QueryBuilder falhar
   - Melhor experiência (sempre tenta melhorar query)

2. **Se QueryBuilder estiver funcionando**:
   - Flag não afeta nada (QueryBuilder sempre tenta primeiro)
   - Flag só importa se QueryBuilder falhar

3. **Se QueryBuilder não estiver disponível**:
   - Flag controla se QueryRewriter será usado
   - Se ligado: usa QueryRewriter
   - Se desligado: usa query original

### Para Desenvolvedores

**Melhorias possíveis:**
1. Renomear flag para "Enable Query Rewriter Fallback"
2. Adicionar flag separado "Enable Query Builder" (se quiser desabilitar)
3. Documentar melhor o comportamento

---

## 📋 Resumo

| Pergunta | Resposta |
|----------|----------|
| **Flag controla QueryBuilder?** | ❌ NÃO - QueryBuilder sempre tenta primeiro |
| **Flag controla QueryRewriter?** | ✅ SIM - Controla se QueryRewriter é usado como fallback |
| **O que acontece se flag ligado?** | QueryBuilder tenta primeiro, QueryRewriter como fallback |
| **O que acontece se flag desligado?** | QueryBuilder tenta primeiro, se falhar usa query original (sem QueryRewriter) |
| **Qual é melhor?** | Deixar ligado (garante fallback) |

---

## 🤔 Por Que Existe Esse Flag?

### História

1. **Flag foi criado ANTES do QueryBuilder existir**
   - Era para controlar o QueryRewriter (que era o único na época)
   - Usuários podiam ligar/desligar query rewriting

2. **QueryBuilder foi adicionado depois**
   - Melhoria que conhece schema
   - Foi adicionado SEM verificar o flag (sempre tenta primeiro)
   - Flag foi mantido por compatibilidade

3. **Resultado atual**
   - Flag só controla QueryRewriter (fallback)
   - QueryBuilder sempre tenta (independente do flag)

### Por Que Manter o Flag?

**Casos práticos onde você pode querer desabilitar:**

1. **QueryRewriter está causando problemas**
   - LLM retorna queries ruins
   - Quer apenas QueryBuilder (sem fallback)

2. **Não tem LLM configurado**
   - QueryRewriter precisa de LLM (Anthropic)
   - Se não tem LLM, QueryRewriter vai falhar mesmo
   - Desligar flag evita tentativas desnecessárias

3. **Performance**
   - QueryRewriter adiciona latência (chamada LLM)
   - Se QueryBuilder sempre funciona, não precisa de fallback
   - Desligar flag reduz tentativas desnecessárias

4. **Controle fino**
   - Quer apenas QueryBuilder (mais inteligente)
   - Não quer fallback para QueryRewriter (mais simples)

### Quando Faz Sentido Desligar?

✅ **Desligue o flag se:**
- QueryBuilder sempre funciona (não precisa de fallback)
- Não tem LLM configurado (QueryRewriter não vai funcionar)
- Quer apenas QueryBuilder (mais inteligente)
- Performance é crítica (evitar chamadas LLM desnecessárias)

✅ **Deixe ligado se:**
- Quer fallback robusto (se QueryBuilder falhar, tenta QueryRewriter)
- Tem LLM configurado
- Quer máxima compatibilidade

---

## 🎯 Conclusão

O flag **"Enable Query Rewriting"** controla apenas o **QueryRewriter** (fallback).

**QueryBuilder sempre tenta primeiro**, independente do flag.

**Flag só importa se QueryBuilder falhar** - então decide se usa QueryRewriter ou query original.

**Recomendação**: 
- **Deixe ligado** se quer fallback robusto (padrão recomendado)
- **Desligue** se QueryBuilder sempre funciona e não precisa de fallback

