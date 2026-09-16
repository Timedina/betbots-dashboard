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

const cores = {
  fundo: "#0e0e0e",
  cartao: "#161616",
  borda: "#2a2a2a",
  texto: "#e8e8e8",
  mudo: "#8a8a8a",
  verde: "#4ade80",
  vermelho: "#f09595",
  amarelo: "#e0b34d",
  azul: "#378ade",
};

function Barra({ pct, cor }) {
  return (
    <div style={{ background: cores.borda, borderRadius: 4, height: 8, width: "100%", maxWidth: 160 }}>
      <div style={{ background: cor, borderRadius: 4, height: 8, width: `${Math.max(0, Math.min(100, pct))}%`, transition: "width 0.3s ease" }} />
    </div>
  );
}

function Badge({ texto, tom }) {
  const paletas = {
    neutro: { bg: "rgba(138,138,138,0.15)", fg: cores.mudo, borda: "rgba(138,138,138,0.35)" },
    aviso: { bg: "rgba(224,179,77,0.15)", fg: cores.amarelo, borda: "rgba(224,179,77,0.4)" },
    positivo: { bg: "rgba(74,222,128,0.15)", fg: cores.verde, borda: "rgba(74,222,128,0.4)" },
    negativo: { bg: "rgba(240,149,149,0.15)", fg: cores.vermelho, borda: "rgba(240,149,149,0.4)" },
    info: { bg: "rgba(55,138,222,0.15)", fg: cores.azul, borda: "rgba(55,138,222,0.4)" },
  };
  const p = paletas[tom] || paletas.neutro;
  return (
    <span
      style={{
        display: "inline-block",
        padding: "3px 10px",
        borderRadius: 999,
        fontSize: 11,
        fontWeight: 700,
        letterSpacing: 0.3,
        textTransform: "uppercase",
        background: p.bg,
        color: p.fg,
        border: `1px solid ${p.borda}`,
        whiteSpace: "nowrap",
      }}
    >
      {texto}
    </span>
  );
}

function Secao({ titulo, subtitulo, badge, children }) {
  return (
    <div
      className="table-card"
      style={{ background: cores.cartao, border: `1px solid ${cores.borda}`, borderRadius: 10, overflow: "hidden" }}
    >
      <div
        style={{
          padding: "14px 16px",
          borderBottom: `1px solid ${cores.borda}`,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
          flexWrap: "wrap",
        }}
      >
        <div>
          <div style={{ color: "#fff", fontSize: 15, fontWeight: 700 }}>{titulo}</div>
          {subtitulo && <div style={{ color: cores.mudo, fontSize: 12, marginTop: 2 }}>{subtitulo}</div>}
        </div>
        {badge}
      </div>
      <div style={{ padding: 16 }}>{children}</div>
    </div>
  );
}
function MetricaMini({ label, valor, cor }) {
  return (
    <div style={{ minWidth: 120 }}>
      <div style={{ color: cores.mudo, fontSize: 11, textTransform: "uppercase", letterSpacing: 0.3, marginBottom: 4 }}>
        {label}
      </div>
      <div style={{ color: cor || "#fff", fontSize: 20, fontWeight: 700 }}>{valor}</div>
    </div>
  );
}

