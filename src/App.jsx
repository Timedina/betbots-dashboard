import { useState, useEffect, useCallback } from "react";
import "./App.css";

const SUPABASE_URL = "https://rxqotlcxujokzujodyhv.supabase.co";
const SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJ4cW90bGN4dWpva3p1am9keWh2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODE5ODMyMzUsImV4cCI6MjA5NzU1OTIzNX0.dWYvLVZCBTWGKpNcw4Ux53ojsN7BLI2OVHtA7mwKLaM";
const BOT_ID = "7449c515-4a4e-4ad3-acda-32916034e9c1";

async function sb(path) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, {
    headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` },
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

async function sbPost(path, body) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, {
    method: "POST",
    headers: {
      apikey: SUPABASE_KEY,
      Authorization: `Bearer ${SUPABASE_KEY}`,
      "Content-Type": "application/json",
      Prefer: "return=representation",
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Erro ${res.status}: ${detail}`);
  }
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

const FILTROS_LABELS = {
  ENTRADA_MINUTOS_MAX: { label: "Entrar ate quantos minutos de jogo", tipo: "numero" },
  ODD_MINIMA:          { label: "Odd minima de entrada", tipo: "numero" },
  ODD_MAXIMA:          { label: "Odd maxima de entrada", tipo: "numero" },
  LIQUIDEZ_MINIMA:     { label: "Liquidez minima no mercado (£)", tipo: "numero" },
  STAKE_FIXO:          { label: "Stake fixo (R$)", tipo: "numero" },
  SAIDA_MINUTOS:       { label: "Sair apos quantos minutos da entrada", tipo: "numero" },
  SAIDA_LUCRO_PCT:     { label: "Sair com quanto % de lucro", tipo: "numero" },
  SAIDA_TIPO:          { label: "Regra de saida", tipo: "texto" },
  MERCADO:             { label: "Mercado", tipo: "texto" },
  DIRECAO:             { label: "Direcao da aposta", tipo: "texto" },
  TEMPO_ENTRADA:       { label: "Tempo de jogo para operar", tipo: "texto" },
  LIABILITY_FIXA:      { label: "Perda maxima aceita por aposta (£)", tipo: "numero" },
  ODD_01_MINIMA:       { label: "Odd minima LAY 0-1", tipo: "numero" },
  ODD_01_MAXIMA:       { label: "Odd maxima LAY 0-1", tipo: "numero" },
  ODD_10_MINIMA:       { label: "Odd minima LAY 1-0", tipo: "numero" },
  ODD_10_MAXIMA:       { label: "Odd maxima LAY 1-0", tipo: "numero" },
  RAZAO_ODD_MAXIMA:    { label: "Razao maxima odd 0-1 / 1-0", tipo: "numero" },
  LIQUIDEZ_MINIMA_CS_DISPONIVEL: { label: "Liquidez minima disponivel (£)", tipo: "numero" },
  ODD_FAVORITO_MAX:    { label: "Odd maxima do favorito", tipo: "numero" },
  ODD_OVER15_MINIMA:   { label: "Odd minima Over 1.5", tipo: "numero" },
  ODD_OVER15_MAXIMA:   { label: "Odd maxima Over 1.5", tipo: "numero" },
  ODD_BTTS_MINIMA:     { label: "Odd minima BTTS", tipo: "numero" },
  ODD_BTTS_MAXIMA:     { label: "Odd maxima BTTS", tipo: "numero" },
};

const SUGESTOES_CHAT = [
  "Como esta o PnL desse bot?",
  "Qual filtro esta barrando mais jogos?",
  "Sugira um ajuste nos filtros atuais",
  "Quais foram as ultimas apostas perdidas?",
];

const MERCADOS = [
  { value: "CORRECT_SCORE", label: "Correct Score" },
  { value: "OVER_UNDER_25", label: "Over/Under 2.5 gols" },
  { value: "OVER_UNDER_15", label: "Over/Under 1.5 gols" },
  { value: "BTTS", label: "Ambas marcam (BTTS)" },
];

