# Testes de caracterização

Esta pasta existe para registrar o comportamento atual do bot antes da refatoração.

## Ordem de implementação

1. `apostas.py::calcular_stake_por_liability`
2. `apostas.py::apostar_jogo_aprovado`
3. filtros Pre-Live extraídos de `bot_prelive.py`
4. filtros/entrada Under25
5. PnL Under25
6. regras de saída Under25
7. precedência de filtros Supabase/default
8. ratio em todas as versões do projeto

## Regra

Os testes devem usar fixtures determinísticas e não podem enviar chamadas reais para a Betfair, Supabase ou Telegram.

Antes de extrair uma função para a V2, primeiro crie um teste que descreva o comportamento do legado.

Não corrija diferenças durante esta etapa. Diferenças devem virar testes/itens de decisão.
