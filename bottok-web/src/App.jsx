import { useState, useEffect, useRef } from 'react';
import './App.css';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const MarkdownComponents = {
  blockquote: ({ node, children, ...props }) => {
    const textContent = String(children).toUpperCase();
    if (textContent.includes('[!WARNING]') || textContent.includes('[!ALERTA]')) {
      return (
        <div className="clin-block clin-alerta">
          <div className="clin-block-title">🚨 ALERTA CLÍNICO</div>
          <div className="clin-block-content">{children}</div>
        </div>
      );
    }
    if (textContent.includes('[!NOTE]') || textContent.includes('[!NOTA]')) {
      return (
        <div className="clin-block clin-conduta">
          <div className="clin-block-title">📋 NOTA CLÍNICA</div>
          <div className="clin-block-content">{children}</div>
        </div>
      );
    }
    return <blockquote className="clin-blockquote" {...props}>{children}</blockquote>;
  },
  ul: ({node, children, ...props}) => <ul style={{ marginLeft: '16px', marginBottom: '8px' }} {...props}>{children}</ul>,
  li: ({node, children, ...props}) => <li style={{ marginBottom: '4px' }} {...props}>{children}</li>,
  p: ({node, children, ...props}) => <p style={{ marginBottom: '12px' }} {...props}>{children}</p>
};


function humanizarNome(nome) {
  return nome
    .replace(/\.pdf$/i, '')
    .replace(/_/g, ' ')
    .replace(/-/g, ' ')
    .replace(/\b\w/g, l => l.toUpperCase());
}

const TEMAS = [
  { n: '1', t: 'Assistente de Diagnóstico' },
  { n: '2', t: 'Tratamento de Infecção de Ouvido' },
  { n: '3', t: 'Doenças Nasais e Sinusais' },
  { n: '4', t: 'Distúrbios da Garganta' },
  { n: '5', t: 'Cirurgias Otorrinolaringológicas' },
  { n: '6', t: 'Audiologia e Perda Auditiva' },
  { n: '7', t: 'Vertigem e Desequilíbrio' },
  { n: '8', t: 'Alergias Nasais' },
  { n: '9', t: 'Sono e Apneia' },
  { n: '10', t: 'Câncer de Cabeça e Pescoço' },
  { n: '11', t: 'Voz e Fala' },
  { n: '12', t: 'Pediatria' },
  { n: '13', t: 'Plástica Facial' },
  { n: '14', t: 'Emergências' },
  { n: '15', t: 'Doenças Crônicas' },
  { n: '16', t: 'Implantes Cocleares' },
  { n: '17', t: 'Protocolos Conservadores' },
  { n: '18', t: 'Risco Cirúrgico' },
  { n: '19', t: 'Novas Tecnologias' },
  { n: '20', t: 'Atualizações ORL' },
];

const PROMPT_TEMPLATES = [
  {
    icon: '🔍',
    label: 'Diagnóstico Diferencial',
    text: 'Quais são os principais diagnósticos diferenciais para otalgia unilateral com otoscopia normal no adulto?',
  },
  {
    icon: '💊',
    label: 'Conduta Terapêutica',
    text: 'Qual o protocolo de tratamento para otite média aguda bacteriana em adulto sem comorbidades?',
  },
  {
    icon: '⚡',
    label: 'Emergência ORL',
    text: 'Qual a conduta imediata para epistaxe posterior refratária à compressão local?',
  },
  {
    icon: '🎯',
    label: 'Posologia',
    text: 'Qual a dose e duração do amoxicilina-clavulanato para sinusite bacteriana aguda?',
  },
  {
    icon: '🏥',
    label: 'Indicação Cirúrgica',
    text: 'Quais são as indicações de timpanoplastia e os critérios de sucesso cirúrgico?',
  },
  {
    icon: '👂',
    label: 'Audiologia',
    text: 'Como interpretar uma audiometria com rebaixamento bilateral em altas frequências e qual conduta?',
  },
];

