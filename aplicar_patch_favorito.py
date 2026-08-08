#!/usr/bin/env python3
"""
Aplica o patch do filtro de sanity-check (odd_favorito vs odd_10/odd_01)
no bot_prelive.py. Faz backup antes de alterar.
"""
import shutil
import sys

ARQUIVO = "bot_prelive.py"

shutil.copy(ARQUIVO, ARQUIVO + ".bak_antes_filtro_favorito")
print(f"Backup criado: {ARQUIVO}.bak_antes_filtro_favorito")

with open(ARQUIVO, "r", encoding="utf-8") as f:
    conteudo = f.read()

# --- PATCH 1: adiciona as constantes do novo filtro ---
old1 = "RAZAO_ODD_MAXIMA = 1.8  # max razao odd_01/odd_10 para entrar"
new1 = (
    "RAZAO_ODD_MAXIMA = 1.8  # max razao odd_01/odd_10 para entrar\n"
    "ODD_FAVORITO_SUSPEITO = 1.15  # abaixo disso, favorito e considerado muito forte\n"
    "RAZAO_10_01_MAX_FAVORITO_FORTE = 0.75  # odd_10 deve ser <= 75% da odd_01 quando favorito for forte"
)
if conteudo.count(old1) != 1:
    print(f"ERRO: PATCH 1 - texto original encontrado {conteudo.count(old1)}x (esperado 1). Abortando.")
    sys.exit(1)
conteudo = conteudo.replace(old1, new1)

# --- PATCH 2: adiciona o filtro de sanity-check apos o filtro de razao ---
old2 = """    # Filtro de razao entre odds (evita desequilibrio extremo)
    if odd_10 and odd_10 > 0:
        razao = round(odd_01 / odd_10, 2)
        if razao > RAZAO_ODD_MAXIMA:
            resultado['motivo_reprovacao'].append(f'Razao odd_01/odd_10 alta: {razao} (max {RAZAO_ODD_MAXIMA})')
            return resultado

    resultado['market_id_cs']        = cs_mercado['marketId']"""
new2 = """    # Filtro de razao entre odds (evita desequilibrio extremo)
    if odd_10 and odd_10 > 0:
        razao = round(odd_01 / odd_10, 2)
        if razao > RAZAO_ODD_MAXIMA:
            resultado['motivo_reprovacao'].append(f'Razao odd_01/odd_10 alta: {razao} (max {RAZAO_ODD_MAXIMA})')
            return resultado

    # Filtro de sanity-check: favorito muito forte mas odd_10 nao reflete isso
    # (dados de Correct Score suspeitos/inconsistentes com o favoritismo real)
    if odd_favorito and odd_favorito <= ODD_FAVORITO_SUSPEITO and odd_10 and odd_10 > 0:
        razao_10_01 = odd_10 / odd_01
        if razao_10_01 > RAZAO_10_01_MAX_FAVORITO_FORTE:
            resultado['motivo_reprovacao'].append(
                f'Dados CS suspeitos: favorito forte (odd={odd_favorito}) mas odd_10/odd_01={razao_10_01:.2f}'
            )
            return resultado

    resultado['market_id_cs']        = cs_mercado['marketId']"""
if conteudo.count(old2) != 1:
    print(f"ERRO: PATCH 2 - texto original encontrado {conteudo.count(old2)}x (esperado 1). Abortando.")
    sys.exit(1)
conteudo = conteudo.replace(old2, new2)

with open(ARQUIVO, "w", encoding="utf-8") as f:
    f.write(conteudo)

print("Patch aplicado com sucesso em bot_prelive.py")
print("Rode: python3 -m py_compile bot_prelive.py  para checar a sintaxe")
