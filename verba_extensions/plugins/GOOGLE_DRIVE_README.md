# Google Drive Reader - Importação com ETL A2

Plugin para importar arquivos diretamente do Google Drive para o Verba, com suporte completo ao ETL A2 avançado (NER + Section Scope).

## 🚀 Funcionalidades

- ✅ Importa arquivos de pastas do Google Drive
- ✅ Importa arquivos específicos por ID
- ✅ Suporte a subpastas (recursivo)
- ✅ Múltiplos formatos (PDF, DOCX, TXT, MD, XLSX, PPTX, etc.)
- ✅ **ETL A2 automático** - Extração de entidades (NER) e Section Scope
- ✅ Suporte a Service Account e OAuth 2.0
- ✅ **Patchable** - Não modifica código core do Verba

## 📦 Instalação

### 1. Instalar dependências

```bash
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

### 2. Configurar credenciais

#### Opção A: Service Account (Recomendado para servidores)

1. Acesse [Google Cloud Console](https://console.cloud.google.com/)
2. Crie um projeto ou selecione um existente
3. Ative a **Google Drive API**
4. Crie uma **Service Account**:
   - Vá em "IAM & Admin" > "Service Accounts"
   - Clique em "Create Service Account"
   - Dê um nome e crie
5. Baixe a chave JSON:
   - Clique na service account criada
   - Vá em "Keys" > "Add Key" > "Create new key"
   - Selecione JSON e baixe
6. Compartilhe a pasta do Google Drive com a service account:
   - Abra a pasta no Google Drive
   - Clique em "Compartilhar"
   - Cole o email da service account (ex: `service-account@project.iam.gserviceaccount.com`)
   - Dê permissão de "Visualizador"
7. Configure a variável de ambiente:

```bash
export GOOGLE_DRIVE_CREDENTIALS="/caminho/para/service-account-key.json"
```

Ou no `.env`:
```
GOOGLE_DRIVE_CREDENTIALS=/caminho/para/service-account-key.json
```

#### Opção B: OAuth 2.0 (Para contas pessoais)

1. Acesse [Google Cloud Console](https://console.cloud.google.com/)
2. Crie um projeto ou selecione um existente
3. Ative a **Google Drive API**
4. Configure OAuth consent screen:
   - Vá em "APIs & Services" > "OAuth consent screen"
   - Selecione "External" (ou "Internal" se for Workspace)
   - Preencha informações básicas
5. Crie credenciais OAuth:
   - Vá em "APIs & Services" > "Credentials"
   - Clique em "Create Credentials" > "OAuth client ID"
   - Selecione "Desktop app"
   - Baixe o JSON
6. Autentique e salve o token:
   - Execute o script de autenticação (veja abaixo)
   - O token será salvo automaticamente

**Script de autenticação OAuth:**

```python
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
import json

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
CLIENT_SECRETS_FILE = 'credentials.json'  # JSON baixado do Google Cloud

flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
creds = flow.run_local_server(port=0)

# Salva credenciais
with open('token.json', 'w') as token:
    token.write(creds.to_json())

print("✅ Autenticação concluída! Use token.json como GOOGLE_DRIVE_CREDENTIALS")
```

Configure:
```bash
export GOOGLE_DRIVE_CREDENTIALS="/caminho/para/token.json"
```

## 📖 Como Usar

### 1. Via Interface Web

1. Acesse a página de Importação no Verba
2. Clique em "Add URL" (o Google Drive Reader aparece como tipo URL)
3. Selecione "Google Drive (ETL A2)"
4. Configure:
   - **Folder ID**: ID da pasta ou URL compartilhada do Google Drive
     - Para obter o ID: abra a pasta no Google Drive, o ID está na URL: `https://drive.google.com/drive/folders/SEU_FOLDER_ID_AQUI`
     - Ou use `root` para a raiz do Drive
   - **File IDs** (opcional): IDs específicos de arquivos (separados por vírgula)
   - **Recursive**: Importar subpastas recursivamente
   - **File Types**: Tipos de arquivo (ex: `pdf,docx,txt,md`)
   - **Enable ETL**: Aplicar ETL A2 automaticamente (recomendado: True)
   - **Language Hint**: Idioma para NER (pt, en, etc.)
5. Clique em "Import"

### 2. Exemplos de Configuração

#### Importar pasta inteira:
- **Folder ID**: `1a2b3c4d5e6f7g8h9i0j`
- **Recursive**: `True`
- **File Types**: `pdf,docx,txt,md`

#### Importar arquivos específicos:
- **File IDs**: 
  ```
  1a2b3c4d5e6f7g8h9i0j
  2b3c4d5e6f7g8h9i0j1k
  ```
- **Folder ID**: (deixe vazio)

#### Importar apenas PDFs de uma pasta:
- **Folder ID**: `1a2b3c4d5e6f7g8h9i0j`
- **File Types**: `pdf`
- **Recursive**: `False`

## 🔧 ETL A2 Integrado

O plugin automaticamente:
- ✅ Habilita ETL A2 em todos os documentos importados
- ✅ Extrai entidades (NER) usando spaCy
- ✅ Aplica Section Scope para contexto de seções
- ✅ Armazena metadados do Google Drive (file_id, source, etc.)

Os chunks importados terão:
- `entities_local_ids`: IDs de entidades encontradas no chunk
- `section_entity_ids`: IDs de entidades relacionadas à seção
- `primary_entity_id`: Entidade primária do chunk
- `entity_focus_score`: Score de foco na entidade
- Metadados do Google Drive preservados

## 🛠️ Troubleshooting

### Erro: "Google Drive API não disponível"
```bash
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

### Erro: "GOOGLE_DRIVE_CREDENTIALS não configurado"
Verifique se a variável de ambiente está configurada:
```bash
echo $GOOGLE_DRIVE_CREDENTIALS
```

### Erro: "Permission denied" ou "File not found"
- Verifique se a Service Account tem acesso à pasta (compartilhe a pasta com o email da service account)
- Verifique se o Folder ID está correto
- Para OAuth, verifique se o token não expirou (re-autentique se necessário)

### Erro: "API not enabled"
Ative a Google Drive API no Google Cloud Console:
1. Vá em "APIs & Services" > "Library"
2. Procure por "Google Drive API"
3. Clique em "Enable"

## 📝 Notas

- O plugin é **patchable** - não modifica código core do Verba
- Compatível com todas as versões do Verba que suportam plugins
- ETL A2 requer schema ETL-aware (collections criadas automaticamente com schema completo)
- Arquivos grandes podem demorar para importar (depende da conexão)

## 🔄 Atualizações

Este plugin é mantido como extensão patchable. Ao atualizar o Verba:
1. Verifique se o plugin ainda funciona
2. Se necessário, atualize as dependências
3. O plugin não será sobrescrito por atualizações do Verba

## 📄 Licença

Este plugin segue a mesma licença do Verba (open source).

