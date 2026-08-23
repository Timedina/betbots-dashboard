import { useState, useEffect } from "react";

const SUPABASE_URL = "https://rxqotlcxujokzujodyhv.supabase.co";
const SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJ4cW90bGN4dWpva3p1am9keWh2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODE5ODMyMzUsImV4cCI6MjA5NzU1OTIzNX0.dWYvLVZCBTWGKpNcw4Ux53ojsN7BLI2OVHtA7mwKLaM";

async function sb(path) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, {
    headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` },
  });
  if (!res.ok) throw new Error(`Erro ${res.status} ao consultar ${path}`);
  return res.json();
}

function Barra({ pct, cor }) {
  return (
    <div style={{ background: "#2a2a2a", borderRadius: 4, height: 8, width: "100%", maxWidth: 160 }}>
      <div style={{ background: cor, borderRadius: 4, height: 8, width: `${Math.min(100, pct)}%` }} />
    </div>
  );
}

export default function AbaEstatistica() {
  const [zona, setZona] = useState([]);
  const [breakeven, setBreakeven] = useState([]);
  const [progresso, setProgresso] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      setLoading(true);
      setError("");
      try {
        const [z, b, p] = await Promise.all([
          sb("v_apostas_zona_liquidez?select=*"),
          sb("v_apostas_odd_breakeven?select=*"),
          sb("v_apostas_progresso_validacao?select=*"),
        ]);
        setZona(z);
        setBreakeven(b);
        setProgresso(p);
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const chi2 = (() => {
    const z = zona.find((x) => x.segmento === "zona_perigo");
    const f = zona.find((x) => x.segmento === "fora_zona");
    if (!z || !f) return null;
    const a = z.perdas, b = z.vitorias, c = f.perdas, d = f.vitorias;
    const n = a + b + c + d;
    const num = n * Math.pow(a * d - b * c, 2);
    const den = (a + b) * (c + d) * (a + c) * (b + d);
    return den ? (num / den).toFixed(2) : null;
  })();

  if (loading) return <p className="empty">Carregando estatisticas...</p>;
  if (error) return <div className="error-box">{error}</div>;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div className="table-card">
        <div style={{ padding: "10px 12px", borderBottom: "1px solid #2a2a2a", color: "#fff", fontSize: 14, fontWeight: 600 }}>
          Zona de perigo de liquidez (chi2 = {chi2 ?? "-"})
        </div>
        <div style={{ padding: 12, fontSize: 12, color: "#e0b34d" }}>
          Teste de permutacao (23/08): p=0,061 corrigido pelo vies de escolha do corte -- ainda NAO confirmado estatisticamente. Filtro nao esta ativo em producao.
        </div>
        <table>
          <thead>
            <tr>
              <th>Segmento</th>
              <th style={{ textAlign: "right" }}>Apostas</th>
              <th style={{ textAlign: "right" }}>Perdas</th>
              <th style={{ textAlign: "right" }}>Win rate</th>
              <th>Barra</th>
            </tr>
          </thead>
          <tbody>
            {zona.map((s) => (
              <tr key={s.segmento}>
                <td>{s.segmento === "zona_perigo" ? "Zona £1200-2600" : "Fora da zona"}</td>
                <td style={{ textAlign: "right" }}>{s.total}</td>
                <td style={{ textAlign: "right" }}>{s.perdas}</td>
                <td style={{ textAlign: "right", fontWeight: 600 }}>{s.win_rate_pct}%</td>
                <td><Barra pct={s.win_rate_pct} cor={s.win_rate_pct >= 90 ? "#4ade80" : "#f09595"} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="table-card">
        <div style={{ padding: "10px 12px", borderBottom: "1px solid #2a2a2a", color: "#fff", fontSize: 14, fontWeight: 600 }}>
          Win rate observado vs. breakeven por faixa de odd
        </div>
        <table>
          <thead>
            <tr>
              <th>Faixa odd</th>
              <th style={{ textAlign: "right" }}>Apostas</th>
              <th style={{ textAlign: "right" }}>Observado</th>
              <th style={{ textAlign: "right" }}>Breakeven</th>
              <th style={{ textAlign: "right" }}>PnL</th>
            </tr>
          </thead>
          <tbody>
            {breakeven.map((f) => (
              <tr key={f.faixa_odd}>
                <td>{f.odd_min} - {f.odd_max}</td>
                <td style={{ textAlign: "right" }}>{f.total}</td>
                <td style={{ textAlign: "right", color: f.win_rate_observado_pct < f.win_rate_breakeven_pct ? "#f09595" : "#4ade80", fontWeight: 600 }}>
                  {f.win_rate_observado_pct}%
                </td>
                <td style={{ textAlign: "right", color: "#aaa" }}>{f.win_rate_breakeven_pct}%</td>
                <td style={{ textAlign: "right", color: f.pnl_total >= 0 ? "#4ade80" : "#f09595", fontWeight: 600 }}>
                  {f.pnl_total >= 0 ? "+" : ""}{f.pnl_total}u
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="table-card" style={{ padding: 12 }}>
        <div style={{ color: "#fff", fontSize: 14, fontWeight: 600, marginBottom: 8 }}>
          Progresso da validacao (N=60/grupo necessario, dados desde 23/08)
        </div>
        {progresso.length === 0 && <p className="empty">Ainda sem apostas novas desde a data de referencia.</p>}
        {progresso.map((p) => (
          <div key={p.segmento} style={{ marginBottom: 10 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, color: "#ccc", marginBottom: 4 }}>
              <span>{p.segmento === "zona_perigo" ? "Zona £1200-2600" : "Fora da zona"}</span>
              <span>{p.n_atual}/{p.n_necessario} ({p.progresso_pct}%)</span>
            </div>
            <Barra pct={p.progresso_pct} cor="#378ade" />
          </div>
        ))}
      </div>
    </div>
  );
}
