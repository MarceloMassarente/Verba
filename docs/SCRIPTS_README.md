# 🛠️ Documentação de Scripts de Utilidade

Este documento descreve todos os scripts de utilidade disponíveis no projeto.

## 📁 Scripts Disponíveis

### 🔧 **Scripts de Patches**

#### `scripts/apply_patches.py`
**Descrição:** Aplica patches automáticos no código do Verba.

**Uso:**
```bash
# Aplicar patches para versão específica
python scripts/apply_patches.py --version 2.1.3

# Aplicar patches sem especificar versão (usa versão atual)
python scripts/apply_patches.py

# Verificar quais patches serão aplicados (dry-run)
python scripts/apply_patches.py --dry-run
```

**Patches que aplica:**
- ✅ Carregamento de extensões (`api.py`)
- ✅ SentenceTransformersEmbedder (`managers.py`)

**Limitações:**
- ⚠️ Não aplica patches complexos (requerem merge manual)
- ⚠️ Sempre faça backup antes de executar

**Exemplo:**
```bash
$ python scripts/apply_patches.py --version 2.1.3
🔄 Aplicador de Patches para Verba
==================================================
ℹ️  Processando: api_startup
✅ Patch aplicado: Carregamento de extensões no startup
ℹ️  Processando: managers_sentence_transformers
✅ Patch aplicado: Adicionar SentenceTransformersEmbedder na lista
==================================================
✅ Todos os patches automáticos foram aplicados!
```

---

#### `APLICAR_PATCHES.sh` / `APLICAR_PATCHES.ps1`
**Descrição:** Script de verificação de patches aplicados (bash/PowerShell).

**Uso:**
```bash
# Linux/Mac
./APLICAR_PATCHES.sh

# Windows
.\APLICAR_PATCHES.ps1
```

**Funcionalidades:**
- ✅ Verifica versão do weaviate-client
- ✅ Verifica imports necessários
- ✅ Verifica quais patches já foram aplicados
- ✅ Mostra status de cada patch

**Exemplo de saída:**
```
==========================================
APLICANDO PATCHES WEAVIATE V4
==========================================
1. Criando backup...
   Backup criado: goldenverba/components/managers.py.backup.*

2. Verificando versão do weaviate-client...
   Versão encontrada: 4.17.0

3. Verificando imports necessários...
   ✓ AuthApiKey import encontrado
   ✓ AdditionalConfig, Timeout imports encontrados

4. Verificando patches já aplicados...
   ✓ PATCH 1 (PaaS config) - APLICADO
   ✓ PATCH 2 (HTTPS connect_to_custom) - PARCIALMENTE APLICADO
   ✓ PATCH 3 (Remover adapter v3) - APLICADO
   ✓ PATCH 4 (Verificação connect) - APLICADO
```

---

### 📦 **Scripts de Schema e Setup**

#### `scripts/create_schema.py`
**Descrição:** Cria schema Weaviate para Article/Passage usado pelo ETL A2.

**Uso:**
```bash
python scripts/create_schema.py
```

**Funcionalidades:**
- ✅ Cria coleções `Article` e `Passage`
- ✅ Configura propriedades necessárias
- ✅ Suporta Weaviate v3 e v4
- ✅ Valida schema após criação

**Variáveis de ambiente necessárias:**
```bash
WEAVIATE_URL=http://localhost:8080
WEAVIATE_API_KEY=  # opcional
WEAVIATE_TENANT=news_v1  # opcional
```

**Exemplo:**
```bash
$ python scripts/create_schema.py
ℹ️  Conectando ao Weaviate...
✅ Conectado ao Weaviate
ℹ️  Criando schema...
✅ Coleção Article criada
✅ Coleção Passage criada
✅ Schema criado com sucesso!
```

---

#### `scripts/pdf_to_a2_json.py`
**Descrição:** Converte PDF para formato JSON A2 usado pelo ingestor.

**Uso:**
```bash
# Converter um arquivo
python scripts/pdf_to_a2_json.py input.pdf output.json

# Converter múltiplos arquivos
python scripts/pdf_to_a2_json.py *.pdf --output-dir ./json_output/

# Converter com opções
python scripts/pdf_to_a2_json.py input.pdf output.json --language pt --min-paragraph-length 100
```

**Opções:**
- `--language`: Idioma do documento (padrão: pt)
- `--min-paragraph-length`: Tamanho mínimo de parágrafo (padrão: 50)
- `--output-dir`: Diretório de saída para múltiplos arquivos

**Exemplo:**
```bash
$ python scripts/pdf_to_a2_json.py documento.pdf documento.json
ℹ️  Lendo PDF: documento.pdf
ℹ️  Extraindo texto...
✅ Extraídos 45 parágrafos
ℹ️  Convertendo para JSON A2...
✅ JSON salvo em: documento.json
```

---

#### `scripts/check_dependencies.py`
**Descrição:** Verifica se todas as dependências estão instaladas.

