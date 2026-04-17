# 🚀 Como rodar a Vectorização da Biblioteca Medica no Kaggle

Criamos com sucesso o arquivo compactado da sua biblioteca! Ele se chama **`biblioteca.zip`** e está localizado na pasta `books\` do nosso GPT (MEDICAL GPT/books/biblioteca.zip).

Siga os passos abaixo, que foram desenhados para que o processamento aproveite as GPUs violentas e gratuitas (placas de vídeo) do Kaggle.

### 1. Preparar o Ambiente Kaggle
1. Acesse [kaggle.com](https://www.kaggle.com/) (suponho que você já possua conta/login, caso não, crie).
2. Na barra lateral esquerda (ou na home), clique no botão **Create** -> **New Dataset**.
3. Dê o título "Biblioteca ORL" e faça o upload do arquivo `books/biblioteca.zip` que acabou de ser criado.
4. Clique em **Create** (pode levar 1 ou 2 minuntos para ele processar).

### 2. Criar e Configurar o Caderno (Notebook)
1. Depois que o Dataset abrir e validar, na página do Dataset haverá um botão lá no alto à direita chamado **"New Notebook"**. Clique nele.
2. Com o seu novo caderno (notebook) aberto, no canto superior direito existe uma aba/sessão chamada de **Session Options** ou três pontinhos que revelam as opções do Notebook (Geralmente no painel vertical à direita, em "Notebook options" -> **Accelerator**).
3. **MUITO IMPORTANTE:** Em "Accelerator", mude de "None" para **"GPU T4 x2"** ou **"GPU P100"** e ligue o ambiente. (É isso que vai deixar o processo milhares de vezes mais rápido sem travar a sua máquina).

### 3. Rodar a Magia
Copie CÓDIGO INTEIRO Mágico abaixo e cole no primeiro bloco (célula) que aparece no Notebook, apagando qualquer coisa que o Kaggle colocar de exemplo. 
Em seguida, clique no botão de "Play" ao lado do código (ou aperte `Shift + Enter`).

```python
!pip install -q pymupdf sentence-transformers faiss-cpu

import os
import pickle
import fitz  # PyMuPDF
import re
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

# Configurações do ambiente Kaggle
INPUT_DIR = "/kaggle/input"
WORKING_DIR = "/kaggle/working"

INDEX_PATH  = os.path.join(WORKING_DIR, "orl_index.faiss")
CHUNKS_PATH = os.path.join(WORKING_DIR, "orl_chunks.pkl")
META_PATH   = os.path.join(WORKING_DIR, "orl_meta.pkl")
MODEL_NAME  = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
CHUNK_MAX_SIZE  = 1600
CHUNK_OVERLAP   = 300

def list_pdfs(pasta):
    pdfs = []
    # Busca por toda a pasta Input independente do nome do Dataset
    for root, dirs, files in os.walk(pasta):
        for f in files:
            if f.lower().endswith(".pdf"):
                pdfs.append(os.path.join(root, f))
    return sorted(pdfs)

def limpar_texto(texto: str) -> str:
    # Hífens de quebra de linha: "diag-\nnóstico" -> "diagnóstico"
    texto = re.sub(r'­\s*\n\s*', '', texto)
    texto = re.sub(r'-\s*\n\s*([a-záéíóúãõ])', r'\1', texto)
    # Detecta padrão de caracteres separados por espaço simples: "d i a g n ó s t i c o"
    if re.search(r'(\b\S{1,2} ){5,}', texto):
        texto = re.sub(r'\b(\w) (\w) (\w)', r'\1\2\3', texto)
        texto = re.sub(r'\b(\w) (\w)\b', r'\1\2', texto)
    # Múltiplas quebras viram parágrafo isolado
    texto = re.sub(r'\n{3,}', '\n\n', texto)
    # Quebras de linha isoladas viram espaço normal (não quebra a frase ao meio)
    texto = re.sub(r'(?<!\n)\n(?!\n)', ' ', texto)
    # Múltiplos espaços viram espaço normal
    texto = re.sub(r'[ \t]{2,}', ' ', texto)
    return texto.strip()

