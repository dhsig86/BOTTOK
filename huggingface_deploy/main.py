# -*- coding: utf-8 -*-
"""
api.py  — Servidor FastAPI para o OTTO ORL RAG (v3)
====================================================
Novidades v3:
- Limpeza de texto (corrige espaços entre caracteres de PDFs com fonts embutidas)
- Sintese via Ollama (local, sem API key) → auto-detecta se está rodando
- Sintese via Groq API (gratuita, requer GROQ_API_KEY no .env ou variavel de ambiente)
- MedicalGPT RAG Prompt adaptado para pt-BR

Uso:
    python books/api.py
    Acesse: http://localhost:8000
"""

import os
import re
import sys
import pickle
import httpx
import numpy as np
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager
from dotenv import load_dotenv

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Carrega o .env da pasta books/
load_dotenv(dotenv_path=Path(__file__).parent / ".env")

# --- Paths -------------------------------------------------------------------
BASE_DIR    = Path(__file__).parent
INDEX_PATH  = BASE_DIR / "orl_index.faiss"
CHUNKS_PATH = BASE_DIR / "orl_chunks.pkl"
META_PATH   = BASE_DIR / "orl_meta.pkl"
MODEL_NAME  = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
# LLM config
OLLAMA_URL  = "http://localhost:11434"
OLLAMA_MODEL = "phi3:mini"          # troque por llama3.2:3b se preferir
GROQ_KEY   = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.1-8b-instant"   # mais econômico e rápido do free tier Groq
# -----------------------------------------------------------------------------

# ── Prompts para LLM ─────────────────────────────────────────────────────────
# Persona fixa enviada como role 'system' — define QUEM o modelo é
SYSTEM_PROMPT = """Você é OTOCONSULT, um assistente de inteligência e suporte à decisão clínica especializado estritamente em Otorrinolaringologia.
Sua missão é responder à dúvida clínica formatando e sumarizando APENAS as informações enviadas pelo RAG no campo [REFERÊNCIAS INDEXADAS].

[DIRETRIZES FUNDAMENTAIS]:
1. TOM E POSTURA: Expresse-se como um médico especialista chefe formal, direto, sem saudações desnecessárias. Vá direto ao ponto. 
2. CITAÇÃO ESTRITA: É absolutamente proibido inventar diagnósticos, tratamentos ou citar literaturas que não estão listadas nas referências abaixo. Se a informação não constar explicitamente no contexto, declare com clareza: "Com base no acervo disponibilizado, não foi encontrada essa informação."
3. FOCO: Leia a pergunta e determine qual a necessidade (lista de diferenciais, procedimento cirúrgico, posologia). 
4. ESTRUTURA VISUAL: Responda usando Markdown limpo. Use listas de pontos (bullet points) ou formato estruturado sempre que possível para facilitar a leitura rápida de outro médico. Se houver alertas perigosos (Red Flags), use **[ALERTA CLÍNICO]**.

[DADOS]
Baseie toda e qualquer afirmação unicamente nas evidências expostas abaixo. Sintentize, mas nunca extrapole."""

# Template enviado como role 'user' — define O QUE processar
USER_TEMPLATE = """REFERÊNCIAS INDEXADAS:
{context}

PERGUNTA CLÍNICA: {pergunta}"""

state = {
    "index":  None,
    "chunks": None,
    "metas":  None,
    "modelo": None,
    "pronto": False,
    "erro":   None,
    "llm_mode": None,  # "ollama" | "groq" | "none"
}


# ── Limpeza de texto ─────────────────────────────────────────────────────────
def limpar_texto(texto: str) -> str:
    """
    Corrige artefatos comuns de extração PDF:
    - 'p a l a v r a' → 'palavra' (fonts embutidas com espaçamento individual)
    - Hífens no fim de linha que quebram palavras
    - Múltiplos espaços e quebras de linha excessivas
    """
    # Detecta padrão de caracteres separados por espaço simples: "d i a g n ó s t i c o"
    # (>= 5 grupos de 1-2 chars seguidos de espaço)
    if re.search(r'(\b\S{1,2} ){5,}', texto):
        # Remove espaços entre caracteres isolados
        texto = re.sub(r'(?<=\S) (?=\S)', lambda m: '' if
                       all(len(w) <= 2 for w in texto[max(0, texto.index(m.group())-10):texto.index(m.group())+10].split())
                       else ' ', texto)
        # Abordagem mais agressiva para o padrão claro
        texto = re.sub(r'\b(\w) (\w) (\w)', r'\1\2\3', texto)
        texto = re.sub(r'\b(\w) (\w)\b', r'\1\2', texto)

    # Hífens de quebra de linha: "diag-\nnóstico" → "diagnóstico"
    texto = re.sub(r'­\s*\n\s*', '', texto)
    texto = re.sub(r'-\s*\n\s*([a-záéíóúãõ])', r'\1', texto)

    # Múltiplas quebras → parágrafo
    texto = re.sub(r'\n{3,}', '\n\n', texto)

    # Múltiplos espaços
    texto = re.sub(r'[ \t]{2,}', ' ', texto)

    return texto.strip()


