// Vercel Serverless Function — chat com IA sobre os dados do bot
// A API key da Anthropic fica SOMENTE aqui no servidor, nunca no frontend.

const SUPABASE_URL = "https://rxqotlcxujokzujodyhv.supabase.co";
const SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJ4cW90bGN4dWpva3p1am9keWh2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODE5ODMyMzUsImV4cCI6MjA5NzU1OTIzNX0.dWYvLVZCBTWGKpNcw4Ux53ojsN7BLI2OVHtA7mwKLaM";

async function sb(path) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, {
    headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` },
  });
  if (!res.ok) throw new Error(`Supabase erro ${res.status}`);
  return res.json();
}

async function montarContexto(botId) {
  const [bot, filtros, apostas, analisesRecentes] = await Promise.all([
    sb(`bots?id=eq.${botId}&select=*`),
    sb(`filtros?bot_id=eq.${botId}&select=*`),
    sb(`apostas?bot_id=eq.${botId}&select=*&order=apostado_em.desc&limit=100`),
    sb(`analises?bot_id=eq.${botId}&select=*&order=analisado_em.desc&limit=50`),
  ]);

  const comResultado = apostas.filter((a) => a.status !== "PENDENTE");
  const vitorias = comResultado.filter((a) => a.status === "VITORIA");
  const derrotas = comResultado.filter((a) => a.status === "PERDA");
  const pnlTotal = comResultado.reduce((acc, a) => acc + (Number(a.pnl) || 0), 0);
  const taxaAcerto = comResultado.length
    ? ((vitorias.length / comResultado.length) * 100).toFixed(1)
    : "N/A";

  return {
    bot: bot[0] || {},
    filtros_atuais: filtros.map((f) => ({
      chave: f.chave,
      valor: f.valor,
      valor_copa: f.valor_copa,
      descricao: f.descricao,
    })),
    resumo_apostas: {
      total: comResultado.length,
      vitorias: vitorias.length,
      derrotas: derrotas.length,
      taxa_acerto_pct: taxaAcerto,
      pnl_total: pnlTotal.toFixed(2),
    },
    ultimas_apostas: apostas.slice(0, 20).map((a) => ({
      jogo: a.nome_jogo,
      competition: a.competition,
      odd_lay: a.odd_lay,
      stake: a.stake,
      status: a.status,
      pnl: a.pnl,
      placar_final: a.placar_final,
    })),
    ultimas_analises_reprovadas: analisesRecentes
      .filter((a) => !a.aprovado)
      .slice(0, 15)
      .map((a) => ({ jogo: a.nome_jogo, motivos: a.motivos })),
  };
}

export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Método não permitido" });
  }

  const { mensagem, bot_id, historico } = req.body || {};
  if (!mensagem || !bot_id) {
    return res.status(400).json({ error: "Faltando 'mensagem' ou 'bot_id'" });
  }

  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    return res.status(500).json({ error: "ANTHROPIC_API_KEY não configurada no servidor" });
  }

  try {
    const contexto = await montarContexto(bot_id);

    const systemPrompt = `Você é um assistente especialista em trading esportivo (Betfair, estratégias de lay/back) ajudando a analisar e ajustar um bot de apostas automatizado.

Aqui estão os dados ATUAIS e REAIS do bot, vindos direto do banco de dados:

${JSON.stringify(contexto, null, 2)}

Use esses dados para responder com precisão. Seja direto, cite números reais quando relevante, e quando sugerir mudança de filtro, seja específico sobre qual chave e valor mudar. Responda em português do Brasil.`;

    const mensagens = [
      ...(historico || []).map((h) => ({ role: h.role, content: h.content })),
      { role: "user", content: mensagem },
    ];

    const resposta = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": apiKey,
        "anthropic-version": "2023-06-01",
      },
      body: JSON.stringify({
        model: "claude-sonnet-4-6",
        max_tokens: 1024,
        system: systemPrompt,
        messages: mensagens,
      }),
    });

    if (!resposta.ok) {
      const erro = await resposta.text();
      return res.status(502).json({ error: `Erro Anthropic: ${erro}` });
    }

    const data = await resposta.json();
    const texto = data.content
      .filter((b) => b.type === "text")
      .map((b) => b.text)
      .join("\n");

    return res.status(200).json({ resposta: texto });
  } catch (e) {
    return res.status(500).json({ error: e.message });
  }
}
