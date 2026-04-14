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
!pip install -q PyPDF2 sentence-transformers faiss-cpu faiss-gpu

import os
import pickle
import PyPDF2
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
CHUNK_SIZE    = 600
CHUNK_OVERLAP = 100

def list_pdfs(pasta):
    pdfs = []
    # Busca por toda a pasta Input independente do nome do Dataset
    for root, dirs, files in os.walk(pasta):
        for f in files:
            if f.lower().endswith(".pdf"):
                pdfs.append(os.path.join(root, f))
    return sorted(pdfs)

def extrair_texto_pdf(caminho):
    nome = os.path.basename(caminho)
    print(f"[LENDO] {nome}")
    paginas = []
    try:
        with open(caminho, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                try:
                    texto = page.extract_text()
                    if texto:
                        paginas.append(texto.strip())
                except:
                    pass
    except Exception as e:
        print(f"[ERRO] Falha ao ler {nome}: {e}")
    return paginas

def criar_chunks(paginas, chunk_size, overlap, fonte):
    texto = "\n".join(paginas)
    chunks = []
    metas = []
    inicio = 0
    while inicio < len(texto):
        fim = inicio + chunk_size
        chunk = texto[inicio:fim].strip()
        if chunk:
            chunks.append(chunk)
            metas.append(fonte)
        inicio += chunk_size - overlap
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
             chunks, metas = criar_chunks(paginas, CHUNK_SIZE, CHUNK_OVERLAP, os.path.basename(pdf))
             todos_chunks.extend(chunks)
             todos_metas.extend(metas)
             
    print(f"\n[INFO] {len(todos_chunks)} blocos médicos criados.")
    
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
