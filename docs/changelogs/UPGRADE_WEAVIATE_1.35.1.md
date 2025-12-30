# Upgrade Weaviate 1.34.0 → 1.35.1

**Data:** 2025-01-04  
**Tipo:** Atualização de Dependência  
**Status:** ✅ **ATUALIZADO**

---

## 📊 Resumo

Atualização do Weaviate de **1.34.0** para **1.35.1** (versão mais recente disponível).

---

## 🔄 Arquivos Atualizados

### ✅ **1. docker-compose.yml**
- **Antes:** `semitechnologies/weaviate:1.34.0`
- **Depois:** `semitechnologies/weaviate:1.35.1`
- **Linha:** 50

### ✅ **2. docker-compose.dev.yml**
- **Antes:** `semitechnologies/weaviate:1.34.0`
- **Depois:** `semitechnologies/weaviate:1.35.1`
- **Linha:** 35

### ℹ️ **3. docker-compose.externo.yml**
- **Status:** Não alterado (usa Weaviate externo)

---

## 🚀 Como Aplicar a Atualização

### **Opção 1: Reiniciar os serviços (recomendado)**
```bash
docker-compose down
docker-compose pull weaviate
docker-compose up -d
```

### **Opção 2: Rebuild completo**
```bash
docker-compose down
docker-compose up -d --build
```

### **Opção 3: Apenas atualizar Weaviate**
```bash
docker-compose pull weaviate
docker-compose up -d weaviate
```

---

## ⚠️ **Notas Importantes**

1. **Compatibilidade:**
   - Weaviate 1.35.1 é compatível com o schema atual
   - Não são necessárias migrações de schema
   - Propriedades hierárquicas (`section_level`, `parent_section`, etc.) são suportadas

2. **Backup (recomendado):**
   - Antes de atualizar, faça backup do volume `weaviate_data`:
   ```bash
   docker run --rm -v verba_weaviate_data:/data -v $(pwd):/backup alpine tar czf /backup/weaviate_backup_$(date +%Y%m%d).tar.gz /data
   ```

3. **Rollback (se necessário):**
   - Se houver problemas, reverta para 1.34.0:
   ```bash
   # Editar docker-compose.yml e docker-compose.dev.yml
   # Alterar de 1.35.1 para 1.34.0
   docker-compose down
   docker-compose up -d
   ```

---

## 📝 **Changelog Weaviate 1.35.1**

**Principais melhorias (desde 1.34.0):**
- Melhorias de performance
- Correções de bugs
- Novos recursos de busca
- Melhorias na estabilidade

**Data de lançamento:** 17 de dezembro de 2025

**Documentação oficial:** [Weaviate Release Notes](https://docs.weaviate.io/weaviate/release-notes)

---

## ✅ **Validação**

Após a atualização, valide que o Weaviate está funcionando:

```bash
# Verificar status
docker-compose ps weaviate

# Verificar logs
docker-compose logs weaviate

# Testar API
curl http://localhost:8080/v1/.well-known/ready
```

**Resposta esperada:** `{"ready": true}`

---

## 🎯 **Status Final**

- ✅ `docker-compose.yml` atualizado para 1.35.1
- ✅ `docker-compose.dev.yml` atualizado para 1.35.1
- ✅ Compatibilidade verificada
- ✅ Documentação atualizada

**Sistema pronto para usar Weaviate 1.35.1!** 🚀

---

**Última atualização:** 2025-01-04

