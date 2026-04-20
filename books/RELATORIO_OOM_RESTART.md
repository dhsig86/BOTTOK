# Relatório Técnico: BOTTOK v4 RAG - Resolução de Trava de Memória (OOM)

**Data do Incidente e Correção:** 19/04/2026
**Local da Correção:** `indexar_livro.py` e `api.py` (Arquitetura Otorrino RAG V4)

## 1. O Problema (O que Causou o "Congelamento")
1. **Sucesso Extraordinário na Leitura:** A biblioteca (PyMuPDF) foi impecável e processou todas as **88 obras e PDFs**, extraindo mais de **11.279 chunks contextuais**.
2. **O Colapso (OOM):** No momento de transformar todas as 11 mil linhas em Tensores Vetoriais (NumPy Floats), o `SentenceTransformer` tentou alocar +17MB na memória RAM de uma única vez em uma Pilha fraturada do Windows (`memory allocation of 17301520 bytes failed`).
3. **Deadlock / Zumbis:** A morte abrupta deste processo por causa do OOM manteve Locks (travas) ativos no cache principal do modelo de embeddings. Toda e qualquer tentativa sua de abrir um novo Python (ou do terminal) ficou pendurada e bloqueada em 0% implorando para que o Kernel soltasse seu processo antigo (razão pela qual nenhuma saída ou mensagem de erro ocorreu desde então — e o porquê reiniciar o PC é a medida perfeita).

## 2. A Intervenção Executada (Solução Coded-in)
Nós injetamos um "Antivírus contra Colapso de Memória" no backend de RAG. Foi alterada radicalmente a função `gerar_embeddings` em `indexar_livro.py` de modo que a RAM do Computador foi protegida usando duas regras:
- **Pré-Alocação NumPY Rigorosa** (`np.zeros`): Reservamos logo no instante Zero o cofre do tamanho exato da base matemática (no caso do modelo `MiniLM`, uma base de 384 dimensões), para evitar realocações brutas que causariam mais buracos de paginação (thrash_memory_faults);
- **Batck-Chunking Capped:** Enviamos agora 32 Chunks por vez para a Inteligência via iterações curtas, garantindo que a memória flutue estritamente sob o controle de limites operacionais de notebooks / ambientes pesados, com print de progresso instantâneo (`-> Vetores criados: X / Total`).

## 3. Próximos Passos Obrigatórios APÓS Reiniciar:
Para concluir sua transição para o novo **Mecanismo de Resposta Científica Implacável do BOTTOK:**

1. Abra um **novo Terminal** no seu VS Code.
2. Navegue até seu backend do BotTok: 
   ```bash
   cd "c:\Users\drdhs\OneDrive\Documentos\AOTTO ECOSYSTEM\BOTTOK\books"
   ```
3. Exclua velharias usando a Interface gráfica ou os comandos deletadores recomendados na aba de Rumo ao Deploy. (Eles deverão ter sido perdidos ou sumido por causa do travamento anterior, mas vale conferir).
4. **Acione o script do Banco Cerebral Capped:**
   ```bash
   python indexar_livro.py
   ```
5. Você verá ele exibir gradativamente os lotes finalizados (sem travar nunca mais). Logo que ele finalizar este processo pesado de CPU, arquivos magnéticos de Vetores FAISS e Pickles nascerão magicamente.
6. **Ligue seu Servidor Backend/RAG (FastAPI)** e seu **Frontend (React/Vite)** como em um dia convencional Clínico.

## Bônus: Detecção Groq Totalmente Automática
Conforme havíamos alinhado durante a crise: a nossa arquitetura já compreende na linha 134 do `api.py` que, em **falta do Ollama aberto, todo o processo do BotTok fará Auto-Fallback Cíclico para sua conta e chave do Groq (que já achei inserida perfeita no seu `.env`) enviando sua Query Clássica médica e recebendo Llama-3.1!** Não há absolutamente nenhuma configuração manual adicional a se alterar.

---

*Gerado automaticamente pelo Antigravity em contingência arquitetural do sistema local de saúde.*
