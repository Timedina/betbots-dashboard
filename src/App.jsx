import { useState, useEffect, useCallback } from "react";
import "./App.css";

const SUPABASE_URL = "https://rxqotlcxujokzujodyhv.supabase.co";
const SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJ4cW90bGN4dWpva3p1am9keWh2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODE5ODMyMzUsImV4cCI6MjA5NzU1OTIzNX0.dWYvLVZCBTWGKpNcw4Ux53ojsN7BLI2OVHtA7mwKLaM";

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

export default function App() {
  const [analises, setAnalises] = useState([]);
  const [apostas, setApostas] = useState([]);
  const [bot, setBot] = useState(null);
  const [tab, setTab] = useState("analises");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [lastUpdate, setLastUpdate] = useState(null);

  const carregar = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [bots, an, ap] = await Promise.all([
        sb("bots?select=*&limit=1"),
        sb("analises?select=*&order=analisado_em.desc&limit=50"),
        sb("apostas?select=*&order=apostado_em.desc&limit=50"),
      ]);
      setBot(bots[0] || null);
      setAnalises(an);
      setApostas(ap);
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

      <p className="footer-note">
        Atualiza automaticamente a cada 30s. Dados vem direto do Supabase
        (somente leitura).
      </p>
    </div>
  );
}
