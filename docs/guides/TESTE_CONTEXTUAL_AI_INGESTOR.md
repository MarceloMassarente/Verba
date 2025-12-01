# Guia de Teste: Contextual.ai Ingestor Integrado

## 🧪 Teste Rápido

### 1. Configurar API Key

**Opção A: Variável de ambiente**
```bash
# Windows PowerShell
$env:CONTEXTUAL_AI_API_KEY="He5TJQTp3Xg_P4gvMoUtDBF727m3rDNIqOue0IuqRCvdExkU4"

# Linux/Mac
export CONTEXTUAL_AI_API_KEY="He5TJQTp3Xg_P4gvMoUtDBF727m3rDNIqOue0IuqRCvdExkU4"
```

**Opção B: Arquivo .env**
```bash
# Adicione ao arquivo .env na raiz do projeto
CONTEXTUAL_AI_API_KEY=He5TJQTp3Xg_P4gvMoUtDBF727m3rDNIqOue0IuqRCvdExkU4
```

### 2. Testar via Script

```bash
# 1. Coloque um arquivo de teste em test_output/
# Exemplo: test_output/test_file.pdf

# 2. Execute o script de teste
python scripts/tests/test_contextual_ai_ingestor.py
```

### 3. Testar via Verba (Recomendado)

1. **Inicie o Verba:**
   ```bash
   verba start
   ```

2. **Acesse a interface:**
   - Vá em `http://localhost:8000`
   - Clique em "Import Data"

3. **Selecione o Ingestor:**
   - Escolha **"Contextual.ai Ingestor (Otimizado)"** como Reader
   - Configure parâmetros (opcional):
     - Parse Mode: `standard`
     - Figure Caption Mode: `detailed`
     - Enable Document Hierarchy: `true`

4. **Faça upload:**
   - Selecione um arquivo PDF, DOCX ou PPTX
   - Clique em "Import"

5. **Verifique resultados:**
   - Logs devem mostrar: "Criados X chunks"
   - Para PPTX: deve mostrar "1 slide = 1 chunk"
   - Para PDF/DOCX: deve mostrar "respeitando hierarquia"

---

## 📊 O Que Verificar

### Para PPTX

**Logs esperados:**
```
[INFO] Tipo detectado: pptx
[INFO] Criados 10 chunks (1 slide = 1 chunk)
```

**Verificação:**
- Número de chunks = número de slides
- Cada chunk contém conteúdo de um slide completo
- Descrições de gráficos preservadas (se houver)

### Para PDF/DOCX

**Logs esperados:**
```
[INFO] Tipo detectado: hierarchy
[INFO] Criados 5 chunks (respeitando hierarquia)
```

**Verificação:**
- Chunks respeitam estrutura H1/H2/H3
- Descrições de gráficos preservadas
- ETL detecta entidades corretamente

### ETL

**Logs esperados:**
```
[ETL-PRE] ETL habilitado detectado
[ETL-POST] ETL executado em X chunks
```

**Verificação:**
- Chunks têm propriedades ETL preenchidas
- `entity_mentions` contém entidades detectadas
- `section_entity_ids` preenchido (se aplicável)

---

## 🔍 Troubleshooting

### Erro: "No Contextual.ai API Key detected"

**Solução:**
- Configure `CONTEXTUAL_AI_API_KEY` como variável de ambiente
- Ou configure na interface do Verba (campo "API Key")

### Erro: "Job não completou"

**Possíveis causas:**
1. Endpoint de resultado incorreto
2. Timeout muito curto
3. Arquivo muito grande

**Solução:**
- Verifique logs para ver qual endpoint foi usado
- Aumente `max_attempts` no código se necessário
- Verifique documentação da API para endpoint correto

### Chunks não são criados

**Verificação:**
- Logs mostram "Criados X chunks"?
- Se sim, problema pode ser no formato da resposta da API
- Verifique arquivo `test_output/contextual_ai_result_*.json`

### ETL não executa

**Verificação:**
- `enable_etl=True` está em `document.meta`?
- Logs mostram `[ETL-PRE]` e `[ETL-POST]`?
- spaCy instalado? (`python -m spacy download pt_core_news_sm`)

---

## 📝 Exemplo de Teste Completo

### Cenário: PPTX com 5 slides

1. **Upload:** `apresentacao_5_slides.pptx`
2. **Resultado esperado:**
   - 5 chunks criados
   - Cada chunk = 1 slide
   - ETL processa 5 chunks
   - Chunks salvos no Weaviate

3. **Verificação:**
   ```python
   # No Weaviate, verificar:
   # - 5 chunks na collection
   # - Cada chunk tem doc_uuid vinculado
   # - Chunks têm propriedades ETL (se ETL habilitado)
   ```

---

## 🔗 Referências

- [Contextual.ai API Documentation](https://docs.contextual.ai/api-reference/parse/parse-file)
- [Guia do Ingestor](./CONTEXTUAL_AI_INGESTOR.md)
- [Integração com ETL](./INTEGRACAO_CONTEXTUAL_AI_ETL.md)

---

**Última atualização**: Janeiro 2025  
**API Key de teste**: Fornecida pelo usuário









