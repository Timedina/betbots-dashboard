# Análise de Perda — FC Basel v Lausanne (Swiss Super League)

**Data:** 02/08/2026
**Estratégia:** LAY Correct Score
**event_id:** 35866765
**market_id_cs:** 1.260436259

## Dados da aposta

| Campo | Valor |
|---|---|
| Odd 1-0 (odd_10) | 13.5 |
| Odd 0-1 (odd_01) | 22.0 |
| Odd favorito (FC Basel) | 1.94 |
| Liquidez disponível | £1.440,46 |
| Liquidez total do mercado | £13.480,48 |
| Placar escolhido para LAY | 0-1 (maior odd, mais improvável) |
| Odd lay usada | 22.0 |
| Stake | 4,76 |
| Liability | £100 (fixa) |
| Placar final | 0-1 |
| Resultado | **PERDA** |
| PnL | **-£100,00** |

## Diagnóstico

O bot entrou no LAY do placar 0-1 por ter a maior odd (22.0 vs 13.5 do 1-0), seguindo a lógica padrão da estratégia: apostar contra o resultado mais improvável do mercado. A odd de 22.0 implica uma probabilidade de ~4,5% para esse placar — ou seja, estatisticamente esperado que aconteça em torno de 1 a cada 22 ocorrências, mesmo com o bot funcionando corretamente.

**Não foram encontrados sinais de bug ou dado suspeito:**
- Liquidez disponível (£1.440) e liquidez total (£13.480) são razoáveis, não indicam mercado fino/ilíquido.
- Odd do favorito (1.94) é moderada, dentro do esperado.
- Razão odd_01/odd_10 = 22.0/13.5 ≈ 1,63 — dentro do limite configurado (`RAZAO_ODD_MAXIMA = 1.8`).
- Todos os filtros (`ODD_01_MAXIMA`, razão de odds, sanity-check de favorito suspeito) foram respeitados.

## Comparação com o caso da Irlanda (que originou o filtro `ODD_FAVORITO_SUSPEITO`)

| | Irlanda (caso anterior) | Suíça (este caso) |
|---|---|---|
| Causa suspeita | Dado de mercado fino/distorcido | Nenhuma — variância normal |
| Liquidez | Muito baixa (mercado fino) | Razoável (£1.440 disp. / £13.480 total) |
| Conclusão | Motivou criação de filtro de sanity-check | Resultado esperado da estratégia, sem indício de bug |

## Recomendação

Não ajustar filtros com base neste caso isolado (n=1 por liga no momento). A tabela por liga no dashboard ainda tem amostra muito pequena (a maioria das ligas também com n=1) — insuficiente para qualquer conclusão estatística sobre desempenho por liga. Seguir acumulando dados antes de considerar exclusão ou ajuste de filtro para Swiss Super League especificamente.

---
*Análise gerada em conversa de suporte — 03/08/2026*
