# MIGRATION AUDIT — V2 Foundation

**Data:** 2026-08-08  
**Base analisada:** `main`  
**Branch de trabalho:** `refactor/v2-foundation`  
**Regra:** esta etapa não altera a lógica de produção.

## 1. Resumo executivo

O projeto atual já possui uma arquitetura funcional, porém as responsabilidades estão concentradas em scripts de processo. Os dois principais bots (`bot_prelive.py` e `bot_under25.py`) reutilizam infraestrutura de Betfair, Supabase e Telegram, mas cada processo também contém regras, persistência, logging e controle de loop.

A migração recomendada é incremental:

```text
LEGACY
  |
  +--> adapters (Betfair / Supabase / Telegram)
  |
  +--> domain (snapshot / signal / order / position / result)
  |
  +--> strategies (PreLive LAY / Under25)
  |
  +--> risk
  |
  +--> execution (PAPER / LIVE)
  |
  +--> research / backtest
```

**Não apagar nem substituir os scripts atuais nesta fase.**

---

## 2. `bot_prelive.py`

O bot Pre-Live concentra:

- descoberta e análise de jogos;
- filtros Correct Score;
- filtros Match Odds;
- filtros Over 1.5;
- filtros BTTS;
- regras específicas de favorito;
- razão entre odds;
- janela temporal;
- liquidez;
- persistência diária de aprovados;
- persistência de reprovados;
- histórico completo para backtest;
- integração Supabase;
- integração Telegram;
- acompanhamento pós-aprovação;
- integração com `apostas.py`;
- monitoramento/saúde;
- opção de análise via IA.

### Parâmetros encontrados

```text
LIQUIDEZ_MINIMA_CS_DISPONIVEL = 150
LIQUIDEZ_MINIMA_CS_TOTAL      = 500
LIQUIDEZ_MINIMA_GOALS         = 1000
MINUTOS_ANTES_INICIO          = 5
MINUTOS_APOS_INICIO           = 15
INTERVALO_VERIFICACAO         = 5 min
INTERVALO_LONGE               = 15 min
LIMIAR_JANELA_ENTRADA         = 30 min
INTERVALO_RECARGA_HORAS       = 0.25
INTERVALO_RESULTADO_MIN       = 30 min
HORA_HEARTBEAT                = 8
ODD_10_MINIMA                 = 0
ODD_10_MAXIMA                 = 25.0
ODD_01_MINIMA                 = 0
ODD_01_MAXIMA                 = 18.0
ODD_FAVORITO_MAX              = 2.20
ODD_FAVORITO_MAX_COPA         = 2.50
ODD_OVER15_MINIMA             = 1.10
ODD_OVER15_MAXIMA             = 1.35
ODD_OVER15_MAXIMA_COPA        = 1.50
ODD_BTTS_MINIMA               = 1.55
ODD_BTTS_MAXIMA               = 2.30
ODD_BTTS_MAXIMA_COPA          = 2.60
APENAS_LAY_01                 = True
APENAS_LAY_10                 = False
RAZAO_ODD_MAXIMA              = 1.8
ODD_FAVORITO_SUSPEITO         = 1.15
RAZAO_10_01_MAX_FAVORITO_FORTE= 0.75
MAX_ERROS_CONSECUTIVOS        = 5
ESPERA_APOS_ERRO              = 30 sec
MOVIMENTO_SUBIDA_ALERTA       = 0.20
MOVIMENTO_QUEDA_ALERTA        = 0.15
INTERVALO_MONITOR_ODDS        = 90 sec
QUEDA_SAIDA_PERCENTUAL        = 0.20
MINUTOS_MONITOR_POS_KICK      = 15
IA_ATIVA                      = False
IA_MODELO                     = gemini-flash-latest
```

O próprio código indica que alguns filtros podem ser sobrescritos pelo Supabase. Isso significa que a configuração efetiva em runtime não é necessariamente igual às constantes do arquivo.

