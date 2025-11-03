# 🌐 Ingestor Universal A2 - ETL Automático

## 🎯 O que é?

Um **Reader único e universal** que:
- ✅ Aceita **qualquer formato** (PDF, DOCX, TXT, JSON, CSV, Excel, HTML)
- ✅ Aplica **ETL A2 automaticamente** em todos os documentos
- ✅ Usa **SpaCy para extrair entidades por chunk**
- ✅ Não precisa de flags ou conversões

---

## 🚀 Como Usar

### Passo 1: Escolher o Ingestor

Na UI do Verba → **Import Data** → Escolha:

**"Universal A2 (ETL Automático)"**

### Passo 2: Upload do Arquivo

Faça upload de **qualquer arquivo**:
- ✅ PDF (um ou múltiplos artigos)
- ✅ DOCX
- ✅ TXT
- ✅ JSON
- ✅ CSV
- ✅ Excel

### Passo 3: Configurar (Opcional)

- **Enable ETL**: Sempre ativo (recomendado manter)
- **Language Hint**: Idioma para NER (padrão: "pt")

### Passo 4: Importar

Clique em **Import** e o ETL executa automaticamente! 🎉

---

## 🔧 O que o ETL Faz Automaticamente?

Para **cada chunk** criado, o ETL:

1. **Extrai Entidades via SpaCy**:
   - Personagens (PERSON)
   - Organizações (ORG)
   - Localizações (GPE, LOC)
   - Outras entidades nomeadas

2. **Normaliza via Gazetteer**:
   - Converte aliases para entity_ids canônicos
   - Ex: "Brasil" → "Q155", "Brasil" → "Q155"

3. **Detecta Seções**:
   - Identifica títulos de seções
   - Calcula scope de entidades por seção
   - Adiciona metadados de seção

4. **Atualiza Weaviate**:
   - Adiciona `entities_local_ids` em cada Passage
   - Adiciona `section_entity_ids` por seção
   - Adiciona `section_title`, `section_first_para`
   - Atualiza `entities_all_ids` no Article

---

## 📊 Comparação com Outros Ingestores

| Ingestor | Formatos | ETL Automático | Quando Usar |
|----------|----------|----------------|-------------|
| **Universal A2** ✅ | Todos (PDF, DOCX, TXT, etc.) | ✅ Sim | **Sempre que quiser ETL** |
| Default | Todos | ❌ Não | Quando não precisa ETL |
| A2 URL Ingestor | URLs apenas | ✅ Sim | Para URLs web |
| A2 Results Ingestor | JSON específico | ✅ Sim | Para conteúdo pré-extraído |

---

## 💡 Exemplos de Uso

### Exemplo 1: PDF Único

```
1. Upload: artigo.pdf
2. Escolher: "Universal A2 (ETL Automático)"
3. Importar
4. ✅ ETL executa automaticamente em todos os chunks
```

### Exemplo 2: PDF com Múltiplos Artigos

```
1. Upload: revista.pdf (contém 3 artigos)
2. Escolher: "Universal A2 (ETL Automático)"
3. Importar
4. ✅ Cada artigo vira documento separado
5. ✅ ETL executa em todos os chunks de todos os artigos
```

### Exemplo 3: DOCX

```
1. Upload: documento.docx
2. Escolher: "Universal A2 (ETL Automático)"
3. Importar
4. ✅ ETL extrai entidades e seções automaticamente
```

---

## ⚙️ Configuração Avançada

### Desabilitar ETL (não recomendado)

Se você não quiser ETL para um documento específico:

1. Escolha outro Reader (ex: "Default")
2. Ou desative "Enable ETL" (mas ETL ainda pode executar no hook)

### Ajustar Idioma do NER

```python
# SpaCy suporta:
- pt_core_news_sm (Português - pequeno)
- pt_core_news_md (Português - médio)
- pt_core_news_lg (Português - grande)
- en_core_web_sm (Inglês)
```

Configure via variável de ambiente:
```bash
SPACY_MODEL=pt_core_news_sm
```

---

## 🔍 Como Funciona Internamente

```
1. Upload de arquivo
   ↓
2. Universal A2 Reader carrega via Default Reader
   ↓
3. Documento processado (chunking normal)
   ↓
4. Import no Weaviate
   ↓
5. Hook detecta documentos com enable_etl=True
   ↓
6. ETL executa em background:
   - Extrai entidades por chunk (SpaCy)
   - Normaliza via Gazetteer
   - Detecta seções
   - Atualiza metadados no Weaviate
   ↓
7. ✅ Documentos no Weaviate com metadados de entidades!
```

---

## 🎯 Vantagens do Ingestor Universal

### ✅ Simplicidade
- Um único ingestor para todos os formatos
- Não precisa converter ou preparar dados

### ✅ Automático
- ETL executa automaticamente
- Não precisa de flags ou configuração extra

### ✅ Completo
- Funciona com qualquer formato suportado pelo Verba
- Extração de entidades por chunk
- Detecção automática de seções

### ✅ Compatível
- Não modifica código core do Verba
- Funciona como plugin/hook

---

## ⚠️ Limitações

1. **Performance**: ETL adiciona processamento (~2-5s por documento)
2. **SpaCy**: Requer modelo instalado (padrão: `pt_core_news_sm`)
3. **Background**: ETL executa em background (não bloqueia import)

---

## 🔧 Instalação

O Universal A2 Reader já está incluído nas extensões. Certifique-se de que:

1. ✅ Extensões estão carregadas (ver logs do Railway)
2. ✅ SpaCy está instalado: `pip install spacy`
3. ✅ Modelo SpaCy está instalado: `python -m spacy download pt_core_news_sm`

---

## 📋 Checklist

- [ ] "Universal A2 (ETL Automático)" aparece no dropdown de Readers
- [ ] Upload de arquivo funciona (PDF, DOCX, etc.)
- [ ] Import executa sem erros
- [ ] ETL aplica metadados no Weaviate (verificar após import)

---

## 🚀 Próximos Passos

Após importar com Universal A2:

1. ✅ Use **Entity-Aware Retriever** para buscar por entidades
2. ✅ Filtre por seções específicas
3. ✅ Combine busca por conteúdo + entidades

---

**Agora você tem um ingestor único que processa qualquer formato e aplica ETL automaticamente!** 🎉

