import { useState, useEffect, useCallback } from "react";
import "./App.css";

const SUPABASE_URL = "https://rxqotlcxujokzujodyhv.supabase.co";
const SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJ4cW90bGN4dWpva3p1am9keWh2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODE5ODMyMzUsImV4cCI6MjA5NzU1OTIzNX0.dWYvLVZCBTWGKpNcw4Ux53ojsN7BLI2OVHtA7mwKLaM";
const BOT_ID = "7449c515-4a4e-4ad3-acda-32916034e9c1";

async function sb(path) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, {
    headers: {
      apikey: SUPABASE_KEY,
      Authorization: `Bearer ${SUPABASE_KEY}`,
    },
  });
  if (!res.ok) throw new Error(`Erro ${res.status} ao consultar ${path}`);
  return res.json();
}

async function sbPatch(path, body) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, {
    method: "PATCH",
    headers: {
      apikey: SUPABASE_KEY,
      Authorization: `Bearer ${SUPABASE_KEY}`,
      "Content-Type": "application/json",
      Prefer: "return=representation",
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Erro ${res.status} ao salvar`);
  return res.json();
}

async function chatComIA(mensagem, botId, historico) {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mensagem, bot_id: botId, historico }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `Erro ${res.status}`);
  return data.resposta;
}

function fmtHora(ts) {
  if (!ts) return "--:--";
  const d = new Date(ts);
  return d.toLocaleTimeString("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "America/Sao_Paulo",
  });
}

function MetricCard({ label, value }) {
  return (
    <div className="card">
      <p className="card-label">{label}</p>
      <p className="card-value">{value}</p>
    </div>
  );
}

function StatusBadge({ aprovado }) {
  return (
    <span className={aprovado ? "badge badge-ok" : "badge badge-bad"}>
      {aprovado ? "Aprovado" : "Reprovado"}
    </span>
  );
}
const FILTROS_GRUPOS = [
  {
    nome: "Placar Exato (Correct Score)",
    campos: [
      { chave: "ODD_01_MINIMA", label: "Odd mínima LAY 0-1" },
      { chave: "ODD_01_MAXIMA", label: "Odd máxima LAY 0-1" },
      { chave: "ODD_10_MINIMA", label: "Odd mínima LAY 1-0" },
      { chave: "ODD_10_MAXIMA", label: "Odd máxima LAY 1-0" },
      { chave: "RAZAO_ODD_MAXIMA", label: "Razão máxima odd 0-1 / 1-0" },
      { chave: "LIQUIDEZ_MINIMA_CS_DISPONIVEL", label: "Liquidez mínima disponível (£)" },
    ],
  },
  {
    nome: "Favorito (Match Odds)",
    campos: [{ chave: "ODD_FAVORITO_MAX", label: "Odd máxima do favorito", copa: true }],
  },
  {
    nome: "Over 1.5 Gols",
    campos: [
      { chave: "ODD_OVER15_MINIMA", label: "Odd mínima" },
      { chave: "ODD_OVER15_MAXIMA", label: "Odd máxima", copa: true },
    ],
  },
  {
    nome: "Ambas Marcam (BTTS)",
    campos: [
      { chave: "ODD_BTTS_MINIMA", label: "Odd mínima" },
      { chave: "ODD_BTTS_MAXIMA", label: "Odd máxima", copa: true },
    ],
  },
  {
    nome: "Gestão de Risco",
    campos: [{ chave: "LIABILITY_FIXA", label: "Perda máxima aceita por aposta (£)" }],
  },
];

const SUGESTOES_CHAT = [
  "Como esta o PnL desse bot?",
  "Qual filtro esta barrando mais jogos?",
  "Sugira um ajuste nos filtros atuais",
  "Quais foram as ultimas apostas perdidas?",
];

function ChatIA({ botId }) {
  const [mensagens, setMensagens] = useState([]);
  const [input, setInput] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState("");

  const enviar = async (textoForcado) => {
    const texto = (textoForcado ?? input).trim();
    if (!texto || enviando) return;

    setErro("");
    const novaMsgUser = { role: "user", content: texto };
    const historicoAtual = [...mensagens, novaMsgUser];
    setMensagens(historicoAtual);
    setInput("");
    setEnviando(true);

    try {
      const resposta = await chatComIA(texto, botId, mensagens);
      setMensagens([...historicoAtual, { role: "assistant", content: resposta }]);
    } catch (e) {
      setErro(e.message);
    } finally {
      setEnviando(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      enviar();
    }
  };

  return (
    <div className="chat-wrap">
      <div className="chat-messages">
        {mensagens.length === 0 && (
          <div className="chat-empty">
            <p>Pergunte sobre o desempenho do bot, filtros atuais ou peca
            sugestoes de ajuste. A IA tem acesso aos dados reais do banco.</p>
            <div className="chat-suggestions">
              {SUGESTOES_CHAT.map((s) => (
                <button key={s} className="chat-suggestion" onClick={() => enviar(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {mensagens.map((m, i) => (
          <div
            key={i}
            className={`chat-msg ${m.role === "user" ? "chat-msg-user" : "chat-msg-assistant"}`}
          >
            {m.content}
          </div>
        ))}
        {enviando && (
          <div className="chat-msg chat-msg-loading">Pensando...</div>
        )}
      </div>
      {erro && <div className="error-box">{erro}</div>}
      <div className="chat-input-row">
        <textarea
          className="chat-input"
          rows={1}
          placeholder="Pergunte algo sobre esse bot..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
        />
        <button className="chat-send" onClick={() => enviar()} disabled={enviando || !input.trim()}>
          Enviar
        </button>
      </div>
    </div>
  );
}

function CampoFiltro({ meta, linha, onSalvar, salvando }) {
  const [valor, setValor] = useState(linha?.valor ?? "");
  const [valorCopa, setValorCopa] = useState(linha?.valor_copa ?? "");
  const [salvo, setSalvo] = useState(false);

  useEffect(() => {
    setValor(linha?.valor ?? "");
    setValorCopa(linha?.valor_copa ?? "");
  }, [linha]);

  const sujo =
    String(valor) !== String(linha?.valor ?? "") ||
    (meta.copa && String(valorCopa) !== String(linha?.valor_copa ?? ""));

  const salvar = async () => {
    await onSalvar(meta.chave, valor, meta.copa ? valorCopa : null);
    setSalvo(true);
    setTimeout(() => setSalvo(false), 2000);
  };

  if (!linha) return null;

  return (
    <div className="filtro-row">
      <div className="filtro-label">
        <span>{meta.label}</span>
        {linha.descricao && <span className="filtro-desc">{linha.descricao}</span>}
      </div>
      <div className="filtro-inputs">
        <input
          type="number"
          step="0.01"
          value={valor}
          onChange={(e) => setValor(e.target.value)}
          className="filtro-input"
        />
        {meta.copa && (
          <>
            <span className="filtro-copa-label">copa</span>
            <input
              type="number"
              step="0.01"
              value={valorCopa}
              onChange={(e) => setValorCopa(e.target.value)}
              className="filtro-input filtro-input-copa"
            />
          </>
        )}
        <button
          className={`btn-salvar ${sujo ? "btn-salvar-ativo" : ""}`}
          onClick={salvar}
          disabled={!sujo || salvando}
        >
          {salvando ? "..." : salvo ? "Salvo ✓" : "Salvar"}
        </button>
      </div>
    </div>
  );
}
export default function App() {
  const [analises, setAnalises] = useState([]);
  const [apostas, setApostas] = useState([]);
  const [filtros, setFiltros] = useState([]);
  const [bot, setBot] = useState(null);
  const [tab, setTab] = useState("analises");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [lastUpdate, setLastUpdate] = useState(null);
  const [salvandoChave, setSalvandoChave] = useState(null);

  const carregar = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [bots, an, ap, fl] = await Promise.all([
        sb("bots?select=*&limit=1"),
        sb("analises?select=*&order=analisado_em.desc&limit=50"),
        sb("apostas?select=*&order=apostado_em.desc&limit=50"),
        sb(`filtros?select=*&bot_id=eq.${BOT_ID}`),
      ]);
      setBot(bots[0] || null);
      setAnalises(an);
      setApostas(ap);
      setFiltros(fl);
      setLastUpdate(new Date());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    carregar();
    const interval = setInterval(carregar, 30000);
    return () => clearInterval(interval);
  }, [carregar]);

  const salvarFiltro = async (chave, valor, valorCopa) => {
    setSalvandoChave(chave);
    try {
      const body = { valor: parseFloat(valor) };
      if (valorCopa !== null && valorCopa !== "") {
        body.valor_copa = parseFloat(valorCopa);
      }
      await sbPatch(`filtros?chave=eq.${chave}&bot_id=eq.${BOT_ID}`, body);
      setFiltros((prev) =>
        prev.map((f) => (f.chave === chave ? { ...f, ...body } : f))
      );
    } catch (e) {
      setError(`Erro ao salvar ${chave}: ${e.message}`);
    } finally {
      setSalvandoChave(null);
    }
  };

  const hoje = new Date().toISOString().slice(0, 10);
  const analisadosHoje = analises.filter((a) =>
    (a.analisado_em || "").startsWith(hoje)
  );
  const aprovadosHoje = analisadosHoje.filter((a) => a.aprovado);
  const taxa = analisadosHoje.length
    ? Math.round((aprovadosHoje.length / analisadosHoje.length) * 100)
    : 0;

  return (
    <div className="app">
      <div className="header">
        <div className="header-left">
          <span className={`dot ${bot?.ativo ? "dot-on" : "dot-off"}`} />
          <span className="bot-name">{bot?.nome || "Carregando..."}</span>
          {bot?.modo_simulacao && <span className="tag">simulacao</span>}
        </div>
        <div className="header-right">
          {lastUpdate && (
            <span className="updated-at">atualizado {fmtHora(lastUpdate)}</span>
          )}
          <button className="btn" onClick={carregar} disabled={loading}>
            {loading ? "Atualizando..." : "Atualizar"}
          </button>
        </div>
      </div>

      {error && <div className="error-box">{error}</div>}

      <div className="metrics">
        <MetricCard label="Analisados hoje" value={analisadosHoje.length} />
        <MetricCard label="Aprovados hoje" value={aprovadosHoje.length} />
        <MetricCard label="Taxa de aprovacao" value={`${taxa}%`} />
      </div>

      <div className="tabs">
        <button
          className={tab === "analises" ? "tab tab-active" : "tab"}
          onClick={() => setTab("analises")}
        >
          Analises
        </button>
        <button
          className={tab === "apostas" ? "tab tab-active" : "tab"}
          onClick={() => setTab("apostas")}
        >
          Apostas
        </button>
        <button
          className={tab === "filtros" ? "tab tab-active" : "tab"}
          onClick={() => setTab("filtros")}
        >
          Filtros
        </button>
        <button
          className={tab === "chat" ? "tab tab-active" : "tab"}
          onClick={() => setTab("chat")}
        >
          Chat IA
        </button>
      </div>

      {tab === "analises" && (
        <div className="table-card">
          <table>
            <thead>
              <tr>
                <th style={{ width: "30%" }}>Jogo</th>
                <th style={{ width: "14%" }}>Status</th>
                <th style={{ width: "40%" }}>Motivo</th>
                <th style={{ width: "16%", textAlign: "right" }}>Hora</th>
              </tr>
            </thead>
            <tbody>
              {analises.length === 0 && !loading && (
                <tr>
                  <td colSpan={4} className="empty">
                    Nenhuma analise registrada ainda.
                  </td>
                </tr>
              )}
              {analises.map((a) => (
                <tr key={a.id}>
                  <td>
                    {a.nome_jogo}
                    <div className="sub">{a.competition}</div>
                  </td>
                  <td>
                    <StatusBadge aprovado={a.aprovado} />
                  </td>
                  <td className="muted">
                    {a.aprovado
                      ? a.ia_motivo || "—"
                      : (a.motivos || []).join(", ") || "—"}
                  </td>
                  <td className="muted" style={{ textAlign: "right" }}>
                    {fmtHora(a.analisado_em)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "apostas" && (
        <div className="table-card">
          <table>
            <thead>
              <tr>
                <th style={{ width: "26%" }}>Jogo</th>
                <th style={{ width: "14%" }}>Odd lay</th>
                <th style={{ width: "14%" }}>Status</th>
                <th style={{ width: "14%" }}>PnL</th>
                <th style={{ width: "32%", textAlign: "right" }}>Apostado em</th>
              </tr>
            </thead>
            <tbody>
              {apostas.length === 0 && !loading && (
                <tr>
                  <td colSpan={5} className="empty">
                    Nenhuma aposta registrada ainda.
                  </td>
                </tr>
              )}
              {apostas.map((a) => (
                <tr key={a.id}>
                  <td>{a.nome_jogo}</td>
                  <td>{a.odd_lay ?? "—"}</td>
                  <td>{a.status}</td>
                  <td>{a.pnl != null ? a.pnl : "—"}</td>
                  <td className="muted" style={{ textAlign: "right" }}>
                    {fmtHora(a.apostado_em)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "filtros" && (
        <div className="filtros-wrap">
          {FILTROS_GRUPOS.map((grupo) => (
            <div className="filtro-grupo" key={grupo.nome}>
              <h3 className="filtro-grupo-titulo">{grupo.nome}</h3>
              {grupo.campos.map((meta) => {
                const linha = filtros.find((f) => f.chave === meta.chave);
                return (
                  <CampoFiltro
                    key={meta.chave}
                    meta={meta}
                    linha={linha}
                    onSalvar={salvarFiltro}
                    salvando={salvandoChave === meta.chave}
                  />
                );
              })}
            </div>
          ))}
          <p className="footer-note">
            As alteracoes valem em ate 5 minutos (o bot recarrega os filtros
            periodicamente).
          </p>
        </div>
      )}

      {tab === "chat" && bot && <ChatIA botId={bot.id} />}

      {tab !== "filtros" && tab !== "chat" && (
        <p className="footer-note">
          Atualiza automaticamente a cada 30s. Dados vem direto do Supabase
          (somente leitura).
        </p>
      )}
    </div>
  );
}