**Uso:**
```bash
# Verificar todas as dependências
python scripts/check_dependencies.py

# Verificar apenas dependências de extensões
python scripts/check_dependencies.py --extensions-only

# Instalar dependências faltantes automaticamente
python scripts/check_dependencies.py --install-missing
```

**Funcionalidades:**
- ✅ Verifica dependências do Verba
- ✅ Verifica dependências de extensões
- ✅ Verifica modelos spaCy instalados
- ✅ Oferece instalação automática

**Exemplo:**
```bash
$ python scripts/check_dependencies.py
✅ Verificando dependências...
✅ weaviate-client: 4.17.0 (OK)
✅ fastapi: 0.111.1 (OK)
✅ sentence-transformers: 2.2.0 (OK)
⚠️  spacy: 3.7.0 (instalado, mas modelo pt_core_news_sm não encontrado)
   Execute: python -m spacy download pt_core_news_sm en_core_web_sm
```

---


---

#### `scripts/verify_ingestion_status.py`
**Descrição:** Verifica o status de ingestão dos documentos, validando metadados e contagens.

**Uso:**
```bash
python scripts/verify_ingestion_status.py
```

**Funcionalidades:**
- ✅ Conta documentos e chunks
- ✅ Verifica metadados críticos (frameworks, companies, etc.)
- ✅ Valida integridade da ingestão

---

#### `scripts/migrate_collection_schema.py`
**Descrição:** Migra e valida o schema das coleções Weaviate.

**Uso:**
```bash
python scripts/migrate_collection_schema.py
```

**Funcionalidades:**
- ✅ Atualiza schema para incluir novas propriedades
- ✅ Verifica consistência entre WeaviateManager e classes Weaviate
- ✅ Seguro: não deleta dados existentes

---

### 🔍 **Scripts de Verificação**

#### `scripts/verify_patches.py` (A criar)
**Descrição:** Verifica se patches foram aplicados corretamente.

**Uso:**
```bash
# Verificar patches para versão específica
python scripts/verify_patches.py --version 2.1.3

# Verificar todos os patches
python scripts/verify_patches.py --all

# Gerar relatório
python scripts/verify_patches.py --version 2.1.3 --report
```

**Funcionalidades:**
- ✅ Verifica cada patch individualmente
- ✅ Detecta conflitos
- ✅ Gera relatório detalhado
- ✅ Sugere correções

---

#### `scripts/merge_connect_to_custom.py` (A criar)
**Descrição:** Script semi-automático para merge do método `connect_to_custom()`.

**Uso:**
```bash
# Fazer merge automático
python scripts/merge_connect_to_custom.py --auto

# Merge interativo (recomendado)
python scripts/merge_connect_to_custom.py --interactive

# Comparar versões
python scripts/merge_connect_to_custom.py --compare
```

**Funcionalidades:**
- ✅ Compara versão oficial vs customizada
- ✅ Detecta conflitos automaticamente
- ✅ Aplica mudanças incrementalmente
- ✅ Cria backup antes de modificar

---

### 🧪 **Scripts de Teste**

#### `run_all_tests.py`
**Descrição:** Executa todos os testes do projeto.

**Uso:**
```bash
# Executar todos os testes
python run_all_tests.py

# Executar testes específicos
python run_all_tests.py --test test_weaviate_access

# Executar com verbose
python run_all_tests.py --verbose
```

---

## 📋 Checklist de Scripts

### Scripts Existentes
- [x] `scripts/apply_patches.py`
- [x] `APLICAR_PATCHES.sh`
- [x] `APLICAR_PATCHES.ps1`
- [x] `scripts/create_schema.py`
- [x] `scripts/pdf_to_a2_json.py`
- [x] `scripts/check_dependencies.py`
- [x] `run_all_tests.py`

### Scripts a Criar
- [ ] `scripts/verify_patches.py`
- [ ] `scripts/merge_connect_to_custom.py`
- [ ] `scripts/test_patches_compatibility.py`

## 🔧 Como Criar Novos Scripts

### Template Básico

```python
#!/usr/bin/env python3
"""
Descrição do script
"""

import argparse
import sys
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description='Descrição do script')
    parser.add_argument('--version', type=str, help='Versão do Verba')
    parser.add_argument('--dry-run', action='store_true', help='Modo simulação')
    
    args = parser.parse_args()
    
    # Sua lógica aqui
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
```

### Boas Práticas

1. **Sempre use argparse** para argumentos
2. **Adicione help** em todos os argumentos
3. **Use logging** ao invés de print
4. **Valide inputs** antes de processar
5. **Crie backups** antes de modificar arquivos
6. **Documente** o script no cabeçalho

## 📚 Documentação Relacionada

- `INDICE_DOCUMENTACAO.md` - Índice geral de documentação
- `GUIA_APLICAR_PATCHES_UPDATE.md` - Guia de aplicação de patches
- `README_EXTENSOES.md` - Sistema de extensões

---

**Última atualização:** 2025-11-04

