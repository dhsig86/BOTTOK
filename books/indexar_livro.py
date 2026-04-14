# -*- coding: utf-8 -*-
"""
indexar_livro.py  (v2 — multi-livro)
=====================================
Escaneia TODOS os PDFs da pasta books/ e cria um indice vetorial unificado.
Execute este script sempre que adicionar novos livros.

Para re-indexar do zero, delete:
  - orl_index.faiss
  - orl_chunks.pkl

Uso:
    python books/indexar_livro.py
"""

import os
import sys
import pickle
import PyPDF2
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

# Forcar saida UTF-8 no terminal Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# --- Configuracoes -----------------------------------------------------------
BOOKS_DIR   = os.path.dirname(__file__)
BIBLIOTECA_DIR = os.path.join(BOOKS_DIR, "biblioteca")
INDEX_PATH  = os.path.join(BOOKS_DIR, "orl_index.faiss")
CHUNKS_PATH = os.path.join(BOOKS_DIR, "orl_chunks.pkl")
META_PATH   = os.path.join(BOOKS_DIR, "orl_meta.pkl")   # guarda de qual livro vem cada chunk
MODEL_NAME  = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
CHUNK_SIZE    = 600   # aumentado para melhor contexto
CHUNK_OVERLAP = 100
# Arquivos a ignorar (nao sao livros)
IGNORAR = {"indexar_livro.py", "perguntar.py"}
# -----------------------------------------------------------------------------

def listar_pdfs(pasta: str) -> list[str]:
    """Retorna lista de PDFs na pasta, ignorando scripts."""
    pdfs = []
    for f in sorted(os.listdir(pasta)):
        if f.endswith(".pdf") and f not in IGNORAR:
            pdfs.append(os.path.join(pasta, f))
    return pdfs


def extrair_texto_pdf(caminho: str) -> list[str]:
    """Extrai texto de todas as paginas do PDF."""
    nome = os.path.basename(caminho)
    print(f"\n  [LENDO] {nome}")
    paginas = []
    try:
        with open(caminho, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            total = len(reader.pages)
            print(f"  -> Total de paginas: {total}")
            for i, page in enumerate(reader.pages):
                try:
                    texto = page.extract_text() or ""
                    texto = texto.strip()
                    if texto:
                        paginas.append(texto)
                except Exception as ex_page:
                    print(f"  [AVISO] Ignorando pagina {i+1} corrompida: {ex_page}")
                if (i + 1) % 100 == 0:
                    print(f"  -> Lidas: {i+1}/{total}")
        print(f"  [OK] Paginas com texto extraido: {len(paginas)}/{total}")
    except Exception as e:
        print(f"  [ERRO] Falha ao ler {nome}: {e}")
    return paginas


def criar_chunks(paginas: list[str], chunk_size: int, overlap: int, fonte: str) -> tuple[list[str], list[str]]:
    """Divide o texto em pedacos menores. Retorna (chunks, metadados_fonte)."""
    texto_completo = "\n".join(paginas)
    chunks = []
    metas  = []
    inicio = 0
    while inicio < len(texto_completo):
        fim   = inicio + chunk_size
        chunk = texto_completo[inicio:fim].strip()
        if chunk:
            chunks.append(chunk)
            metas.append(fonte)
        inicio += chunk_size - overlap
    return chunks, metas


def gerar_embeddings(chunks: list[str], model_name: str):
    """Gera embeddings para todos os chunks."""
    print(f"\n[MODELO] {model_name}")
    modelo = SentenceTransformer(model_name)
    print(f"Gerando embeddings para {len(chunks)} chunks (CPU — pode demorar)...")
    embeddings = modelo.encode(
        chunks,
        show_progress_bar=True,
        batch_size=32,
        convert_to_numpy=True
    )
    return np.array(embeddings, dtype="float32")


def main():
    if not os.path.exists(BIBLIOTECA_DIR):
        os.makedirs(BIBLIOTECA_DIR)
        
    pdfs = listar_pdfs(BIBLIOTECA_DIR)
    if not pdfs:
        print("[ERRO] Nenhum PDF encontrado na pasta books/biblioteca/")
        return

    print(f"=== OTTO ORL — Indexador Multi-Livro (v2) ===")
    print(f"Livros encontrados: {len(pdfs)}")
    for p in pdfs:
        print(f"  - {os.path.basename(p)}")

    # Se ja existir indice, perguntar se quer reindexar
    if os.path.exists(INDEX_PATH) and os.path.exists(CHUNKS_PATH):
        print(f"\n[AVISO] Indice existente encontrado ({INDEX_PATH})")
        print("Delete os arquivos orl_index.faiss, orl_chunks.pkl e orl_meta.pkl para reindexar.")
        return

    # Processar todos os PDFs
    todos_chunks = []
    todos_metas  = []

    for pdf_path in pdfs:
        nome   = os.path.basename(pdf_path)
        paginas = extrair_texto_pdf(pdf_path)
        if not paginas:
            continue
        chunks, metas = criar_chunks(paginas, CHUNK_SIZE, CHUNK_OVERLAP, fonte=nome)
        todos_chunks.extend(chunks)
        todos_metas.extend(metas)
        print(f"  -> {len(chunks)} chunks gerados de '{nome}'")

    print(f"\n[TOTAL] {len(todos_chunks)} chunks de {len(pdfs)} livros")

    # Gerar embeddings unificados
    embeddings = gerar_embeddings(todos_chunks, MODEL_NAME)

    # Criar e salvar indice FAISS
    dim   = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings)
    print(f"\n[OK] Indice FAISS: {index.ntotal} vetores (dim={dim})")

    faiss.write_index(index, INDEX_PATH)
    with open(CHUNKS_PATH, "wb") as f:
        pickle.dump(todos_chunks, f)
    with open(META_PATH, "wb") as f:
        pickle.dump(todos_metas, f)

    print(f"[OK] Salvo: {INDEX_PATH}")
    print(f"[OK] Salvo: {CHUNKS_PATH}")
    print(f"[OK] Salvo: {META_PATH}")
    print(f"\n[PRONTO] Execute: python books/perguntar.py")


if __name__ == "__main__":
    main()
