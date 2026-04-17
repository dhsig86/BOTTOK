FROM python:3.11-slim

WORKDIR /app

# Instala dependências do SO (necessárias para faiss/pandas/etc em alguns casos)
RUN apt-get update && apt-get install -y \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copia os requirements e instala
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Configurações do Hugging Face (Porta padrao 7860)
ENV PORT=7860
EXPOSE 7860

# Configura o diretório local para cache dos modelos (impede re-downloads)
ENV TRANSFORMERS_CACHE=/app/.cache
RUN mkdir -p /app/.cache && chmod 777 /app/.cache

# Copia o código da API (main.py) e os vetores (.faiss, .pkl) para o container
COPY . /app/

# Dá permissões totais para o ambiente rodar sem erro no user 1000 padrão do HF
RUN chmod -R 777 /app

# Inicia o servidor FastAPI do arquivo main.py
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