export default function App() {
  const [status, setStatus] = useState({ state: 'carregando', error: null });
  const [stats, setStats] = useState({ total_chunks: '—', n_livros: '—', llm_mode: 'none', livros: [] });
  const [history, setHistory] = useState([]);
  const [query, setQuery] = useState('');
  const [contextoTema, setContextoTema] = useState(null);
  const [topn, setTopn] = useState(6);
  const [buscando, setBuscando] = useState(false);
  const [focused, setFocused] = useState(false);
  const resultsRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    verificarStatus();
  }, []);

  useEffect(() => {
    if (resultsRef.current) {
      resultsRef.current.scrollTop = resultsRef.current.scrollHeight;
    }
  }, [history, buscando]);

  const verificarStatus = async () => {
    try {
      const res = await fetch(`${API}/status`);
      const d = await res.json();
      if (d.pronto) {
        setStatus({ state: 'ok', error: null });
        setStats({
          total_chunks: d.total_chunks,
          n_livros: d.n_livros,
          llm_mode: d.llm_mode || 'none',
          livros: d.livros || []
        });
      } else {
        setStatus({ state: 'carregando', error: d.erro });
        setTimeout(verificarStatus, 2000);
      }
    } catch (e) {
      setStatus({ state: 'erro', error: 'Servidor offline' });
      setTimeout(verificarStatus, 3000);
    }
  };

  const ehPerguntaDeAcervo = (q) => {
    const p = q.toLowerCase();
    const termos = ['lista', 'livro', 'acervo', 'referência', 'referencia', 'base de dado',
      'quais livros', 'quais referência', 'que livros', 'que referência',
      'tem no banco', 'está indexado', 'contém', 'contem', 'disponível', 'disponivel'];
    return termos.some(t => p.includes(t));
  };

  const autoResize = (e) => {
    e.target.style.height = 'auto';
    e.target.style.height = Math.min(e.target.scrollHeight, 180) + 'px';
  };

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      buscar();
    }
  };

  const selecionarTema = (tema) => {
    setContextoTema(tema);
    setTimeout(() => inputRef.current?.focus(), 50);
  };

  const buscar = async () => {
    const pergunta = query.trim();
    if (!pergunta || buscando || status.state !== 'ok') return;

    setQuery('');
    if (inputRef.current) inputRef.current.style.height = 'auto';

    const finalQuestionText = contextoTema ? `[Tema: ${contextoTema.t}] ${pergunta}` : pergunta;
    const newQueryItem = { type: 'query', text: pergunta, temaVisual: contextoTema?.t };

    if (ehPerguntaDeAcervo(pergunta) && stats.livros.length > 0) {
      setHistory(prev => [...prev, newQueryItem, { type: 'acervo' }]);
      setTimeout(() => inputRef.current?.focus(), 100);
      return;
    }

    setHistory(prev => [...prev, newQueryItem]);
    setBuscando(true);

    try {
      const res = await fetch(`${API}/buscar`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pergunta: finalQuestionText, topn, sintetizar: true })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Erro na busca');

      setHistory(prev => [...prev, { type: 'response', data }]);
    } catch (e) {
      setHistory(prev => [...prev, { type: 'error', message: e.message }]);
    } finally {
      setBuscando(false);
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  };

  const getTipText = () => {
    const msgs = {
      ollama: <><p><strong>🤖 SÍNTESE VIA OLLAMA ATIVA</strong></p>A resposta sintetizada cita obrigatoriamente as referências de base lidas.</>,
      groq: <><p><strong>⚡ SÍNTESE VIA GROQ ATIVA</strong></p>As respostas são elaboradas considerando apenas os livros retornados na busca.</>,
      none: <><p><strong>📚 MODO REFERÊNCIAS BRUTO</strong></p>Nenhum gerador ativo. Exibindo apenas trechos extraídos em ordem de relevância.</>,
    };
    return msgs[stats.llm_mode] || msgs.none;
  };

  const renderRefs = (resultados) => {
    return (
      <div className="refs-card-wrapper">
        <details>
          <summary className="refs-toggle" style={{ listStyle: 'none' }}>
            <span className="refs-toggle-label">📖 Referências dos Livros ({resultados.length})</span>
            <span className="refs-toggle-icon">▼</span>
          </summary>
          <div className="refs-list" style={{ marginTop: '10px' }}>
            {resultados.map((r, i) => {
              const sc = r.score >= 60 ? 'score-high' : r.score >= 35 ? 'score-medium' : 'score-low';
              const ft = r.fonte.length > 50 ? r.fonte.slice(0, 48) + '…' : r.fonte;
              return (
                <div key={i} className="result-card">
                  <div className="card-header">
                    <div className="card-num">{r.ordem}</div>
                    <div className="card-fonte" title={r.fonte}>📖 {ft}</div>
                    <span className={`score-badge ${sc}`}>{r.score}%</span>
                  </div>
                  <div className="card-text">
                    <div dangerouslySetInnerHTML={{ __html: r.texto.replace(/\n/g, '<br>') }} />
                  </div>
                </div>
              );
            })}
          </div>
        </details>
      </div>
    );
  };

  return (
    <div className="claude-layout">
      
      {/* Sidebar Lateral */}
      <aside className="claude-sidebar">
        <div className="logo-container">
          <div className="logo-icon"><svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="lucide-book-open"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg></div>
          <div className="logo-title">OTOCONSULT RAG</div>
        </div>

        <div className="section-title">Filtro Clínico (Tema)</div>
        <div className="thematic-menu">
          {TEMAS.map(tema => (
            <div 
              key={tema.n} 
              className={`thematic-item ${contextoTema?.n === tema.n ? 'active' : ''}`}
              onClick={() => selecionarTema(tema)}
            >
              <span className="thematic-item-num">{tema.n}</span>
              <span>{tema.t}</span>
            </div>
          ))}
          <div 
            className={`thematic-item ${contextoTema?.n === '00' ? 'active' : ''}`}
            onClick={() => selecionarTema({n:'00', t:'Geral'})}
            style={{ marginTop: '8px', borderTop: '1px solid var(--border)', borderRadius: '0' }}
          >
            <span className="thematic-item-num" style={{ background: 'transparent', border: 'none' }}>00</span>
            <span>Sem Filtro (Livre)</span>
          </div>
        </div>

        <div className="section-title" style={{ marginTop: '30px' }}>Estatísticas da Base</div>
        <div className="stat-box">
          <span>Trechos Extraídos</span>
          <strong>{stats.total_chunks}</strong>
        </div>
        <div className="stat-box">
          <span>Obras Avaliadas</span>
          <strong>{stats.n_livros}</strong>
        </div>
      </aside>

      {/* Main Área Estilo Claude */}
      <main className="claude-main">

        {/* Mobile-only horizontal filter strip */}
        <div className="mobile-filter-bar">
          {TEMAS.map(tema => (
            <div
              key={tema.n}
              className={`mobile-chip ${contextoTema?.n === tema.n ? 'active' : ''}`}
              onClick={() => selecionarTema(tema)}
            >
              {tema.t}
            </div>
          ))}
          <div
            className={`mobile-chip ${contextoTema?.n === '00' ? 'active' : ''}`}
            onClick={() => selecionarTema({ n: '00', t: 'Geral' })}
          >
            Geral (Sem Filtro)
          </div>
        </div>

        <div className="status-indicator">
           <div className={`dot ${status.state}`}></div>
           {status.state === 'carregando' ? status.error || 'Aguardando Servidor...' : 'Online & Conectado'}
        </div>

        <div className="claude-chat-history" ref={resultsRef}>
          {history.length === 0 && (
            <div className="empty-state">
              <div className="empty-state-icon">🐬</div>
              <h2>Como posso te ajudar hoje doutor?</h2>
              <p>O OTOCONSULT pesquisa diretamente em livros didáticos de residentes e manuais técnicos para formatar sua conduta. Selecione um TEMA na lateral para guiar a lógica matemática de varredura.</p>
              <div className="template-grid">
                {PROMPT_TEMPLATES.map((tpl, i) => (
                  <button
                    key={i}
                    className="template-card"
                    onClick={() => {
                      setQuery(tpl.text);
                      setTimeout(() => {
                        if (inputRef.current) {
                          inputRef.current.style.height = 'auto';
                          inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 180) + 'px';
                          inputRef.current.focus();
                        }
                      }, 50);
                    }}
                  >
                    <span className="template-card-icon">{tpl.icon}</span>
                    <span className="template-card-label">{tpl.label}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {history.map((item, idx) => {
            if (item.type === 'query') {
              return (
                <div key={idx} className="message-wrapper message-user">
                  <div className="bubble">
                    {item.temaVisual && <div style={{ fontSize: '11px', fontWeight: 'bold', color: 'var(--accent)', marginBottom: '4px' }}>[Foco: {item.temaVisual}]</div>}
                    {item.text}
                  </div>
                </div>
              );
            }
            if (item.type === 'error') {
              return (
                <div key={idx} className="message-wrapper message-ai">
                  <div className="ai-avatar" style={{background: '#ef4444'}}>!</div>
                  <div className="ai-content" style={{color: '#ef4444'}}>Erro de Conexão: {item.message}</div>
                </div>
              );
            }
            if (item.type === 'response') {
              const { data } = item;
              return (
                <div key={idx} className="message-wrapper message-ai">
                  <div className="ai-avatar">OT</div>
                  <div className="ai-content">
                    {data.sintese ? (
                      <ReactMarkdown 
                        remarkPlugins={[remarkGfm]} 
                        components={MarkdownComponents}
                      >
                        {data.sintese}
                      </ReactMarkdown>
                    ) : (
                       <span>Buscando diretamente no acervo...</span>
                    )}
                    {renderRefs(data.resultados)}
                  </div>
                </div>
              );
            }
            return null;
          })}

          {buscando && (
            <div className="message-wrapper message-ai" style={{ opacity: 0.7 }}>
              <div className="ai-avatar" style={{ animation: 'blink 1.5s infinite'}}>...</div>
              <div className="ai-content">Ponderando referências em {stats.n_livros} obras...</div>
            </div>
          )}
        </div>

        <div className="input-anchored">
          <div className={`input-wrapper ${focused ? 'focused' : ''}`}>
             {contextoTema && (
               <div className="context-badge">
                 Filtro Ativo: {contextoTema.t}
                 <span className="context-close" onClick={() => setContextoTema(null)}>✕</span>
               </div>
             )}
             <div className="input-row">
                <textarea
                  ref={inputRef}
                  value={query}
                  onChange={e => { setQuery(e.target.value); autoResize(e); }}
                  onKeyDown={handleKey}
                  onFocus={() => setFocused(true)}
                  onBlur={() => setFocused(false)}
                  placeholder="Escreva seu caso ou dúvida técnica..."
                  rows="1"
                ></textarea>
                <button className="btn-send" onClick={buscar} disabled={buscando || status.state !== 'ok' || (!query.trim())}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="22" y1="2" x2="11" y2="13"></line>
                    <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                  </svg>
                </button>
             </div>
          </div>
        </div>
        <div className="input-hint" style={{ position: 'absolute', bottom: '8px', width: '100%', left: 0 }}>
          Pressione Enter para buscar. Shift + Enter para quebrar linha. O OTOCONSULT pode cometer erros. Revise condutas.
        </div>
      </main>
    </div>
  );
}
