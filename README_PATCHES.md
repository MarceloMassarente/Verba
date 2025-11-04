# Guia Rápido de Patches - Verba Customizado

Este README fornece uma referência rápida para aplicar patches após atualizações do Verba padrão.

## 📚 Documentação Completa

- **[TODAS_MUDANCAS_VERBA.md](./TODAS_MUDANCAS_VERBA.md)** - Documentação completa de TODAS as mudanças
- **[PATCHES_VERBA_WEAVIATE_V4.md](./PATCHES_VERBA_WEAVIATE_V4.md)** - Patches específicos do Weaviate v4
- **[CORRECAO_CONEXAO_WEAVIATE.md](./CORRECAO_CONEXAO_WEAVIATE.md)** - Detalhes da correção de conexão

## 🚀 Processo Rápido

### 1. Verificar Status Atual

**Windows:**
```powershell
.\APLICAR_PATCHES.ps1
```

**Linux/Mac:**
```bash
./APLICAR_PATCHES.sh
```

Isso mostrará quais patches já estão aplicados e quais faltam.

### 2. Aplicar Patches

Siga a ordem em **[TODAS_MUDANCAS_VERBA.md](./TODAS_MUDANCAS_VERBA.md)**:

1. **Core Changes** (Chunk, VerbaManager)
2. **Weaviate v4** (managers.py) - **CRÍTICO**
3. **Plugins RAG2** (novos arquivos)
4. **EntityAwareRetriever** (integração)

### 3. Testar

```bash
# Testes de conexão Weaviate
python test_weaviate_access.py

# Testes unitários RAG2
pytest verba_extensions/tests/

# Teste de named vectors
python test_named_vectors_v4_rest.py
```

## ⚠️ Mudanças Críticas

### Weaviate v4 (managers.py)

**POR QUE É CRÍTICO:** Sem essas mudanças, conexão Weaviate v4 em PaaS (Railway) falha.

**CHECKLIST:**
- [ ] Configuração PaaS explícita (`WEAVIATE_HTTP_HOST`, `WEAVIATE_GRPC_HOST`)
- [ ] Uso de `connect_to_custom` para HTTPS
- [ ] Remoção de `WeaviateV3HTTPAdapter`
- [ ] Verificação de `hasattr(client, 'connect')`

**Ver:** [PATCHES_VERBA_WEAVIATE_V4.md](./PATCHES_VERBA_WEAVIATE_V4.md)

### Chunk (chunk_lang, chunk_date)

**POR QUE É IMPORTANTE:** Necessário para filtros RAG2 (bilingual, temporal).

**CHECKLIST:**
- [ ] Adicionar `chunk_lang` e `chunk_date` no `__init__`
- [ ] Atualizar `to_json()` e `from_json()`

**Ver:** [TODAS_MUDANCAS_VERBA.md - Seção 1](./TODAS_MUDANCAS_VERBA.md#1-chunk-goldenverbacomponentschunkpy)

## 📦 Dependências

```bash
# Weaviate v4
pip install weaviate-client>=4.0.0

# RAG2 Features
pip install langdetect cachetools

# Testes (opcional)
pip install pytest pytest-asyncio httpx
```

## 🔍 Troubleshooting Rápido

| Erro | Solução |
|------|---------|
| `'WeaviateV3HTTPAdapter' object has no attribute 'connect'` | Remover referências ao adapter v3 |
| `ModuleNotFoundError: No module named 'langdetect'` | `pip install langdetect` |
| `Meta endpoint! Unexpected status code: 400` | Verificar configuração PaaS (`WEAVIATE_HTTP_HOST`, etc.) |
| `gRPC health check could not be completed` | Verificar `WEAVIATE_GRPC_HOST` e `WEAVIATE_GRPC_PORT` |

## 📝 Estrutura de Arquivos

```
Verba/
├── goldenverba/
│   ├── components/
│   │   ├── chunk.py          # MODIFICADO (chunk_lang, chunk_date)
│   │   └── managers.py       # MODIFICADO (Weaviate v4)
│   └── verba_manager.py      # MODIFICADO (detecção de idioma)
│
├── verba_extensions/
│   └── plugins/
│       ├── bilingual_filter.py       # NOVO
│       ├── query_rewriter.py         # NOVO
│       ├── temporal_filter.py       # NOVO
│       └── entity_aware_retriever.py # MODIFICADO (integração RAG2)
│
└── Documentação/
    ├── TODAS_MUDANCAS_VERBA.md      # Guia completo
    ├── PATCHES_VERBA_WEAVIATE_V4.md # Patches Weaviate
    ├── README_PATCHES.md            # Este arquivo
    ├── APLICAR_PATCHES.ps1          # Script Windows
    └── APLICAR_PATCHES.sh           # Script Linux/Mac
```

## 🎯 Ordem de Aplicação Recomendada

1. ✅ **Backup** do código atual
2. ✅ **Atualizar** Verba padrão (merge/rebase)
3. ✅ **Verificar** status com script de verificação
4. ✅ **Aplicar** patches na ordem:
   - Core (Chunk, VerbaManager)
   - Weaviate v4 (managers.py) - **CRÍTICO**
   - Plugins RAG2 (novos arquivos)
   - EntityAwareRetriever (modificações)
5. ✅ **Testar** conexão e funcionalidades
6. ✅ **Commit** patches aplicados

## 📞 Ajuda

Se encontrar problemas:

1. Verifique os logs de erro
2. Consulte a documentação específica:
   - Weaviate v4: [PATCHES_VERBA_WEAVIATE_V4.md](./PATCHES_VERBA_WEAVIATE_V4.md)
   - Todas mudanças: [TODAS_MUDANCAS_VERBA.md](./TODAS_MUDANCAS_VERBA.md)
3. Execute o script de verificação para diagnóstico
4. Verifique variáveis de ambiente (PaaS)

---

**Última atualização:** 2025-11-04  
**Versão Verba Base:** (verificar após update)  
**weaviate-client:** 4.17.0

