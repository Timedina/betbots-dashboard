import { useEffect, useState } from "react";
import { supabase } from "./supabaseClient";

export interface Aposta {
  id: string;
  bot_id: string;
  status: string;
  pnl: number | null;
  apostado_em: string;
  odd_lay: number | null;
}

export interface Estatisticas {
  totalApostas: number;
  vitorias: number;
  derrotas: number;
  winRate: number;
  pnlTotal: number;
  serieAcumulada: { data: string; pnlAcumulado: number }[];
  dataCorteAplicada: string | null;
}

const STATS_VAZIAS: Estatisticas = {
  totalApostas: 0,
  vitorias: 0,
  derrotas: 0,
  winRate: 0,
  pnlTotal: 0,
  serieAcumulada: [],
  dataCorteAplicada: null,
};

export function useEstatisticas(botId: string) {
  const [stats, setStats] = useState<Estatisticas>(STATS_VAZIAS);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    if (!botId) return;

    let cancelado = false;

    async function carregar() {
      setLoading(true);
      setErro(null);

      try {
        const { data: filtroCorte, error: erroFiltro } = await supabase
          .from("filtros")
          .select("valor_texto")
          .eq("bot_id", botId)
          .eq("chave", "DATA_CORTE_ESTATISTICAS")
          .maybeSingle();

        if (erroFiltro) throw erroFiltro;

        const dataCorte = filtroCorte?.valor_texto ?? null;

        let query = supabase
          .from("apostas")
          .select("id, bot_id, status, pnl, apostado_em, odd_lay")
          .eq("bot_id", botId)
          .in("status", ["VITORIA", "PERDA"])
          .order("apostado_em", { ascending: true });

        if (dataCorte) {
          query = query.gte("apostado_em", dataCorte);
        }

        const { data: apostas, error: erroApostas } = await query;
        if (erroApostas) throw erroApostas;

        const lista = (apostas ?? []) as Aposta[];

        const vitorias = lista.filter((a) => a.status === "VITORIA").length;
        const derrotas = lista.filter((a) => a.status === "PERDA").length;
        const totalApostas = vitorias + derrotas;
        const pnlTotal = lista.reduce((acc, a) => acc + (a.pnl ?? 0), 0);
        const winRate = totalApostas > 0 ? (vitorias / totalApostas) * 100 : 0;

        let acumulado = 0;
        const serieAcumulada = lista.map((a) => {
          acumulado += a.pnl ?? 0;
          return { data: a.apostado_em, pnlAcumulado: acumulado };
        });

        if (!cancelado) {
          setStats({
            totalApostas,
            vitorias,
            derrotas,
            winRate,
            pnlTotal,
            serieAcumulada,
            dataCorteAplicada: dataCorte,
          });
        }
      } catch (e) {
        if (!cancelado) setErro(e instanceof Error ? e.message : "Erro ao carregar estatisticas");
      } finally {
        if (!cancelado) setLoading(false);
      }
    }

    carregar();
    return () => {
      cancelado = true;
    };
  }, [botId]);

  return { stats, loading, erro };
}
