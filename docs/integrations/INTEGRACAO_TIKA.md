# 🔧 Integração Apache Tika no Verba

## 📋 Visão Geral

A integração do Apache Tika foi implementada em **duas camadas**:

1. **Universal Reader** (`universal_reader.py` v2.0.0) - Reader universal com integração Tika
2. **Patch de Fallback** (`tika_fallback_patch.py`) - Integração transparente no BasicReader

> **Nota:** O plugin `tika_reader.py` foi **consolidado** no Universal Reader (v2.0.0) para evitar redundância.

Esta arquitetura permite:
- ✅ **Atualizações seguras** - patches não quebram com atualizações do Verba
- ✅ **Flexibilidade** - pode usar Tika como reader principal ou apenas fallback
- ✅ **Transparência** - métodos nativos têm prioridade, Tika só quando necessário
- ✅ **Consolidação** - um único reader universal para arquivos, URLs e JSON

---

## 🏗️ Arquitetura

### **1. Universal Reader com Tika**

**Localização:** `verba_extensions/plugins/universal_reader.py`

**Características:**
- Reader verdadeiramente universal: Arquivos + URLs + JSON Results
- Integração Tika para formatos benéficos (PPTX, DOC, RTF, ODT, etc.)
- Suporta 1000+ formatos via Tika quando disponível
- Extrai metadados automaticamente
- Configurável via UI ("Use Tika When Available") ou variável de ambiente

**Uso:**
- Escolher "Universal A2 (Arquivos + URLs)" na UI ao importar
- Habilitar "Use Tika When Available" para melhor extração
- Útil para formatos exóticos ou quando precisa de metadados

### **2. Patch de Fallback**

**Localização:** `verba_extensions/integration/tika_fallback_patch.py`

**Características:**
- Modifica `BasicReader` para usar Tika quando métodos nativos falham
- Totalmente transparente - usuário não percebe
- Tenta método nativo primeiro, depois Tika

**Fluxo:**
```
1. Usuário importa arquivo
2. BasicReader tenta método nativo
3. Se falhar OU formato não suportado → usa Tika
4. Se Tika não disponível → retorna erro original
```

---

## 🚀 Como Usar

### **Opção 1: Reader Tika (Recomendado para formatos exóticos)**

1. Na UI do Verba → **Import Data**
2. Escolher **"Tika Reader (Multi-Formato)"**
3. Fazer upload do arquivo
4. Metadados serão extraídos automaticamente

### **Opção 2: Fallback Automático (Padrão)**

1. Usar qualquer reader (Default, Universal A2, etc.)
2. Se formato não suportado → Tika é usado automaticamente
3. Se método nativo falhar → Tika é usado automaticamente

**Vantagem:** Funciona transparentemente, sem necessidade de escolher reader específico

---

## ⚙️ Configuração

### **Variável de Ambiente**

```bash
export TIKA_SERVER_URL="http://192.168.1.197:9998"
```

**Padrão:** `http://localhost:9998`

### **Configuração no Railway**

No Railway → **Verba** → Settings → Variables:

```bash
TIKA_SERVER_URL=http://192.168.1.197:9998
```

**OU** se Tika estiver em outro serviço Railway:

```bash
# Mesmo projeto (acesso interno)
TIKA_SERVER_URL=http://tika.railway.internal:9998

# Projeto separado (URL pública)
TIKA_SERVER_URL=https://tika-production-xxxx.up.railway.app
```

**Ver guia completo:** `GUIA_TIKA_RAILWAY.md`

### **Configuração no Dockerfile**

```dockerfile
# Instalar Java (requerido pelo Tika)
RUN apt-get update && apt-get install -y \
    openjdk-11-jdk \
    && rm -rf /var/lib/apt/lists/*

# Instalar Tika Server (opcional - se quiser rodar localmente)
# Ou usar servidor Tika remoto via TIKA_SERVER_URL
ENV TIKA_SERVER_URL="http://192.168.1.197:9998"
```

---

## 📊 Formatos Suportados

### **Formatos Nativos (via BasicReader):**
- ✅ PDF (pypdf)
- ✅ DOCX (python-docx)
- ✅ Excel (pandas)
- ✅ CSV (built-in)
- ✅ TXT (built-in)