### Ponto crítico

`RAZAO_ODD_MAXIMA = 1.8` aparece no Pre-Live e precisa ser comparada com **todas** as implementações de backtest antes de qualquer normalização.

Também há regra explícita `APENAS_LAY_01 = True`, que força o runner 0-1 independentemente das odds na rotina de apostas.

---

## 3. `bot_under25.py`

O Under 2.5 trabalha em jogos ao vivo no mercado `OVER_UNDER_25`.

### Parâmetros atuais encontrados

```text
INTERVALO_LOOP          = 60 sec
ODD_MINIMA             = 1.8
ODD_MAXIMA             = 2.1
LIQUIDEZ_MINIMA        = 150.0
STAKE_FIXO             = 50.0
ENTRADA_MINUTOS_MAX    = 5
SAIDA_MINUTOS          = 10
SAIDA_LUCRO_PCT        = 10.0
```

Os valores podem ser substituídos por `sb.carregar_filtros()`.

### Entrada

1. Lista mercados ao vivo do tipo `OVER_UNDER_25`.
2. Identifica o runner Under 2.5.
3. Calcula minuto do jogo.
4. Rejeita se o minuto exceder `ENTRADA_MINUTOS_MAX`.
5. Consulta back e liquidez.
6. Valida odd no intervalo.
7. Valida liquidez.
8. A liquidez mínima é reduzida nos primeiros minutos:
   - minuto <= 2: mínimo efetivo até £50;
   - minuto <= 4: mínimo efetivo até £100.
9. Cria uma posição em `apostas_ativas`.
10. Registra no Supabase e Telegram.

### Saída

O PnL estimado para BACK Under 2.5 é calculado como:

```text
pnl = stake * (odd_entrada / odd_atual - 1)
```

A posição é encerrada quando:

- `lucro_pct >= SAIDA_LUCRO_PCT`; ou
- `minutos_passados >= SAIDA_MINUTOS`.

### Observação crítica

O código atual chama isso de saída automática, mas a implementação mostrada registra o resultado, envia Telegram e remove a posição de `apostas_ativas`; não existe uma chamada de `placeOrders` de saída dentro de `verificar_saidas`. Portanto, antes de transformar isso em `ExecutionEngine`, precisamos confirmar se o comportamento pretendido é apenas simulação/contabilização ou se existe outro mecanismo externo de fechamento.

---

## 4. `betfair_client.py`

Responsabilidades atuais:

- carregar `.env`;
- autenticação certificada;
- guardar `SESSION_TOKEN`;
- cooldown de login de 30s;
- renovação de token a cada ~2h;
- logout;
- chamadas JSON-RPC;
- retries para erros transitórios;
- tratamento de `INVALID_SESSION`;
- `listMarketCatalogue`;
- `listMarketBook`;
- helpers `get_back` e `get_lay`;
- integração com `saude`.

### Decisão de arquitetura

Este módulo deve virar um **adapter Betfair**. Não devemos criar um segundo sistema de autenticação.

---

## 5. `apostas.py`

Responsabilidades atuais:

- cálculo de stake por liability;
- seleção do runner 1-0 ou 0-1;
- envio de `placeOrders` LAY;
- modo de simulação;
- leitura direta de `bot_prelive.APENAS_LAY_01/APENAS_LAY_10`.

### Fórmula encontrada

```text
stake = liability / (odd - 1)
```

com mínimo de £2.

Valores atuais:

```text
STAKE_LAY      = 11.0
LIABILITY_FIXA = 100.0
STAKE_MINIMO   = 2.0
MODO_SIMULACAO = True
```

**IMPORTante:** `LIABILITY_FIXA` é sobrescrita pelo Supabase no `bot_prelive.py`. Portanto, a configuração efetiva precisa ser auditada em runtime.

### Risco arquitetural

