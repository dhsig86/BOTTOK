# -*- coding: utf-8 -*-
"""
perguntar.py  (v2 — multi-livro + citacao de fonte)
====================================================
Consulta clinica ao acervo ORL indexado.
Funciona 100% offline, sem GPU. Pergunta em portugues, busca em qualquer idioma.

Uso:
    python books/perguntar.py
    python books/perguntar.py --pergunta "Criterios para indicacao de amigdalectomia"
    python books/perguntar.py --topn 5 --pergunta "Colesteatoma conduta cirurgica"
    python books/perguntar.py --traduzir   (tenta traduzir os trechos p/ pt-BR via Google)
"""

import os
import sys
import pickle
import argparse
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss

# Forcar saida UTF-8 no terminal Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# --- Configuracoes -----------------------------------------------------------
INDEX_PATH  = os.path.join(os.path.dirname(__file__), "orl_index.faiss")
CHUNKS_PATH = os.path.join(os.path.dirname(__file__), "orl_chunks.pkl")
META_PATH   = os.path.join(os.path.dirname(__file__), "orl_meta.pkl")
MODEL_NAME  = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
TOPN_DEFAULT = 4
# -----------------------------------------------------------------------------

BANNER = """
+--------------------------------------------------------------+
|   OTTO ORL - Consulta ao Acervo de Livros (v2)              |
|   Livros: Decision-Making, CURRENT Dx&Tx, Advanced ENT,     |
|           Logica Diagnostica ORL                             |
|   Modo: busca semantica multilingue (pt/en) - 100% local    |
+--------------------------------------------------------------+
Digite 'sair' para encerrar.
"""


def carregar_indice():
    """Carrega indice FAISS, chunks e metadados."""
    if not os.path.exists(INDEX_PATH) or not os.path.exists(CHUNKS_PATH):
        print("[ERRO] Indice nao encontrado. Execute primeiro:")
        print("   python books/indexar_livro.py")
        sys.exit(1)

    index = faiss.read_index(INDEX_PATH)
    with open(CHUNKS_PATH, "rb") as f:
        chunks = pickle.load(f)

    # Metadados de fonte (opcional — compativel com indice antigo)
    metas = None
    if os.path.exists(META_PATH):
        with open(META_PATH, "rb") as f:
            metas = pickle.load(f)

    print(f"[OK] {index.ntotal} trechos indexados de {len(set(metas)) if metas else '?'} livro(s).")
    return index, chunks, metas


def buscar(pergunta: str, index, chunks: list, metas, modelo, topn: int) -> list[dict]:
    """Busca semantica: retorna os chunks mais relevantes."""
    emb = modelo.encode([pergunta], convert_to_numpy=True).astype("float32")
    distancias, indices = index.search(emb, topn)
    resultados = []
    for j, i in enumerate(indices[0]):
        if i < len(chunks):
            resultados.append({
                "texto": chunks[i],
                "fonte": metas[i] if metas else "Desconhecido",
                "dist":  float(distancias[0][j])
            })
    return resultados


def tentar_traduzir(texto: str) -> str:
    """Tenta traduzir o texto para pt-BR usando deep-translator."""
    try:
        from deep_translator import GoogleTranslator
        t = GoogleTranslator(source='auto', target='pt').translate(texto[:4500])
        return t or texto
    except ImportError:
        return "[Para traducao: pip install deep-translator]\n\n" + texto
    except Exception as e:
        return f"[Erro na traducao: {e}]\n\n" + texto


def formatar_resultado(pergunta: str, resultados: list[dict], traduzir: bool) -> str:
    """Formata a saida de forma legivel e clinica."""
    sep = "=" * 62
    sep2 = "-" * 62
    linhas = [f"\n{sep}"]
    linhas.append(f"PERGUNTA: {pergunta}")
    linhas.append(sep)
    linhas.append("")

    for i, r in enumerate(resultados, start=1):
        # Score visual aproximado (menor distancia = mais relevante)
        # L2 distance: ~0 = identico, >100 = pouco relevante
        score = max(0, round(100 - r['dist'] * 8))
        fonte = r['fonte']
        # Encurtar nome do arquivo para exibicao
        fonte_curta = fonte[:55] + "..." if len(fonte) > 55 else fonte
        linhas.append(f"[{i}] Fonte: {fonte_curta}  |  Score: {score}%")
        linhas.append(sep2)

        texto = r["texto"].strip()
        if traduzir:
            print(f"  Traduzindo trecho {i}...", end=" ", flush=True)
            texto = tentar_traduzir(texto)
            print("OK")

        linhas.append(texto)
        linhas.append("")

    linhas.append(sep2)
    if traduzir:
        linhas.append("Traducao automatica (Google Translate) - Use como referencia.")
    else:
        linhas.append("Trechos em ingles do original. Use --traduzir para versao pt-BR.")
    linhas.append("Valide sempre com diretrizes atualizadas e julgamento clinico.")
    linhas.append(sep2 + "\n")
    return "\n".join(linhas)


def loop_interativo(index, chunks, metas, modelo, topn: int, traduzir: bool):
    print(BANNER)
    while True:
        try:
            pergunta = input("Pergunta clinica: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nEncerrando. Ate logo!")
            break

        if not pergunta:
            continue
        if pergunta.lower() in ("sair", "exit", "quit", "q"):
            print("Encerrando. Ate logo!")
            break

        resultados = buscar(pergunta, index, chunks, metas, modelo, topn)
        print(formatar_resultado(pergunta, resultados, traduzir))


def main():
    parser = argparse.ArgumentParser(description="Consulta ORL ao acervo indexado")
    parser.add_argument("--pergunta", type=str, default=None,
                        help="Pergunta clinica (modo nao-interativo)")
    parser.add_argument("--topn", type=int, default=TOPN_DEFAULT,
                        help=f"Numero de trechos a retornar (padrao: {TOPN_DEFAULT})")
    parser.add_argument("--traduzir", action="store_true",
                        help="Traduzir trechos para pt-BR via Google Translate (requer internet)")
    args = parser.parse_args()

    print("Carregando indice...")
    index, chunks, metas = carregar_indice()

    print("Carregando modelo de embeddings...")
    modelo = SentenceTransformer(MODEL_NAME)
    print("Modelo pronto.\n")

    if args.pergunta:
        resultados = buscar(args.pergunta, index, chunks, metas, modelo, args.topn)
        print(formatar_resultado(args.pergunta, resultados, args.traduzir))
    else:
        loop_interativo(index, chunks, metas, modelo, args.topn, args.traduzir)


if __name__ == "__main__":
    main()