### **Formatos via Tika (fallback ou reader dedicado):**
- ✅ PPTX, PPT (PowerPoint)
- ✅ DOC (Word antigo)
- ✅ RTF
- ✅ ODT, ODS, ODP (OpenOffice)
- ✅ EPUB
- ✅ E muitos outros (1000+ formatos)

---

## 🔍 Metadados Extraídos

Quando usando Tika, os seguintes metadados são extraídos:

### **Metadados Básicos:**
- `title` - Título do documento
- `author` / `creator` - Autor
- `producer` - Software que criou o documento
- `subject` - Assunto
- `keywords` - Palavras-chave
- `created` / `modified` - Datas

### **Metadados Técnicos:**
- `language` - Idioma detectado
- `pdf:PDFVersion` - Versão do PDF
- `xmpTPg:NPages` - Número de páginas
- `access_permission:*` - Permissões do documento

### **Acesso aos Metadados:**

```python
# No documento
document.meta['tika_title']  # Título
document.meta['tika_author']  # Autor
document.meta['tika_metadata']  # Todos os metadados (dict)
```

---

## 🛠️ Manutenção e Atualizações

### **Ao Atualizar Verba:**

1. **Verificar se métodos ainda existem:**
   ```bash
   # Verificar se BasicReader.load() ainda existe
   python -c "from goldenverba.components.reader.BasicReader import BasicReader; print(hasattr(BasicReader, 'load'))"
   ```

2. **Testar fallback:**
   - Importar um PPTX
   - Verificar se Tika é usado automaticamente
   - Verificar logs para "[TIKA-FALLBACK]"

3. **Se métodos mudarem:**
   - Atualizar `tika_fallback_patch.py` com novas assinaturas
   - Testar com vários formatos

### **Desabilitar Tika Fallback:**

```python
# Em verba_extensions/startup.py
# Comentar ou remover:
# patch_basic_reader_with_tika_fallback()
```

---

## 🐛 Troubleshooting

### **Tika não está sendo usado:**

1. Verificar se servidor está acessível:
   ```bash
   curl http://192.168.1.197:9998/tika
   ```

2. Verificar variável de ambiente:
   ```bash
   echo $TIKA_SERVER_URL
   ```

3. Verificar logs:
   - Procurar por "[TIKA-FALLBACK]" nos logs
   - Se não aparecer, Tika não está sendo usado

### **Erro "Tika não disponível":**

- Servidor Tika não está rodando
- URL incorreta em `TIKA_SERVER_URL`
- Problema de rede/firewall

**Solução:** Verificar se servidor Tika está acessível ou usar apenas métodos nativos

### **Método nativo funciona mas Tika não:**

- Normal - métodos nativos têm prioridade
- Tika só é usado quando método nativo falha
- Se quiser forçar Tika, usar "Tika Reader" na UI

---

## 📈 Benefícios

### **Para o Sistema:**

1. ✅ **Suporte amplo** - 1000+ formatos sem código adicional
2. ✅ **Metadados** - informação rica dos documentos
3. ✅ **Robustez** - fallback quando métodos nativos falham
4. ✅ **Manutenibilidade** - patches isolados, fácil atualizar

### **Para o Usuário:**

1. ✅ **PPTX funciona** - finalmente implementado
2. ✅ **PDFs complexos** - extração melhorada
3. ✅ **Formatos antigos** - DOC, RTF, etc. funcionam
4. ✅ **Transparente** - funciona automaticamente

---

## 🔗 Arquivos Relacionados

- `verba_extensions/plugins/universal_reader.py` - Reader Universal com integração Tika (v2.0.0)
- `verba_extensions/integration/tika_fallback_patch.py` - Patch de fallback
- `verba_extensions/startup.py` - Inicialização (aplica patches)

> **Nota:** `tika_reader.py` foi consolidado no Universal Reader (v2.0.0)
- `verba_extensions/patches/README_PATCHES.md` - Documentação de patches
- `scripts/test_tika_local_file.py` - Script de teste

---

**Última atualização:** 2025-11-05