def extrair_texto_pdf(caminho):
    nome = os.path.basename(caminho)
    print(f"[LENDO] {nome}")
    paginas = []
    try:
        pdf_document = fitz.open(caminho)
        for page_num in range(len(pdf_document)):
            page = pdf_document.load_page(page_num)
            texto = page.get_text("text") or ""
            texto = limpar_texto(texto)
            if texto:
                paginas.append(texto)
        pdf_document.close()
    except Exception as e:
        print(f"[ERRO] Falha ao ler {nome}: {e} (Tentando ignoar artefacto corrompido)")
    return paginas

def criar_chunks_inteligentes(paginas, max_size, overlap, fonte):
    texto_completo = "\n\n".join(paginas)
    paragrafos = re.split(r'\n\n+', texto_completo)
    
    chunks = []
    metas = []
    bloco_atual = ""
    
    for para in paragrafos:
        para = para.strip()
        if not para:
            continue
            
        if len(para) > max_size:
            # Dividir paragrafo monstruoso por pontos
            frases = re.split(r'(?<=[.!?])\s+', para)
            for frase in frases:
                if len(bloco_atual) + len(frase) <= max_size:
                    bloco_atual += (" " + frase if bloco_atual else frase)
                else:
                    if bloco_atual:
                        chunks.append(bloco_atual.strip())
                        metas.append(fonte)
                    bloco_atual = frase
            continue
            
        if len(bloco_atual) + len(para) <= max_size:
            bloco_atual += ("\n\n" + para if bloco_atual else para)
        else:
            chunks.append(bloco_atual.strip())
            metas.append(fonte)
            # Para o overlap de parágrafo estrutural, usamos o bloco que ultrapassou o limite como o início (frequentemente com 200 a 400 chars)
            bloco_atual = para
            
    if bloco_atual:
        chunks.append(bloco_atual.strip())
        metas.append(fonte)
        
    return chunks, metas

print("1. Mapeando PDFs vindos do seu Dataset...")
pdfs = list_pdfs(INPUT_DIR)
print(f"Total Encontrado: {len(pdfs)} Livros e Arquivos Médicos\n")

if len(pdfs) == 0:
    print("Nenhum PDF encontrado! Verifique se você subiu o Dataset corretamente.")
else:
    todos_chunks = []
    todos_metas = []
    for pdf in pdfs:
         paginas = extrair_texto_pdf(pdf)
         if paginas:
             chunks, metas = criar_chunks_inteligentes(paginas, CHUNK_MAX_SIZE, CHUNK_OVERLAP, os.path.basename(pdf))
             todos_chunks.extend(chunks)
             todos_metas.extend(metas)
             
    print(f"\n[INFO] {len(todos_chunks)} blocos médicos criados com semântica robusa.")
    
    print("\n2. 🔥 ACENDENDO MOTORES DA GPU PARA GERAR OS VETORES (EMBEDDINGS)...")
    # Usa a GPU alocada pelo Kaggle
    modelo = SentenceTransformer(MODEL_NAME)
    embeddings = modelo.encode(todos_chunks, show_progress_bar=True, batch_size=64, convert_to_numpy=True)
    embeddings = np.array(embeddings, dtype="float32")
    
    print("\n3. Consolidando Matriz de Conhecimento (FAISS Index)...")
    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings)
    
    faiss.write_index(index, INDEX_PATH)
    with open(CHUNKS_PATH, "wb") as f:
        pickle.dump(todos_chunks, f)
    with open(META_PATH, "wb") as f:
        pickle.dump(todos_metas, f)
        
    print("\n🎉 [SUCESSO ABSOLUTO] CÉREBRO GERADO COM SUCESSO!")
    print("Na aba direta lateral do seu Notebook Kaggle -> Sessão 'Output' -> '/kaggle/working'")
    print("Você encontrará 3 arquivos:")
    print("- orl_index.faiss")
    print("- orl_chunks.pkl")
    print("- orl_meta.pkl")
    print("Baixe-os clicando nos 'três pontinhos' > Download, e mova para a nossa pasta 'books/'.")
```

### 4. Última Etapa
No menu direito do notebook Kaggle, há uma aba **"Output"**. Ali estão os seus **três arquivos de cérebro** (`.faiss` e dois `.pkl`). Você faz o download deles para o seu computador, joga-os dentro da pasta `books\` do GPT e pronto! O sistema local vai ler os arquivos já mastigados, poupando a sua memória local!
