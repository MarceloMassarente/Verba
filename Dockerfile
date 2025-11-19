FROM python:3.11-slim

# 1. Instala Node.js e dependências de sistema para build
RUN apt-get update && apt-get install -y \
    build-essential \
    wget \
    curl \
    ca-certificates \
    gnupg \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /Verba

# 2. Copia arquivos do projeto
COPY . /Verba

# 3. Build do Frontend
# Instala dependências e compila o frontend React
# O resultado será movido para o diretório correto que o Python serve
WORKDIR /Verba/frontend
RUN npm install
RUN npm run build

# Volta para a raiz para instalar o Python
WORKDIR /Verba

# 4. Instala dependências do Backend (Python)
RUN pip install --no-cache-dir '.'

# Instala sentence-transformers (para embedder local)
RUN pip install --no-cache-dir sentence-transformers || true

# Instala dependências das extensões
RUN pip install --no-cache-dir -r requirements-extensions.txt || true

# Instala pandas e openpyxl para suporte completo a arquivos Excel (.xlsx e .xls)
RUN pip install --no-cache-dir pandas openpyxl xlrd || true

# Instala dependências do Google Drive Reader (plugin patchable)
RUN pip install --no-cache-dir google-api-python-client google-auth-httplib2 google-auth-oauthlib || true

# Baixa modelos do spaCy (para ETL A2 e EntityAware Retriever)
RUN python -m spacy download pt_core_news_sm || true
RUN python -m spacy download en_core_web_sm || pip install --no-cache-dir https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.0/en_core_web_sm-3.7.0-py3-none-any.whl

# Baixa dados do NLTK (para chunker)
RUN python -c "import nltk; nltk.download('punkt', quiet=True)" || true

# Expõe porta
EXPOSE 8000

# Comando de inicialização
CMD ["verba", "start", "--port", "8000", "--host", "0.0.0.0", "--prod", "--workers", "1"]