# ── LLM Detection ────────────────────────────────────────────────────────────
async def detectar_llm() -> str:
    """Detecta qual LLM está disponível: ollama > groq > none."""
    # Testa Ollama
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{OLLAMA_URL}/api/tags")
            if r.status_code == 200:
                modelos = [m["name"] for m in r.json().get("models", [])]
                if modelos:
                    state["llm_mode"] = "ollama"
                    print(f"[LLM] Ollama detectado. Modelos: {modelos}")
                    return "ollama"
    except Exception:
        pass

    # Testa Groq
    if GROQ_KEY:
        state["llm_mode"] = "groq"
        print("[LLM] Groq API configurada.")
        return "groq"

    state["llm_mode"] = "none"
    print("[LLM] Nenhum LLM disponivel. Retornando trechos brutos limpos.")
    return "none"


# ── Síntese LLM ──────────────────────────────────────────────────────────────
async def sintetizar_ollama(contexto: str, pergunta: str) -> str:
    """Chama Ollama local via /api/chat com roles system/user."""
    user_content = USER_TEMPLATE.format(context=contexto, pergunta=pergunta)
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(f"{OLLAMA_URL}/api/chat", json={
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_content},
            ],
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 1024},
        })
        r.raise_for_status()
        return r.json()["message"]["content"].strip()


async def sintetizar_groq(contexto: str, pergunta: str) -> str:
    """Chama Groq API com roles system/user separados corretamente."""
    print(f"[LLM] Solicitando sintese ao Groq (Modelo: {GROQ_MODEL})...")
    user_content = USER_TEMPLATE.format(context=contexto, pergunta=pergunta)
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": user_content},
                ],
                "temperature": 0.1,
                "max_tokens": 1024,
                "top_p": 0.9,
            }
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()


async def sintetizar(pergunta: str, trechos: list[dict]) -> str | None:
    """Monta o contexto RAG e despacha para o LLM disponível."""
    if state["llm_mode"] == "none":
        return None

    contexto = "\n\n".join(
        f"[Ref {i+1} — {t['fonte'].split('.')[0]}]\n{t['texto']}"
        for i, t in enumerate(trechos)
    )

    try:
        if state["llm_mode"] == "ollama":
            return await sintetizar_ollama(contexto, pergunta)
        elif state["llm_mode"] == "groq":
            return await sintetizar_groq(contexto, pergunta)
    except Exception as e:
        print(f"[LLM] Erro na sintese: {e}")
        return None


# ── Startup ──────────────────────────────────────────────────────────────────
def carregar_tudo():
    import faiss
    from sentence_transformers import SentenceTransformer
    from collections import Counter
    import time

    print("[STARTUP] Iniciando carregamento do index FAISS para Otorrinolaringologia...")
    start_time = time.time()
    
    if not INDEX_PATH.exists() or not CHUNKS_PATH.exists():
        state["erro"] = "Indice nao encontrado. Execute indexar_livro.py primeiro."
        return

    print("[STARTUP] Lendo arquivo orl_index.faiss (Pode demorar dependendo do tamanho)...")
    state["index"] = faiss.read_index(str(INDEX_PATH))
    
    print("[STARTUP] Lendo pickles base (orl_chunks.pkl e orl_meta.pkl)...")
    with open(CHUNKS_PATH, "rb") as f:
        state["chunks"] = pickle.load(f)
    if META_PATH.exists():
        with open(META_PATH, "rb") as f:
            state["metas"] = pickle.load(f)

    if state["metas"]:
        n_livros = len(set(state["metas"]))
        print(f"[STARTUP] Distribuicao de chunks por livro/fonte:")
        distribuicao = Counter(state["metas"])
        for fonte, qtd in distribuicao.most_common():
            print(f"  - {fonte}: {qtd} chunks")
    else:
        n_livros = "?"
        
    print(f"[STARTUP] TOTAL CARREGADO: {state['index'].ntotal} chunks de {n_livros} livro(s).")
    print(f"[STARTUP] Carregando modelo NLP '{MODEL_NAME}' para embeddings de query...")
    
    state["modelo"] = SentenceTransformer(MODEL_NAME)
    state["pronto"] = True
    
    elapsed = time.time() - start_time
    print(f"[STARTUP] Sistema 100% pronto em {elapsed:.2f} segundos!")


