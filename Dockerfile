FROM python:3.11-slim

# Instala dependências do sistema
RUN apt-get update && apt-get install -y \
    build-essential \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /Verba

# Copia arquivos necessários
COPY . /Verba

# Instala dependências do Verba base
RUN pip install --no-cache-dir '.'

# Instala sentence-transformers (para embedder local)
RUN pip install --no-cache-dir sentence-transformers || true

# Instala dependências das extensões
RUN pip install --no-cache-dir -r requirements-extensions.txt || true

# Instala pandas e openpyxl para suporte completo a arquivos Excel (.xlsx e .xls)
RUN pip install --no-cache-dir pandas openpyxl xlrd || true

# Baixa modelos do spaCy (para ETL A2 e EntityAware Retriever)
RUN python -m spacy download pt_core_news_sm || true

# Baixa dados do NLTK (para chunker)
RUN python -c "import nltk; nltk.download('punkt', quiet=True)" || true

# Expõe porta
EXPOSE 8000

# Comando de inicialização
CMD ["verba", "start", "--port", "8000", "--host", "0.0.0.0", "--prod", "--workers", "1"]
