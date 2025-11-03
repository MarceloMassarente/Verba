# 🔄 Análise: Ordem do Fluxo ETL - Chunking vs Embedding

## ❓ Pergunta Chave

**Qual ordem é melhor?**
1. **Fluxo Atual**: Chunking → Embedding → ETL (adiciona metadados)
2. **Fluxo Alternativo**: SpaCy/ETL → Chunking Inteligente → Embedding

---

## 📊 Comparação dos Fluxos

### **Fluxo Atual** (Implementado)

```
1. Upload PDF
   ↓
2. Chunking Simples (sentenças/tokens)
   - Divide por ~200-500 palavras
   - Sem conhecimento de entidades
   ↓
3. Embedding (cada chunk)
   - Vetoriza chunks genéricos
   ↓
4. Import no Weaviate
   ↓
5. ETL (background)
   - Extrai entidades de cada chunk
   - Adiciona metadados (entities_local_ids, section_*)
   - Atualiza chunks já armazenados
```

**Vantagens:**
- ✅ Rápido (chunking simples é leve)
- ✅ Embedding não depende de ETL (não bloqueia)
- ✅ ETL pode falhar sem quebrar import
- ✅ Compatível com fluxo padrão do Verba

**Desvantagens:**
- ❌ Chunks podem cortar entidades/seções no meio
- ❌ Embedding não captura contexto semântico de entidades
- ❌ Metadados adicionados depois (não usados no embedding)
- ❌ Possível contaminação entre empresas em chunks mistos

---

### **Fluxo Alternativo 1**: Chunking Baseado em Entidades

```
1. Upload PDF
   ↓
2. SpaCy (análise completa do documento)
   - Extrai entidades
   - Detecta seções
   - Identifica estrutura
   ↓
3. Chunking Inteligente
   - Agrupa por entidade principal
   - Respeita limites de seção
   - Chunks semanticamente coerentes
   ↓
4. Embedding (cada chunk)
   - Vetoriza chunks já enriquecidos
   ↓
5. Import no Weaviate
   - Já com metadados de entidades
```

**Vantagens:**
- ✅ Chunks mais semânticos (agrupados por entidade)
- ✅ Embedding captura melhor contexto
- ✅ Menos contaminação entre empresas
- ✅ Metadados disponíveis desde o início

**Desvantagens:**
- ❌ Mais lento (SpaCy processa documento completo)
- ❌ Chunking pode ser irregular (alguns chunks grandes)
- ❌ Mais complexo de implementar
- ❌ Quebra fluxo padrão do Verba (chunking é fase separada)

---

### **Fluxo Alternativo 2**: Chunking Baseado em Seções

```
1. Upload PDF
   ↓
2. Detecção de Seções (leve)
   - Identifica títulos/seções
   - Marca limites de seção
   ↓
3. Chunking por Seção
   - Divide respeitando limites de seção
   - Se seção muito grande, divide dentro da seção
   ↓
4. Embedding
   ↓
5. Import
   ↓
6. ETL (refinamento)
   - Extrai entidades finas
   - Atualiza metadados
```

**Vantagens:**
- ✅ Chunks respeitam estrutura natural (seções)
- ✅ Menos contaminação entre artigos/tópicos
- ✅ Balanceado: não muito lento, não muito genérico

**Desvantagens:**
- ❌ Ainda pode ter contaminação dentro de seções
- ❌ Requer detecção de seções confiável

---

## 🎯 Recomendação: Fluxo Híbrido

### **Melhor Abordagem** (Combina vantagens):

```
1. Upload PDF
   ↓
2. Detecção Leve de Seções (regex/heurística)
   - Identifica títulos/seções sem SpaCy pesado
   - Marca limites de seção
   ↓
3. Chunking Híbrido
   - Prioriza limites de seção
   - Se seção grande, divide respeitando parágrafos
   - Tamanho alvo: ~200-500 palavras
   ↓
4. Embedding (cada chunk)
   ↓
5. Import no Weaviate
   ↓
6. ETL Refinado (background)
   - SpaCy extrai entidades por chunk
   - Normaliza via Gazetteer
   - Refina section_entity_ids
   - Atualiza metadados
```

**Por que é melhor:**
- ✅ Balanceado: velocidade + qualidade
- ✅ Chunks respeitam estrutura (seções)
- ✅ Embedding captura melhor contexto
- ✅ ETL adiciona refinamento sem bloquear
- ✅ Compatível com arquitetura do Verba

---

## 🔧 Implementação Sugerida

### **Opção A: Chunker Customizado**

Criar um `EntityAwareChunker` que:
1. Detecta seções (regex simples)
2. Chunking respeitando seções
3. Se necessário, divide dentro da seção

```python
class EntityAwareChunker(Chunker):
    async def chunk(
        documents: List[Document],
        chunking_strategy: str = "section_aware",
        chunk_size: int = 300
    ) -> List[Document]:
        # 1. Detecta seções (regex)
        sections = detect_sections(document.content)
        
        # 2. Chunking por seção
        chunks = []
        for section in sections:
            if len(section.text) <= chunk_size:
                chunks.append(section)
            else:
                # Divide dentro da seção
                sub_chunks = split_by_paragraphs(section, chunk_size)
                chunks.extend(sub_chunks)
        
        return chunks
```

### **Opção B: Melhorar ETL Atual**

Manter chunking simples, mas melhorar ETL:
1. ETL analisa chunks adjacentes
2. Detecta quando entidade foi cortada
3. Adiciona metadados de continuidade

---

## 📊 Comparação de Resultados

### **Cenário**: PDF com 3 artigos sobre Apple, Microsoft, Google

**Fluxo Atual:**
```
Chunk 1: "Apple lança iPhone. Características incluem..."
Chunk 2: "...processador A17. Microsoft também anunciou..."  ← Contaminação!
Chunk 3: "...parceria com OpenAI. Google desenvolve IA..."
```

**Problema**: Chunk 2 mistura Apple e Microsoft!

**Fluxo Híbrido (Section-Aware):**
```
Chunk 1 (Seção Apple): "Apple lança iPhone. Características..."
Chunk 2 (Seção Apple): "...processador A17. Preço será..."
Chunk 3 (Seção Microsoft): "Microsoft anuncia parceria..."
Chunk 4 (Seção Google): "Google desenvolve IA..."
```

**Vantagem**: Cada chunk pertence a uma seção/artigo!

---

## 🚀 Próximos Passos

### **Implementação Imediata** (Mais Simples):

1. Criar `SectionAwareChunker` como plugin
2. Detecção de seções via regex/heurística
3. Chunking respeitando limites de seção

### **Implementação Avançada** (Mais Complexa):

1. Chunking baseado em entidades (requer SpaCy antes)
2. Re-agrupar chunks por entidade principal
3. Balanceamento de tamanho vs coerência semântica

---

## ✅ Conclusão

**Fluxo Atual é funcional, mas pode melhorar:**

**Curto Prazo:**
- ✅ Adicionar `SectionAwareChunker` (chunking respeita seções)
- ✅ Manter ETL como refinamento

**Longo Prazo:**
- ✅ Considerar chunking baseado em entidades
- ✅ Mas só se performance permitir (SpaCy é pesado)

**Recomendação Final:**
- **Fluxo Atual + SectionAwareChunker** = Melhor balance
- Mantém velocidade + Melhora qualidade

---

Quer que eu implemente o `SectionAwareChunker`? 🛠️