const TEMPOS = [
  { value: "AMBOS", label: "1o e 2o tempo" },
  { value: "1T", label: "Apenas 1o tempo" },
  { value: "2T", label: "Apenas 2o tempo" },
];

const SAIDAS = [
  { value: "MINUTOS_OU_LUCRO", label: "Minutos ou lucro (o que vier primeiro)" },
  { value: "MINUTOS", label: "Apenas minutos apos a entrada" },
  { value: "LUCRO_PCT", label: "Apenas percentual de lucro" },
  { value: "GOL", label: "Sair quando sair um gol" },
  { value: "SEM_SAIDA", label: "Segurar ate o fim do jogo" },
];

const DIRECOES = {
  CORRECT_SCORE: [{ value: "LAY_0X1_1X0", label: "LAY 0x1 / 1x0" }],
  OVER_UNDER_25: [
    { value: "BACK_UNDER", label: "BACK Under 2.5 (ate 2 gols)" },
    { value: "LAY_UNDER", label: "LAY Under 2.5 (3+ gols)" },
  ],
  OVER_UNDER_15: [
    { value: "BACK_UNDER", label: "BACK Under 1.5 (0 ou 1 gol)" },
    { value: "LAY_UNDER", label: "LAY Under 1.5 (2+ gols)" },
  ],
  BTTS: [
    { value: "BACK_SIM", label: "BACK Sim (ambas marcam)" },
    { value: "BACK_NAO", label: "BACK Nao (pelo menos uma nao marca)" },
  ],
};

const FORM_INICIAL = {
  nome: "",
  descricao: "",
  mercado: "OVER_UNDER_25",
  direcao: "BACK_UNDER",
  tempo_entrada: "AMBOS",
  entrada_minutos_max: 10,
  odd_minima: "",
  odd_maxima: "",
  liquidez_minima: 150,
  saida_tipo: "MINUTOS_OU_LUCRO",
  saida_minutos: 10,
  saida_lucro_pct: 10,
  stake_fixo: 50,
  modo_simulacao: true,
};

function Field({ label, children, hint }) {
  return (
    <div style={{ marginBottom: "1rem" }}>
      <label style={{ display: "block", fontSize: 13, color: "var(--color-text-secondary)", marginBottom: 6 }}>
        {label}
      </label>
      {children}
      {hint && <p style={{ fontSize: 12, color: "var(--color-text-tertiary)", margin: "4px 0 0" }}>{hint}</p>}
    </div>
  );
}

function BotStatusPill({ ativo }) {
  return (
    <span style={{
      fontSize: 12, padding: "2px 8px", borderRadius: "var(--border-radius-md)",
      background: ativo ? "var(--color-background-success)" : "var(--color-background-secondary)",
      color: ativo ? "var(--color-text-success)" : "var(--color-text-tertiary)",
    }}>
      {ativo ? "Ativo" : "Aguardando motor"}
    </span>
  );
}

