import { useState, useEffect, useRef } from 'react';
import './App.css';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function formatSintese(txt) {
  const topicRegex = /(?:^|\n)(\d+\.\s*\*\*.*?\*\*)/g;
  if (!txt.match(topicRegex)) {
    let replaced = txt.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    replaced = replaced.replace(/^[•\-]\s+(.+)$/gm, '<li>$1</li>');
    replaced = replaced.replace(/(<li>[\s\S]*?<\/li>)/g, m => `<ul>${m}</ul>`);
    replaced = replaced.replace(/\n\n/g, '<br><br>');
    return `<p>${replaced}</p>`;
  }

  const parts = txt.split(topicRegex).map(p => p.trim()).filter(Boolean);
  let html = '';

  for (let i = 0; i < parts.length; i++) {
    let part = parts[i];
    const isHeader = part.match(/^\d+\.\s*\*\*(.*?)\*\*/);

    if (isHeader) {
      let title = isHeader[1].replace(/:$/, '').trim();
      let content = (parts[i + 1] && !parts[i + 1].match(/^\d+\.\s*\*\*/)) ? parts[++i] : "Sem informações.";

      content = content.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
      content = content.replace(/^[•\-]\s+(.+)$/gm, '<li>$1</li>');
      content = content.replace(/(<li>[\s\S]*?<\/li>)/g, m => `<ul style="margin-left:8px">${m}</ul>`);
      content = content.replace(/\n\n/g, '<br><br>');

      let blockClass = 'clin-default';
      let icon = '📌';
      let lowTitle = title.toLowerCase();

      if (lowTitle.includes('impressão')) { blockClass = 'clin-impressao'; icon = '🧑‍⚕️'; }
      else if (lowTitle.includes('diagnóstico')) { blockClass = 'clin-default'; icon = '🔍'; }
      else if (lowTitle.includes('exame')) { blockClass = 'clin-default'; icon = '🧪'; }
      else if (lowTitle.includes('conduta')) { blockClass = 'clin-conduta'; icon = '📋'; }
      else if (lowTitle.includes('alerta') || lowTitle.includes('red flag')) { blockClass = 'clin-alerta'; icon = '🚨'; }
      else if (lowTitle.includes('referência')) { blockClass = 'clin-default'; icon = '📖'; }

      html += `<div class="clin-block ${blockClass}">
        <div class="clin-block-title">${icon} ${title}</div>
        <div class="clin-block-content">${content}</div>
      </div>`;
    } else {
      let replaced = part.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
      html += `<div style="margin-bottom:12px; font-weight:500; color:var(--text-2)">${replaced}</div>`;
    }
  }
  return html;
}

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

