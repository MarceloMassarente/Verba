# 🔍 Diferença: Dockerfile vs docker-compose.yml no Railway

## ⚠️ Importante: Railway usa apenas Dockerfile!

### O que acontece no Railway:

1. **Railway lê apenas o `Dockerfile`**
2. **Railway NÃO usa `docker-compose.yml`**
3. Railway roda apenas **1 container** por serviço

### O que o Railway instalou:

Quando você fez deploy no Railway, ele executou apenas:

```dockerfile
FROM python:3.11-slim
# ... instalações ...
RUN pip install '.'
RUN pip install -r requirements-extensions.txt
# ...
CMD ["verba", "start", ...]
```

**Resultado**: Apenas o container do **Verba** foi criado!

---

## 📋 O docker-compose.yml é só para local

O `docker-compose.yml` que criamos é **apenas para uso local**:

```bash
# Funciona assim:
docker-compose up -d  # ← Lê docker-compose.yml e sobe 2 serviços

# No Railway:
# Não usa docker-compose!
# Apenas roda o Dockerfile → 1 container
```

---

## 🚂 Como Railway funciona

### Cenário 1: Serviços Separados (seu caso atual)

```
Railway Projeto 1: Verba
  └─ Dockerfile → Container Verba

Railway Projeto 2: Weaviate  
  └─ Dockerfile do Weaviate → Container Weaviate
```

**Cada projeto = 1 container**

### Cenário 2: Usar docker-compose no Railway (não comum)

Railway **pode** usar docker-compose, mas precisa:
1. Configurar `railway.json` ou usar "Docker Compose" como buildpack
2. Aí sim leria o `docker-compose.yml`

**Mas isso é raro!** A maioria usa Dockerfile simples.

---

## ✅ O que você precisa fazer

### Opção 1: Manter como está (Recomendado)

- Verba em um projeto
- Weaviate em outro projeto
- Conectar via variáveis de ambiente

### Opção 2: Usar docker-compose no Railway

1. No Railway, configure para usar "Docker Compose"
2. Aí sim o `docker-compose.yml` seria lido
3. Mas isso criaria 2 serviços no mesmo projeto

---

## 🔧 Como Railway viu seu código

Quando você fez push para o GitHub e Railway buildou:

```
Railway viu:
├── Dockerfile ← USEI ESTE!
├── docker-compose.yml ← IGNOREI (não uso por padrão)
├── verba_extensions/ ← COPIEI
└── ... resto do código

Resultado:
  Container único com Verba + extensões
  SEM Weaviate (precisa ser externo ou outro serviço)
```

---

## 📝 Resumo

| Arquivo | Onde funciona | Railway usa? |
|---------|---------------|--------------|
| `Dockerfile` | Local e Railway | ✅ SIM |
| `docker-compose.yml` | Apenas local | ❌ NÃO (por padrão) |

**Railway instalou**: Apenas o que está no `Dockerfile` = Verba + extensões  
**Railway NÃO instalou**: Weaviate (não está no Dockerfile, está só no compose)

---

## 🎯 Próximos Passos

1. **Manter setup atual** (Verba separado de Weaviate):
   - Configure `WEAVIATE_URL_VERBA` no Railway
   
2. **OU criar serviço Weaviate no Railway**:
   - Novo serviço no Railway
   - Use imagem: `semitechnologies/weaviate:1.25.10`
   - Conecte via variáveis

**Recomendação**: Opção 1 (já está quase pronto!)