`apostas.py` importa `bot_prelive`, criando dependência circular conceitual entre estratégia e execução. Na V2 isso deve ser invertido:

```text
strategy -> OrderRequest -> RiskManager -> Execution
```

---

## 6. Supabase

O Supabase funciona como fonte dinâmica de filtros e armazenamento de análises/resultados.

Isso significa que a estratégia não deve carregar seus parâmetros exclusivamente de YAML/JSON. Na migração, devemos criar uma camada de configuração com precedência explícita:

```text
runtime override / Supabase
          |
          v
strategy config
          |
          v
safe defaults
```

A precedência exata deve ser documentada e testada.

---

## 7. Telegram

Telegram é usado como canal operacional para:

- entrada;
- saída;
- erro;
- heartbeat;
- avisos de liquidez;
- comandos.

Na V2, Telegram deve ser uma notificação/event adapter. A estratégia não deve depender diretamente de `enviar_mensagem()`.

---

## 8. Dados e persistência

O Pre-Live já salva:

- aprovados do dia;
- histórico completo de análises;
- reprovados do dia;
- dados de aposta;
- motivos de aprovação/reprovação.

Isso é valioso para a futura pesquisa, mas deve ser tratado como **dataset observacional** antes de ser usado em treinamento/otimização.

Regra obrigatória: nenhuma feature histórica pode usar informação que não estava disponível no instante da decisão.

---

## 9. Backtests

Foram identificados:

- `backtest_lay.py`;
- `backtest_lay_v2.py`;
- `backtest_filtro_favorito.py`;
- `ingest_historical_odds.py`.

Antes de unificar, precisamos comparar as fórmulas de ratio, filtros e definição de vitória/derrota.

**Não selecionar uma fórmula canônica por preferência.** A escolha precisa ser baseada na implementação de produção e/ou decisão explícita do proprietário da estratégia.

---

## 10. Principais riscos encontrados

### Alto

1. Execução e estratégia estão acopladas em `apostas.py`.
2. Configuração pode vir do Supabase e sobrescrever constantes.
3. `MODO_SIMULACAO` é uma variável dentro do módulo de execução.
4. `bot_under25.py` mantém posições apenas em memória.
5. Precisamos confirmar se a saída Under25 realmente envia ordem ou apenas calcula/contabiliza saída.

### Médio

6. Estado operacional espalhado por módulos globais.
7. Persistência em JSON local no Pre-Live.
8. Telegram está acoplado ao fluxo.
9. Backtests podem ter versões divergentes da regra.

### Baixo / estrutural

10. Nomes e responsabilidades podem ser normalizados depois dos testes.

---

## 11. Arquitetura V2 aprovada para implementação incremental

```text
MarketData / BetfairAdapter
          |
          v
     MarketSnapshot
          |
          v
      Strategy
     /        \
PreLive       Under25
     \        /
       Signal
          |
          v
     RiskManager
          |
     OrderRequest
          |
      +---+---+
      |       |
    PAPER    LIVE*

* bloqueado até aprovação humana.
```

---

## 12. Próxima fase obrigatória

**Não refatorar ainda.**

Criar testes de caracterização para funções puras e decisões de entrada/saída.

Prioridade:

1. fórmula de stake por liability;
2. seleção 0-1/1-0;
3. filtros Pre-Live;
4. filtros Under25;
5. cálculo de PnL Under25;
6. regras de saída;
7. precedência de configuração Supabase/default;
8. identificação de todas as fórmulas de ratio.

Critério de passagem:

> O teste deve provar o comportamento atual antes de qualquer mudança estrutural.

---

## 13. Regra para o Cline

Durante a Fase 1:

- não alterar produção;
- não alterar parâmetros;
- não corrigir ratio;
- não mudar stake;
- não mudar execução;
- não adicionar LIVE;
- não apagar arquivos;
- não fazer deploy.

Se houver ambiguidade, registrar `UNKNOWN` e parar para revisão.