export default function AbaEstatistica() {
  const [zona, setZona] = useState([]);
  const [breakeven, setBreakeven] = useState([]);
  const [progresso, setProgresso] = useState([]);
  const [filtroCombo, setFiltroCombo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      setLoading(true);
      setError("");
      try {
        const [z, b, p, fc] = await Promise.all([
          sb("v_apostas_zona_liquidez?select=*"),
          sb("v_apostas_odd_breakeven?select=*"),
          sb("v_apostas_progresso_validacao?select=*"),
          sb("v_filtro_combo_monitor?select=*"),
        ]);
        setZona(z);
        setBreakeven(b);
        setProgresso(p);
        setFiltroCombo(fc[0] || null);
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

  const pnlTotalBreakeven = breakeven.reduce((acc, f) => acc + (Number(f.pnl_total) || 0), 0);

  if (loading) return <p className="empty">Carregando estatisticas...</p>;
  if (error) return <div className="error-box">{error}</div>;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

      {/* Filtro combo razao+favorito -- novo em producao desde 16/09 */}
      <Secao
        titulo="Filtro combo razao + favorito"
        subtitulo="Ativo em producao desde 16/09/2026 -- monitoramento pos-lancamento"
        badge={<Badge texto="Em producao" tom="info" />}
      >
        {filtroCombo ? (
          <>
            <div style={{ display: "flex", gap: 24, flexWrap: "wrap", marginBottom: 12 }}>
              <MetricaMini label="Bloqueados pelo filtro" valor={filtroCombo.bloqueados_pelo_filtro_novo} />
              <MetricaMini label="Analisados fora do filtro" valor={filtroCombo.analisados_fora_do_filtro} />
              <MetricaMini label="Apostas resolvidas depois" valor={filtroCombo.apostas_resolvidas_pos_filtro} />
              <MetricaMini
                label="PnL pos-filtro"
                valor={filtroCombo.pnl_pos_filtro != null ? `${filtroCombo.pnl_pos_filtro >= 0 ? "+" : ""}${filtroCombo.pnl_pos_filtro}u` : "--"}
                cor={filtroCombo.pnl_pos_filtro >= 0 ? cores.verde : cores.vermelho}
              />
            </div>
            <div style={{ fontSize: 12, color: cores.mudo }}>
              Amostra ainda pequena -- numeros vao ganhar sentido estatistico com mais volume acumulado desde o lancamento.
            </div>
          </>
        ) : (
          <p className="empty">Sem dados ainda.</p>
        )}
      </Secao>

      {/* Zona de liquidez -- estudo em validacao, separado do filtro novo acima */}
      <Secao
        titulo="Zona de perigo de liquidez"
        subtitulo={`Estudo em validacao desde 23/08 -- chi2 = ${chi2 ?? "-"}`}
        badge={<Badge texto="Nao significativo (p > 0,05)" tom="aviso" />}
      >
        <div style={{ fontSize: 12, color: cores.amarelo, marginBottom: 12, lineHeight: 1.5 }}>
          Teste de permutacao (23/08): p=0,061 corrigido pelo vies de escolha do corte -- ainda NAO confirmado
          estatisticamente. Filtro nao esta ativo em producao.
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
                <td>{s.segmento === "zona_perigo" ? "Zona L1200-2600" : "Fora da zona"}</td>
                <td style={{ textAlign: "right" }}>{s.total}</td>
                <td style={{ textAlign: "right" }}>{s.perdas}</td>
                <td style={{ textAlign: "right", fontWeight: 600 }}>{s.win_rate_pct}%</td>
                <td><Barra pct={s.win_rate_pct} cor={s.win_rate_pct >= 90 ? cores.verde : cores.vermelho} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </Secao>

      {/* Panorama descritivo -- win rate vs breakeven por faixa de odd */}
      <Secao
        titulo="Win rate observado vs. breakeven por faixa de odd"
        subtitulo="Panorama descritivo -- historico completo, sem corte de data"
        badge={
          <Badge
            texto={`PnL somado: ${pnlTotalBreakeven >= 0 ? "+" : ""}${pnlTotalBreakeven.toFixed(2)}u`}
            tom={pnlTotalBreakeven >= 0 ? "positivo" : "negativo"}
          />
        }
      >
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
                <td style={{ textAlign: "right", color: f.win_rate_observado_pct < f.win_rate_breakeven_pct ? cores.vermelho : cores.verde, fontWeight: 600 }}>
                  {f.win_rate_observado_pct}%
                </td>
                <td style={{ textAlign: "right", color: cores.mudo }}>{f.win_rate_breakeven_pct}%</td>
                <td style={{ textAlign: "right", color: f.pnl_total >= 0 ? cores.verde : cores.vermelho, fontWeight: 600 }}>
                  {f.pnl_total >= 0 ? "+" : ""}{f.pnl_total}u
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Secao>

      {/* Progresso da validacao */}
      <Secao
        titulo="Progresso da validacao"
        subtitulo="N=60 por grupo necessario -- dados desde 23/08"
      >
        {progresso.length === 0 && <p className="empty">Ainda sem apostas novas desde a data de referencia.</p>}
        {progresso.map((p) => (
          <div key={p.segmento} style={{ marginBottom: 14 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, color: "#ccc", marginBottom: 4 }}>
              <span>{p.segmento === "zona_perigo" ? "Zona L1200-2600" : "Fora da zona"}</span>
              <span>{p.n_atual}/{p.n_necessario} ({p.progresso_pct}%)</span>
            </div>
            <Barra pct={p.progresso_pct} cor={cores.azul} />
          </div>
        ))}
      </Secao>
    </div>
  );
}