export default function App() {
  const [status, setStatus] = useState({ state: 'carregando', error: null });
  const [stats, setStats] = useState({ total_chunks: '—', n_livros: '—', llm_mode: 'none', livros: [] });
  const [history, setHistory] = useState([]);
  const [query, setQuery] = useState('');
  const [topn, setTopn] = useState(4);
  const [buscando, setBuscando] = useState(false);
  const resultsRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    verificarStatus();
  }, []);

  useEffect(() => {
    // Scroll to bottom when history changes
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
    e.target.style.height = Math.min(e.target.scrollHeight, 130) + 'px';
  };

  const usarPill = (txt) => {
    setQuery(txt);
    if (inputRef.current) {
      inputRef.current.focus();
    }
  };

  const handleKey = (e) => {
    if (e.ctrlKey && e.key === 'Enter') {
      e.preventDefault();
      buscar();
    }
  };

  const buscar = async () => {
    const pergunta = query.trim();
    if (!pergunta || buscando || status.state !== 'ok') return;

    setQuery('');
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
    }

    const newQueryItem = { type: 'query', text: pergunta };

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
        body: JSON.stringify({ pergunta, topn, sintetizar: true })
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
    <>
      <header>
        <div className="logo">
          <div className="logo-icon">🐬</div>
          <div>
            <div className="logo-text">BOTTOK</div>
            <div className="logo-sub">Consultor de Literatura Médica</div>
          </div>
        </div>
        <div className="status-badge">
          <div className={`status-dot ${status.state}`}></div>
          <span>
            {status.state === 'carregando' && (status.error || 'Carregando...')}
            {status.state === 'erro' && status.error}
            {status.state === 'ok' && `${stats.total_chunks.toLocaleString()} trechos${stats.llm_mode === 'none' ? '' : ' · ' + stats.llm_mode}`}
          </span>
        </div>
      </header>

      <main>
        <aside>
          <div>
            <div className="section-label">Índice Temático Estratégico</div>
            <div className="thematic-menu">
              {TEMAS.map(tema => (
                <div 
                  key={tema.n} 
                  className="thematic-item" 
                  onClick={() => usarPill(`📚 [TEMA ${tema.n} - ${tema.t}] `)}
                >
                  <span className="thematic-item-num">{tema.n}</span>
                  <span>{tema.t}</span>
                </div>
              ))}
              <div 
                className="thematic-item" 
                onClick={() => usarPill(`📚 [OUTROS TEMAS] `)}
                style={{ marginTop: '4px', borderColor: 'var(--border)', background: 'transparent' }}
              >
                <span className="thematic-item-num" style={{color: 'var(--text-3)', background: 'var(--bg-card)'}}>00</span>
                <span>Outros...</span>
              </div>
            </div>
          </div>
          
          <div style={{ marginTop: '10px' }}>
            <div className="section-label">Estatísticas do Motor</div>
            <div className="stats-grid">
              <div className="stat-card" style={{ padding: '8px' }}>
                <div className="stat-val" style={{ fontSize: '15px' }}>{stats.total_chunks !== '—' ? stats.total_chunks.toLocaleString() : '—'}</div>
                <div className="stat-lbl" style={{ fontSize: '9px' }}>Trechos</div>
              </div>
              <div className="stat-card" style={{ padding: '8px' }}>
                <div className="stat-val" style={{ fontSize: '15px' }}>{stats.n_livros}</div>
                <div className="stat-lbl" style={{ fontSize: '9px' }}>Arquivos</div>
              </div>
            </div>
          </div>
          <div className="tip-box">
            {getTipText()}
          </div>
        </aside>

        <div className="chat-area">
          <div className="results-container" ref={resultsRef}>
            {history.length === 0 && (
              <div className="empty-state">
                <div className="empty-state-icon">🐬</div>
                <h2>OTOCONSULT: Plataforma de Apoio (RAG)</h2>
                <p>As análises abaixo são sintetizadas seguindo padrões de Suporte à Decisão Baseado em Evidências (Sinais de alerta, condutas, diferenciais).</p>
                <div className="quick-pills">
                  <span className="pill" onClick={() => usarPill('Analisar Caso: Paciente 40a, vertigem e zumbido...')}>Analisar Caso: Paciente 40a, vertigem e zumbido...</span>
                  <span className="pill" onClick={() => usarPill('Diagnósticos diferenciais: perdas condutivas')}>Diagnósticos diferenciais: perdas condutivas</span>
                  <span className="pill" onClick={() => usarPill('Sinais de alerta: paralisia facial periférica')}>Sinais de alerta: paralisia facial periférica</span>
                  <span className="pill" onClick={() => usarPill('Protocolo cirúrgico: amigdalectomia pediátrica')}>Protocolo cirúrgico: amigdalectomia pediátrica</span>
                </div>
              </div>
            )}

            {history.map((item, idx) => {
              if (item.type === 'query') {
                return (
                  <div key={idx} className="query-bubble">
                    <div className="query-text">{item.text}</div>
                  </div>
                );
              }
              if (item.type === 'error') {
                return (
                  <div key={idx} className="disclaimer" style={{ marginBottom: '14px' }}>
                    ⚠️ <span>{item.message}</span>
                  </div>
                );
              }
              if (item.type === 'acervo') {
                const sorted = [...stats.livros].sort((a, b) => humanizarNome(a).localeCompare(humanizarNome(b), 'pt'));
                return (
                  <div key={idx} className="sintese-card" style={{ marginBottom: '16px' }}>
                    <div className="sintese-header">
                      <div className="sintese-icon">📚</div>
                      <span className="sintese-title">Acervo Indexado — {stats.livros.length} documentos</span>
                    </div>
                    <div style={{ maxHeight: '340px', overflowY: 'auto', paddingRight: '4px' }}>
                      {sorted.map((nome, i) => (
                        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '5px 0', borderBottom: '1px solid var(--border)' }}>
                          <span style={{ fontSize: '10px', color: 'var(--text-3)', minWidth: '22px', textAlign: 'right' }}>{i + 1}</span>
                          <span style={{ fontSize: '12px', color: 'var(--text-2)' }}>📖 {humanizarNome(nome)}</span>
                        </div>
                      ))}
                    </div>
                    <div style={{ marginTop: '10px', fontSize: '11px', color: 'var(--text-3)' }}>
                      Total: {stats.total_chunks.toLocaleString()} trechos extraídos deste acervo.
                    </div>
                  </div>
                );
              }
              if (item.type === 'response') {
                const { data } = item;
                const cls = { ollama: 'llm-ollama', groq: 'llm-groq', none: 'llm-none' }[data.llm_usado] || 'llm-none';
                const label = { ollama: 'Ollama local', groq: 'Groq API', none: '' }[data.llm_usado] || '';
                return (
                  <div key={idx}>
                    {data.sintese && (
                      <div className="sintese-card">
                        <div className="sintese-header">
                          <div className="sintese-icon">🧠</div>
                          <span className="sintese-title">Resposta Sintetizada</span>
                          <span className={`llm-badge ${cls}`}>{label}</span>
                        </div>
                        <div className="sintese-body" dangerouslySetInnerHTML={{ __html: formatSintese(data.sintese) }} />
                      </div>
                    )}
                    {renderRefs(data.resultados)}
                    <div className="disclaimer">
                      ⚠️ <span>Baseado exclusivamente nos livros indexados. Não constitui prescrição médica. Valide com diretrizes atualizadas e julgamento clínico.</span>
                    </div>
                  </div>
                );
              }
              return null;
            })}

            {buscando && (
              <div className="loading-card">
                <div className="spinner"></div>
                <div>
                  <div style={{ fontSize: '13px', fontWeight: 500, color: 'var(--text-1)' }}>{stats.llm_mode !== 'none' ? 'Buscando e sintetizando...' : 'Buscando referências...'}</div>
                  <div style={{ fontSize: '11px', color: 'var(--text-3)', marginTop: '2px' }}>{stats.total_chunks.toLocaleString()} trechos{stats.llm_mode !== 'none' ? ' · ' + stats.llm_mode.toUpperCase() : ''}</div>
                </div>
              </div>
            )}
          </div>

          <div className="input-area">
            <div className="topn-row">
              <span className="topn-label">Puxar quantas referências por resposta?</span>
              <div className="topn-btns">
                {[2, 4, 6, 8, 10].map(n => (
                  <button key={n} className={`topn-btn ${topn === n ? 'active' : ''}`} onClick={() => setTopn(n)}>{n}</button>
                ))}
              </div>
            </div>
            <div style={{ display: 'flex', gap: '8px', marginBottom: '12px', flexWrap: 'wrap' }}>
              <span className="pill" style={{ fontSize: '11px', padding: '4px 10px' }} onClick={() => usarPill('[CASO] ')}>[CASO]</span>
              <span className="pill" style={{ fontSize: '11px', padding: '4px 10px' }} onClick={() => usarPill('Red flags em: ')}>Red flags em:</span>
              <span className="pill" style={{ fontSize: '11px', padding: '4px 10px' }} onClick={() => usarPill('Exames sugeridos para: ')}>Exames sugeridos para:</span>
              <span className="pill" style={{ fontSize: '11px', padding: '4px 10px' }} onClick={() => usarPill('Tratamento clínico e cirúrgico de: ')}>Tratamento clínico e cirúrgico de:</span>
            </div>
            <div className="input-row">
              <textarea
                ref={inputRef}
                value={query}
                onChange={e => { setQuery(e.target.value); autoResize(e); }}
                onKeyDown={handleKey}
                placeholder="Sua pergunta clínica..."
                rows="1"
              ></textarea>
              <button className="btn-send" onClick={buscar} disabled={buscando || status.state !== 'ok'} title="Ctrl+Enter">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="22" y1="2" x2="11" y2="13"></line>
                  <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                </svg>
              </button>
            </div>
            <div className="help-text">Ctrl+Enter para enviar &nbsp;·&nbsp; Respostas baseadas no Acervo &nbsp;·&nbsp; Confirme sempre com julgamento clínico</div>
          </div>
        </div>
      </main>
    </>
  );
}
