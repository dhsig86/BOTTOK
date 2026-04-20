# -*- coding: utf-8 -*-
"""
indexar_livro.py  (v3 — multi-livro e chunking semântico)
=========================================================
Escaneia TODOS os PDFs da pasta books/ e cria um indice vetorial unificado.
Usa limpeza Regex, chunking semantico (respeita quebras de frase) 
e tamanho maximo de 1600 caracteres para RAG profundo.

Para re-indexar do zero, delete:
  - orl_index.faiss
  - orl_chunks.pkl

Uso:
    python books/indexar_livro.py
"""

import os
import sys
import pickle
import fitz # PyMuPDF
import re
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

# Usando MiniLM-L12-v2 para garantir compatibilidade de memória (Evitar crash do backend)
MODEL_NAME  = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2" 
CHUNK_MAX_SIZE = 1800   # Aumentado para melhor contexto.
CHUNK_OVERLAP  = 400
# Arquivos a ignorar (nao sao livros ou estão corrompidos gerando C-Level SegFault)
IGNORAR = {
    "indexar_livro.py", 
    "perguntar.py",
    "Endoscopic dacryocystorhinostomy _DCR_ surgical technique.pdf"
}
# -----------------------------------------------------------------------------

def listar_pdfs(pasta: str) -> list[str]:
    """Retorna lista de PDFs na pasta, ignorando scripts."""
    pdfs = []
    for f in sorted(os.listdir(pasta)):
        if f.endswith(".pdf") and f not in IGNORAR:
            pdfs.append(os.path.join(pasta, f))
    return pdfs

def limpar_texto(texto: str) -> str:
    # Hífens de quebra de linha: "diag-\nnóstico" -> "diagnóstico"
    texto = re.sub(r'-\s*\n\s*([a-záéíóúãõ])', r'\1', texto)
    texto = re.sub(r'­\s*\n\s*', '', texto)
    # Detecta padrão de caracteres separados por espaço simples: "d i a g n ó s t i c o"
    if re.search(r'(\b\S{1,2} ){5,}', texto):
        texto = re.sub(r'\b(\w) (\w) (\w)', r'\1\2\3', texto)
        texto = re.sub(r'\b(\w) (\w)\b', r'\1\2', texto)
    # Múltiplas quebras viram parágrafo isolado
    texto = re.sub(r'\n{3,}', '\n\n', texto)
    # Quebras de linha isoladas viram espaço normal
    texto = re.sub(r'(?<!\n)\n(?!\n)', ' ', texto)
    # Múltiplos espaços viram espaço normal
    texto = re.sub(r'[ \t]{2,}', ' ', texto)
    return texto.strip()

def extrair_texto_pdf(caminho: str) -> list[str]:
    """Extrai texto de todas as paginas do PDF."""
    nome = os.path.basename(caminho)
    print(f"\n  [LENDO] {nome}")
    paginas = []
    try:
        pdf_document = fitz.open(caminho)
        total = len(pdf_document)
        print(f"  -> Total de paginas: {total}")
        for page_num in range(total):
            try:
                page = pdf_document.load_page(page_num)
                texto = page.get_text("text") or ""
                texto = limpar_texto(texto)
                if texto:
                    paginas.append(texto)
            except Exception as ex_page:
                print(f"  [AVISO] Ignorando pagina {page_num+1} corrompida: {ex_page}")
            if (page_num + 1) % 100 == 0:
                print(f"  -> Lidas: {page_num+1}/{total}")
        pdf_document.close()
        print(f"  [OK] Paginas com texto extraido: {len(paginas)}/{total}")
    except Exception as e:
        print(f"  [ERRO] Falha ao ler {nome}: {e}")
    return paginas

def criar_chunks_inteligentes(paginas: list[str], max_size: int, overlap: int, fonte: str) -> tuple[list[str], list[str]]:
    """Divide o texto com quebras semanticas. Retorna (chunks, metadados_fonte)."""
    texto_completo = "\n\n".join(paginas)
    paragrafos = re.split(r'\n\n+', texto_completo)
    
    chunks = []
    metas = []
    
    # Injeta a fonte como base do contexto no chunk atual
    prefixo_fonte = f"[LIVRO-TEXTO: {fonte.replace('.pdf', '')}] "
    bloco_atual = prefixo_fonte
    
    for para in paragrafos:
        para = para.strip()
        if not para:
            continue
            
        if len(para) > max_size:
            # Dividir paragrafo monstruoso por pontos
            frases = re.split(r'(?<=[.!?])\s+', para)
            for frase in frases:
                if len(bloco_atual) + len(frase) <= max_size:
                    bloco_atual += (" " + frase)
                else:
                    if bloco_atual.strip() != prefixo_fonte.strip():
                        chunks.append(bloco_atual.strip())
                        metas.append(fonte)
                    bloco_atual = prefixo_fonte + frase
            continue
            
        if len(bloco_atual) + len(para) <= max_size:
            bloco_atual += ("\n\n" + para if bloco_atual != prefixo_fonte else para)
        else:
            if bloco_atual.strip() != prefixo_fonte.strip():
                chunks.append(bloco_atual.strip())
                metas.append(fonte)
            # overlap estrutural injeta a fonte de novo
            bloco_atual = prefixo_fonte + para
            
    if bloco_atual.strip() != prefixo_fonte.strip():
        chunks.append(bloco_atual.strip())
        metas.append(fonte)
        
    return chunks, metas

def gerar_embeddings(chunks: list[str], model_name: str):
    """Gera embeddings para todos os chunks."""
    print(f"\n[MODELO] {model_name}")
    modelo = SentenceTransformer(model_name)
    print(f"Gerando embeddings para {len(chunks)} chunks (CPU — pode demorar)...")
    # Pre-alocar array numpy de embeddings reduz o uso de memoria em 3x (Evita OOM)
    dim = 384 # Dimensao do MiniLM-L12
    total = len(chunks)
    embeddings = np.zeros((total, dim), dtype="float32")
    
    batch_size = 32
    for i in range(0, total, batch_size):
        batch = chunks[i:i+batch_size]
        batch_emb = modelo.encode(batch, show_progress_bar=False, convert_to_numpy=True)
        embeddings[i:i+len(batch)] = batch_emb
        if (i + len(batch)) % 128 == 0 or (i + len(batch)) >= total:
            print(f"  -> Vetores criados: {min(i+len(batch), total)} / {total}", flush=True)
            
    return np.array(embeddings, dtype="float32")

def main():
    if not os.path.exists(BIBLIOTECA_DIR):
        os.makedirs(BIBLIOTECA_DIR)
        
    pdfs = listar_pdfs(BIBLIOTECA_DIR)
    if not pdfs:
        print("[ERRO] Nenhum PDF encontrado na pasta books/biblioteca/")
        return

    print(f"=== OTTO ORL — Indexador Multi-Livro (v3 Semântico) ===")
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
        chunks, metas = criar_chunks_inteligentes(paginas, CHUNK_MAX_SIZE, CHUNK_OVERLAP, fonte=nome)
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
    print(f"\n[PRONTO] Sistema Atualizado com Chunking Semântico!")

if __name__ == "__main__":
    main()