@asynccontextmanager
async def lifespan(app: FastAPI):
    carregar_tudo()
    await detectar_llm()
    yield


# ── FastAPI App ───────────────────────────────────────────────────────────────
app = FastAPI(title="OTTO ORL API", version="3.0 - Vercel Ready", lifespan=lifespan)

# Restringindo CORS: Habilitando localhost (dev) e urls de Vercel/Render
CORS_ORIGINS = [
    "http://127.0.0.1:5500",
    "http://localhost:5500",
    "http://localhost:3000",
    "http://localhost:8000",
    "*"  # TODO: Trocar '*' pela url definitiva do Vercel quando for publicado
]

app.add_middleware(
    CORSMiddleware, 
    allow_origins=CORS_ORIGINS, 
    allow_methods=["*"], 
    allow_headers=["*"]
)


# ── Schemas ───────────────────────────────────────────────────────────────────
class ConsultaRequest(BaseModel):
    pergunta: str
    topn: int = 6
    sintetizar: bool = True


class TrechoResult(BaseModel):
    ordem: int
    texto: str
    fonte: str
    score: int


class ConsultaResponse(BaseModel):
    pergunta: str
    sintese: str | None       # resposta gerada pelo LLM (None se sem LLM)
    llm_usado: str            # "ollama" | "groq" | "none"
    resultados: list[TrechoResult]
    total_chunks: int
    n_livros: int


# ── Rotas ─────────────────────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
async def root():
    return JSONResponse({
        "status": "OTTO ORL API (Fase 2)",
        "mensagem": "Servidor backend independente. Acesse a interface Frontend pelo Vercel ou via Live Server.",
        "docs": "/docs"
    })


@app.get("/status")
async def status():
    if state["erro"]:
        return {"pronto": False, "erro": state["erro"]}
    if not state["pronto"]:
        return {"pronto": False, "mensagem": "Carregando..."}
    livros = list(set(state["metas"])) if state["metas"] else []
    return {
        "pronto": True,
        "total_chunks": state["index"].ntotal,
        "n_livros": len(livros),
        "livros": livros,
        "llm_mode": state["llm_mode"],
    }


@app.post("/buscar", response_model=ConsultaResponse)
async def buscar(req: ConsultaRequest):
    if not state["pronto"]:
        raise HTTPException(503, "Sistema carregando.")
    if not req.pergunta.strip():
        raise HTTPException(400, "Pergunta vazia.")

    topn = max(1, min(req.topn, 12))
    emb  = state["modelo"].encode([req.pergunta], convert_to_numpy=True).astype("float32")
    dists, idxs = state["index"].search(emb, topn)

    resultados = []
    for j, i in enumerate(idxs[0]):
        if i < len(state["chunks"]):
            texto_limpo = limpar_texto(state["chunks"][i])
            score = max(0, round(100 - float(dists[0][j]) * 8))
            fonte = state["metas"][i] if state["metas"] else "Desconhecido"
            resultados.append(TrechoResult(ordem=j+1, texto=texto_limpo, fonte=fonte, score=score))

    # Síntese
    sintese = None
    if req.sintetizar and resultados:
        trechos_dict = [{"texto": r.texto, "fonte": r.fonte} for r in resultados]
        sintese = await sintetizar(req.pergunta, trechos_dict)

    return ConsultaResponse(
        pergunta=req.pergunta,
        sintese=sintese,
        llm_usado=state["llm_mode"] or "none",
        resultados=resultados,
        total_chunks=state["index"].ntotal,
        n_livros=len(set(state["metas"])) if state["metas"] else 0,
    )


if __name__ == "__main__":
    import uvicorn
    print("=" * 55)
    print("  OTTO ORL — Servidor RAG v3")
    print("  http://localhost:8000")
    print("  Docs: http://localhost:8000/docs")
    print("=" * 55)
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False, log_level="warning")
