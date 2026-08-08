"""
Testes de PnL do resultado_jogos.py (modelo de execucao real: UM unico LAY).

A execucao (apostas.py) coloca apenas UM LAY (0-1 por padrao, APENAS_LAY_01=True)
com stake = liability/(odd-1) e liability fixa de LIABILITY_FIXA=100.
"""
import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resultado_jogos as rj

COM = 0.0636
LIAB = 100.0


class TestPnl(unittest.TestCase):
    def _criar(self, placar_lay='0-1', odd_lay=15.0, stake=0.0, odd_01=15.0):
        return {
            'liability': 0.0,
            'odd_lay': odd_lay,
            'stake': stake,
            'odd_10': 12.0,
            'odd_01': odd_01,
            'placar_lay': placar_lay,
        }

    def test_vitoria_quando_placar_diferente_do_lay(self):
        # LAY 0-1 @15, resultado 0-0 -> lay ganhou
        r = rj.determinar_resultado_lay('0-0', self._criar())
        self.assertEqual(r['resultado_geral'], 'VITORIA')
        esperado = round((LIAB / (15 - 1)) * (1 - COM), 2)
        self.assertEqual(r['pnl_estimado'], esperado)

    def test_perda_quando_placar_igual_ao_lay(self):
        # LAY 0-1 @15, resultado 0-1 -> lay perdeu (liability)
        r = rj.determinar_resultado_lay('0-1', self._criar())
        self.assertEqual(r['resultado_geral'], 'PERDA')
        self.assertAlmostEqual(r['pnl_estimado'], -100.0, places=2)

    def test_pnl_varia_com_odd(self):
        r15 = rj.determinar_resultado_lay('0-0', self._criar(odd_lay=15.0))
        r12 = rj.determinar_resultado_lay('0-0', self._criar(odd_lay=12.0))
        self.assertEqual(r15['resultado_geral'], 'VITORIA')
        self.assertNotEqual(r15['pnl_estimado'], r12['pnl_estimado'],
                            'BUG DO PNL FIXO VOLTOU')

    def test_usa_stake_gravado(self):
        r = rj.determinar_resultado_lay('0-0', self._criar(stake=7.5))
        self.assertEqual(r['pnl_estimado'], round(7.5 * (1 - COM), 2))

    def test_fallback_stake_por_liability(self):
        # sem stake gravado -> stake = liability/(odd-1)
        r = rj.determinar_resultado_lay('0-0', self._criar())
        esperado = round((LIAB / (15 - 1)) * (1 - COM), 2)
        self.assertEqual(r['pnl_estimado'], esperado)

    def test_placar_lay_gravado_respeitado(self):
        # LAY 1-0 gravado @12; placar 2-1 -> vitoria com odd do lay 1-0
        r = rj.determinar_resultado_lay('2-1', self._criar(placar_lay='1-0', odd_lay=12.0))
        self.assertEqual(r['resultado_geral'], 'VITORIA')
        self.assertEqual(r['pnl_estimado'], round((LIAB / 11) * (1 - COM), 2))

    def test_sem_placar_lay_usa_padrao_0_1(self):
        # fallback historico: LAY 0-1
        r = rj.determinar_resultado_lay('2-1', self._criar(placar_lay=None))
        self.assertEqual(r['resultado_geral'], 'VITORIA')

    def test_placar_vazio_pendente(self):
        r = rj.determinar_resultado_lay('', self._criar())
        self.assertIsNone(r['resultado_geral'])
        self.assertIsNone(r['pnl_estimado'])


if __name__ == '__main__':
    unittest.main()