function EstrategiasTab() {
  const [form, setForm] = useState(FORM_INICIAL);
  const [bots, setBots] = useState([]);
  const [filtrosPorBot, setFiltrosPorBot] = useState({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loadingList, setLoadingList] = useState(true);

  const carregarBots = useCallback(async () => {
    setLoadingList(true);
    try {
      const lista = await sb("bots?select=*&order=criado_em.desc");
      setBots(lista);
      const todos = await sb("filtros?select=bot_id,chave,valor,valor_texto");
      const agrupado = {};
      for (const f of todos) {
        if (!agrupado[f.bot_id]) agrupado[f.bot_id] = {};
        agrupado[f.bot_id][f.chave] = f.valor_texto ?? f.valor;
      }
      setFiltrosPorBot(agrupado);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoadingList(false);
    }
  }, []);

  useEffect(() => { carregarBots(); }, [carregarBots]);

  function update(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  function handleMercadoChange(value) {
    const dirs = DIRECOES[value] || [];
    setForm((f) => ({ ...f, mercado: value, direcao: dirs[0]?.value || "" }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!form.nome.trim()) { setError("Da um nome pro bot antes de salvar."); return; }
    setSaving(true); setError(""); setSuccess("");
    try {
      const [novoBot] = await sbPost("bots", {
        nome: form.nome.trim(),
        descricao: form.descricao.trim() || null,
        estrategia: form.mercado,
        ativo: false,
        modo_simulacao: form.modo_simulacao,
      });

      const linhas = [
        { bot_id: novoBot.id, chave: "MERCADO", valor_texto: form.mercado },
        { bot_id: novoBot.id, chave: "DIRECAO", valor_texto: form.direcao },
        { bot_id: novoBot.id, chave: "TEMPO_ENTRADA", valor_texto: form.tempo_entrada },
        { bot_id: novoBot.id, chave: "SAIDA_TIPO", valor_texto: form.saida_tipo },
        { bot_id: novoBot.id, chave: "ENTRADA_MINUTOS_MAX", valor: Number(form.entrada_minutos_max) },
        { bot_id: novoBot.id, chave: "SAIDA_MINUTOS", valor: Number(form.saida_minutos) },
        { bot_id: novoBot.id, chave: "SAIDA_LUCRO_PCT", valor: Number(form.saida_lucro_pct) },
        { bot_id: novoBot.id, chave: "STAKE_FIXO", valor: Number(form.stake_fixo) },
        ...(form.liquidez_minima !== "" ? [{ bot_id: novoBot.id, chave: "LIQUIDEZ_MINIMA", valor: Number(form.liquidez_minima) }] : []),
        ...(form.odd_minima !== "" ? [{ bot_id: novoBot.id, chave: "ODD_MINIMA", valor: Number(form.odd_minima) }] : []),
        ...(form.odd_maxima !== "" ? [{ bot_id: novoBot.id, chave: "ODD_MAXIMA", valor: Number(form.odd_maxima) }] : []),
      ];

      await sbPost("filtros", linhas);
      setSuccess(`Bot "${form.nome}" cadastrado com sucesso.`);
      setForm(FORM_INICIAL);
      carregarBots();
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  async function toggleAtivo(bot) {
    try {
      await sbPatch(`bots?id=eq.${bot.id}`, { ativo: !bot.ativo });
      carregarBots();
    } catch (e) {
      setError(e.message);
    }
  }

  const dirs = DIRECOES[form.mercado] || [];

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "2rem", alignItems: "start" }}>
      <form onSubmit={handleSubmit}>
        <h3 style={{ fontSize: 15, fontWeight: 500, margin: "0 0 1.25rem" }}>Cadastrar novo bot</h3>

        <Field label="Nome do bot">
          <input type="text" value={form.nome} onChange={(e) => update("nome", e.target.value)}
            placeholder="Ex: BACK Under 2.5 Entrada 10min" style={{ width: "100%" }} />
        </Field>

        <Field label="Descricao (opcional)">
          <input type="text" value={form.descricao} onChange={(e) => update("descricao", e.target.value)}
            placeholder="Breve resumo da estrategia" style={{ width: "100%" }} />
        </Field>

        <Field label="Mercado">
          <select value={form.mercado} onChange={(e) => handleMercadoChange(e.target.value)} style={{ width: "100%" }}>
            {MERCADOS.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
          </select>
        </Field>

        <Field label="Direcao da aposta">
          <select value={form.direcao} onChange={(e) => update("direcao", e.target.value)} style={{ width: "100%" }}>
            {dirs.map((d) => <option key={d.value} value={d.value}>{d.label}</option>)}
          </select>
        </Field>

        <Field label="Tempo de jogo para operar">
          <select value={form.tempo_entrada} onChange={(e) => update("tempo_entrada", e.target.value)} style={{ width: "100%" }}>
            {TEMPOS.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
        </Field>

        <Field label="Entrar ate quantos minutos de jogo" hint="Apos esse minuto, o bot nao entra mais nesse jogo.">
          <input type="number" min="0" value={form.entrada_minutos_max}
            onChange={(e) => update("entrada_minutos_max", e.target.value)} style={{ width: "100%" }} />
        </Field>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <Field label="Odd minima de entrada">
            <input type="number" step="0.01" min="1" value={form.odd_minima}
              onChange={(e) => update("odd_minima", e.target.value)}
              placeholder="ex: 1.10" style={{ width: "100%" }} />
          </Field>
          <Field label="Odd maxima de entrada">
            <input type="number" step="0.01" min="1" value={form.odd_maxima}
              onChange={(e) => update("odd_maxima", e.target.value)}
              placeholder="ex: 1.90" style={{ width: "100%" }} />
          </Field>
        </div>

        <Field label="Liquidez minima no mercado (£)" hint="Dinheiro minimo disponivel pra considerar entrada segura.">
          <input type="number" min="0" value={form.liquidez_minima}
            onChange={(e) => update("liquidez_minima", e.target.value)} style={{ width: "100%" }} />
        </Field>

        <Field label="Regra de saida">
          <select value={form.saida_tipo} onChange={(e) => update("saida_tipo", e.target.value)} style={{ width: "100%" }}>
            {SAIDAS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
        </Field>

        {(form.saida_tipo === "MINUTOS" || form.saida_tipo === "MINUTOS_OU_LUCRO") && (
          <Field label="Sair apos quantos minutos da entrada">
            <input type="number" min="1" value={form.saida_minutos}
              onChange={(e) => update("saida_minutos", e.target.value)} style={{ width: "100%" }} />
          </Field>
        )}

        {(form.saida_tipo === "LUCRO_PCT" || form.saida_tipo === "MINUTOS_OU_LUCRO") && (
          <Field label="Sair com quanto % de lucro">
            <input type="number" min="1" value={form.saida_lucro_pct}
              onChange={(e) => update("saida_lucro_pct", e.target.value)} style={{ width: "100%" }} />
          </Field>
        )}

        <Field label="Stake fixo (R$)">
          <input type="number" min="1" value={form.stake_fixo}
            onChange={(e) => update("stake_fixo", e.target.value)} style={{ width: "100%" }} />
        </Field>

        <Field label="Modo">
          <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14 }}>
            <input type="checkbox" checked={form.modo_simulacao}
              onChange={(e) => update("modo_simulacao", e.target.checked)} />
            Simulacao (nao aposta dinheiro real)
          </label>
        </Field>

        {error && (
          <div className="error-box" style={{ marginBottom: "0.75rem" }}>{error}</div>
        )}
        {success && (
          <div style={{
            background: "var(--color-background-success)", color: "var(--color-text-success)",
            padding: "0.6rem 0.8rem", borderRadius: "var(--border-radius-md)",
            fontSize: 13, marginBottom: "0.75rem",
          }}>{success}</div>
        )}

        <button type="submit" disabled={saving} style={{ width: "100%" }}>
          {saving ? "Salvando..." : "Cadastrar bot"}
        </button>
      </form>

      <div>
        <h3 style={{ fontSize: 15, fontWeight: 500, margin: "0 0 1.25rem" }}>Bots cadastrados</h3>
        {loadingList && <p style={{ fontSize: 13, color: "var(--color-text-tertiary)" }}>Carregando...</p>}
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {bots.map((bot) => {
            const f = filtrosPorBot[bot.id] || {};
            return (
              <div key={bot.id} style={{
                background: "var(--color-background-primary)",
                border: "0.5px solid var(--color-border-tertiary)",
                borderRadius: "var(--border-radius-lg)",
                padding: "0.9rem 1rem",
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 6 }}>
                  <p style={{ fontWeight: 500, fontSize: 14, margin: 0 }}>{bot.nome}</p>
                  <BotStatusPill ativo={bot.ativo} />
                </div>
                {bot.descricao && (
                  <p style={{ fontSize: 12, color: "var(--color-text-secondary)", margin: "0 0 8px" }}>
                    {bot.descricao}
                  </p>
                )}
                <div style={{ fontSize: 12, color: "var(--color-text-tertiary)", display: "flex", flexWrap: "wrap", gap: "4px 12px", marginBottom: 8 }}>
                  {f.MERCADO && <span>Mercado: {f.MERCADO}</span>}
                  {f.DIRECAO && <span>Direcao: {f.DIRECAO}</span>}
                  {f.STAKE_FIXO && <span>Stake: R${f.STAKE_FIXO}</span>}
                  {f.ODD_MINIMA && <span>Odd min: {f.ODD_MINIMA}</span>}
                  {f.ODD_MAXIMA && <span>Odd max: {f.ODD_MAXIMA}</span>}
                  {f.LIQUIDEZ_MINIMA && <span>Liquidez: £{f.LIQUIDEZ_MINIMA}</span>}
                  {f.SAIDA_TIPO && <span>Saida: {f.SAIDA_TIPO}</span>}
                  {bot.modo_simulacao && <span>Simulacao</span>}
                </div>
                <button onClick={() => toggleAtivo(bot)} style={{ fontSize: 12 }}>
                  {bot.ativo ? "Marcar inativo" : "Marcar ativo"}
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

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
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); enviar(); }
  };

  return (
    <div className="chat-wrap">
      <div className="chat-messages">
        {mensagens.length === 0 && (
          <div className="chat-empty">
            <p>Pergunte sobre o desempenho do bot, filtros atuais ou peca sugestoes de ajuste.</p>
            <div className="chat-suggestions">
              {SUGESTOES_CHAT.map((s) => (
                <button key={s} className="chat-suggestion" onClick={() => enviar(s)}>{s}</button>
              ))}
            </div>
          </div>
        )}
        {mensagens.map((m, i) => (
          <div key={i} className={`chat-msg ${m.role === "user" ? "chat-msg-user" : "chat-msg-assistant"}`}>
            {m.content}
          </div>
        ))}
        {enviando && <div className="chat-msg chat-msg-loading">Pensando...</div>}
      </div>
      {erro && <div className="error-box">{erro}</div>}
      <div className="chat-input-row">
        <textarea className="chat-input" rows={1} placeholder="Pergunte algo sobre esse bot..."
          value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={handleKeyDown} />
        <button className="chat-send" onClick={() => enviar()} disabled={enviando || !input.trim()}>Enviar</button>
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
        <input type="number" step="0.01" value={valor}
          onChange={(e) => setValor(e.target.value)} className="filtro-input" />
        {meta.copa && (
          <>
            <span className="filtro-copa-label">copa</span>
            <input type="number" step="0.01" value={valorCopa}
              onChange={(e) => setValorCopa(e.target.value)} className="filtro-input filtro-input-copa" />
          </>
        )}
        <button className={`btn-salvar ${sujo ? "btn-salvar-ativo" : ""}`}
          onClick={salvar} disabled={!sujo || salvando}>
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
  const [todosBots, setTodosBots] = useState([]);
  const [botId, setBotId] = useState(() => localStorage.getItem("betbots_bot_id") || BOT_ID);
  const [tab, setTab] = useState("analises");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [lastUpdate, setLastUpdate] = useState(null);
  const [salvandoChave, setSalvandoChave] = useState(null);

  const bot = todosBots.find((b) => b.id === botId) || null;

  const trocarBot = (novoId) => {
    setBotId(novoId);
    localStorage.setItem("betbots_bot_id", novoId);
  };

  const carregar = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const bots = await sb("bots?select=*&order=criado_em.asc");
      setTodosBots(bots);

      const idAtivo = bots.find((b) => b.id === botId) ? botId : bots[0]?.id;
      if (idAtivo && idAtivo !== botId) setBotId(idAtivo);

      if (!idAtivo) {
        setAnalises([]); setApostas([]); setFiltros([]);
        setLastUpdate(new Date()); return;
      }

      const [an, ap, fl] = await Promise.all([
        sb(`analises?select=*&bot_id=eq.${idAtivo}&order=analisado_em.desc&limit=50`),
        sb(`apostas?select=*&bot_id=eq.${idAtivo}&order=apostado_em.desc&limit=50`),
        sb(`filtros?select=*&bot_id=eq.${idAtivo}`),
      ]);
      setAnalises(an);
      setApostas(ap);
      setFiltros(fl);
      setLastUpdate(new Date());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [botId]);

  useEffect(() => {
    carregar();
    const interval = setInterval(carregar, 30000);
    return () => clearInterval(interval);
  }, [carregar]);

  const salvarFiltro = async (chave, valor, valorCopa) => {
    setSalvandoChave(chave);
    try {
      const body = { valor: parseFloat(valor) };
      if (valorCopa !== null && valorCopa !== "") body.valor_copa = parseFloat(valorCopa);
      await sbPatch(`filtros?chave=eq.${chave}&bot_id=eq.${botId}`, body);
      setFiltros((prev) => prev.map((f) => (f.chave === chave ? { ...f, ...body } : f)));
    } catch (e) {
      setError(`Erro ao salvar ${chave}: ${e.message}`);
    } finally {
      setSalvandoChave(null);
    }
  };

  const hoje = new Date().toISOString().slice(0, 10);
  const analisadosHoje = analises.filter((a) => (a.analisado_em || "").startsWith(hoje));
  const aprovadosHoje = analisadosHoje.filter((a) => a.aprovado);
  const taxa = analisadosHoje.length ? Math.round((aprovadosHoje.length / analisadosHoje.length) * 100) : 0;

  const ABAS = [
    { id: "analises", label: "Analises" },
    { id: "apostas", label: "Apostas" },
    { id: "filtros", label: "Filtros" },
    { id: "chat", label: "Chat IA" },
    { id: "estrategias", label: "Estrategias" },
  ];

  return (
    <div className="app">
      <div className="header">
        <div className="header-left">
          <span className={`dot ${bot?.ativo ? "dot-on" : "dot-off"}`} />
          {todosBots.length > 1 ? (
            <select className="bot-select" value={botId || ""} onChange={(e) => trocarBot(e.target.value)}>
              {todosBots.map((b) => <option key={b.id} value={b.id}>{b.nome}</option>)}
            </select>
          ) : (
            <span className="bot-name">{bot?.nome || "Carregando..."}</span>
          )}
          {bot?.modo_simulacao && <span className="tag">simulacao</span>}
        </div>
        <div className="header-right">
          {lastUpdate && <span className="updated-at">atualizado {fmtHora(lastUpdate)}</span>}
          <button className="btn" onClick={carregar} disabled={loading}>
            {loading ? "Atualizando..." : "Atualizar"}
          </button>
        </div>
      </div>

      {error && <div className="error-box">{error}</div>}

      {tab !== "estrategias" && (
        <div className="metrics">
          <MetricCard label="Analisados hoje" value={analisadosHoje.length} />
          <MetricCard label="Aprovados hoje" value={aprovadosHoje.length} />
          <MetricCard label="Taxa de aprovacao" value={`${taxa}%`} />
        </div>
      )}

      <div className="tabs">
        {ABAS.map((a) => (
          <button key={a.id} className={tab === a.id ? "tab tab-active" : "tab"} onClick={() => setTab(a.id)}>
            {a.label}
          </button>
        ))}
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
                <tr><td colSpan={4} className="empty">Nenhuma analise registrada ainda.</td></tr>
              )}
              {analises.map((a) => (
                <tr key={a.id}>
                  <td>{a.nome_jogo}<div className="sub">{a.competition}</div></td>
                  <td><StatusBadge aprovado={a.aprovado} /></td>
                  <td className="muted">{a.aprovado ? a.ia_motivo || "—" : (a.motivos || []).join(", ") || "—"}</td>
                  <td className="muted" style={{ textAlign: "right" }}>{fmtHora(a.analisado_em)}</td>
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
                <tr><td colSpan={5} className="empty">Nenhuma aposta registrada ainda.</td></tr>
              )}
              {apostas.map((a) => (
                <tr key={a.id}>
                  <td>{a.nome_jogo}</td>
                  <td>{a.odd_lay ?? "—"}</td>
                  <td>{a.status}</td>
                  <td>{a.pnl != null ? a.pnl : "—"}</td>
                  <td className="muted" style={{ textAlign: "right" }}>{fmtHora(a.apostado_em)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "filtros" && (() => {
        const estrategia = bot?.estrategia || "CORRECT_SCORE";
        const usaGruposFixos = estrategia === "CORRECT_SCORE" || !estrategia;

        if (usaGruposFixos) {
          return (
            <div className="filtros-wrap">
              {FILTROS_GRUPOS.map((grupo) => (
                <div className="filtro-grupo" key={grupo.nome}>
                  <h3 className="filtro-grupo-titulo">{grupo.nome}</h3>
                  {grupo.campos.map((meta) => {
                    const linha = filtros.find((f) => f.chave === meta.chave);
                    return (
                      <CampoFiltro key={meta.chave} meta={meta} linha={linha}
                        onSalvar={salvarFiltro} salvando={salvandoChave === meta.chave} />
                    );
                  })}
                </div>
              ))}
              <p className="footer-note">As alteracoes valem em ate 5 minutos.</p>
            </div>
          );
        }

        const filtrosNumericos = filtros.filter((f) => f.valor !== null && f.valor_texto === null);
        const filtrosTexto = filtros.filter((f) => f.valor_texto !== null);

        return (
          <div className="filtros-wrap">
            {filtrosNumericos.length > 0 && (
              <div className="filtro-grupo">
                <h3 className="filtro-grupo-titulo">Parametros numericos</h3>
                {filtrosNumericos.map((f) => {
                  const meta = FILTROS_LABELS[f.chave] || { label: f.chave, tipo: "numero" };
                  return (
                    <CampoFiltro key={f.chave} meta={{ chave: f.chave, label: meta.label }}
                      linha={f} onSalvar={salvarFiltro} salvando={salvandoChave === f.chave} />
                  );
                })}
              </div>
            )}
            {filtrosTexto.length > 0 && (
              <div className="filtro-grupo">
                <h3 className="filtro-grupo-titulo">Parametros de configuracao</h3>
                {filtrosTexto.map((f) => {
                  const meta = FILTROS_LABELS[f.chave] || { label: f.chave, tipo: "texto" };
                  return (
                    <div key={f.chave} className="filtro-row">
                      <div className="filtro-label">
                        <span>{meta.label}</span>
                      </div>
                      <div className="filtro-inputs">
                        <span style={{ fontSize: 13, color: "var(--color-text-secondary)", padding: "0 8px" }}>
                          {f.valor_texto}
                        </span>
                        <span style={{ fontSize: 11, color: "var(--color-text-tertiary)" }}>
                          (altere via aba Estrategias)
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
            <p className="footer-note">As alteracoes nos parametros numericos valem em ate 5 minutos.</p>
          </div>
        );
      })()}

      {tab === "chat" && bot && <ChatIA botId={bot.id} />}

      {tab === "estrategias" && <EstrategiasTab />}

      {tab !== "filtros" && tab !== "chat" && tab !== "estrategias" && (
        <p className="footer-note">Atualiza automaticamente a cada 30s.</p>
      )}
    </div>
  );
}
