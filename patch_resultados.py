"""
Execute este script na VM para adicionar o resumo automático de resultados ao bot_prelive.py
"""
import re

path = '/home/tmedina117/bot-prelive-betfair/bot_prelive.py'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Adicionar import do resultado_jogos no topo
if 'resultado_jogos' not in content:
    content = content.replace(
        'import betfair_client as bf',
        'import betfair_client as bf\ntry:\n    import resultado_jogos\n    RESULTADO_DISPONIVEL = True\nexcept ImportError:\n    RESULTADO_DISPONIVEL = False'
    )

# 2. Adicionar variável de controle do resumo após FUSO_BRASILIA
if 'HORA_RESUMO_RESULTADOS' not in content:
    content = content.replace(
        'PASTA_DADOS = \'dados_bot\'',
        'PASTA_DADOS = \'dados_bot\'\nHORA_RESUMO_RESULTADOS = 23  # Hora para enviar resumo de resultados'
    )

# 3. Adicionar variável ultima_verificacao_resultados no loop
if 'ultima_verificacao_resultados' not in content:
    content = content.replace(
        '    ultima_recarga          = datetime.now(timezone.utc)',
        '    ultima_recarga                  = datetime.now(timezone.utc)\n    ultima_verificacao_resultados   = None'
    )

# 4. Adicionar bloco de verificação de resultados no loop principal
bloco_resultados = '''
            # ============================================================
            # RESUMO DE RESULTADOS AS 23H
            # ============================================================
            agora_br = datetime.now(FUSO_BRASILIA)
            if RESULTADO_DISPONIVEL and agora_br.hour == HORA_RESUMO_RESULTADOS:
                data_hoje_str = agora_br.strftime('%Y-%m-%d')
                if ultima_verificacao_resultados != data_hoje_str:
                    print(f'  📊 Buscando resultados do dia...')
                    try:
                        resultado_jogos.atualizar_resultados_do_dia(verbose=True)
                        resumo = resultado_jogos.resumo_resultados()
                        enviar_mensagem(resumo)
                        ultima_verificacao_resultados = data_hoje_str
                        print(f'  ✅ Resumo de resultados enviado!')
                    except Exception as e:
                        print(f'  ⚠️ Erro ao buscar resultados: {e}')

'''

if 'RESUMO DE RESULTADOS AS 23H' not in content:
    content = content.replace(
        '            # Recarrega lista de jogos do dia a cada hora',
        bloco_resultados + '            # Recarrega lista de jogos do dia a cada hora'
    )

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print('✅ bot_prelive.py atualizado com sucesso!')
print('Verifique: grep -n "RESUMO DE RESULTADOS" ' + path)
