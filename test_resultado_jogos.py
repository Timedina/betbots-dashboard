import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resultado_jogos as rj

COM = 0.0636


class TestPnl(unittest.TestCase):
    def test_pnl_varia_com_odd(self):
        i15 = {'liability': 100.0, 'odd_lay': 15.0, 'stake': 0, 'odd_10': 15.0, 'odd_01': 0, 'placar_lay': '1-0'}
        i12 = {'liability': 100.0, 'odd_lay': 12.0, 'stake': 0, 'odd_10': 12.0, 'odd_01': 0, 'placar_lay': '1-0'}
        r15 = rj.determinar_resultado_lay('0-0', i15)
        r12 = rj.determinar_resultado_lay('0-0', i12)
        self.assertEqual(r15['resultado_geral'], 'VITORIA')
        self.assertEqual(r12['resultado_geral'], 'VITORIA')
        self.assertNotEqual(r15['pnl_estimado'], r12['pnl_estimado'], 'BUG DO PNL FIXO VOLTOU')

    def test_formula_vitoria(self):
        i = {'liability': 100.0, 'odd_lay': 15.0, 'stake': 0, 'odd_10': 15.0, 'odd_01': 0, 'placar_lay': '1-0'}
        r = rj.determinar_resultado_lay('0-0', i)
        esperado = round((100.0 / 14) * (1 - COM), 2)
        self.assertEqual(r['pnl_estimado'], esperado)

    def test_formula_perda(self):
        i = {'liability': 100.0, 'odd_lay': 15.0, 'stake': 0, 'odd_10': 15.0, 'odd_01': 0, 'placar_lay': '1-0'}
