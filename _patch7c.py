lines = open('src/App.jsx').readlines()

# Encontra a linha de inicio e fim do bloco filtros
start = None
end = None
for i, l in enumerate(lines):
    if 'tab === "filtros" && (() => {' in l:
        start = i
    if start and '})()}' in l:
        end = i
        break

print(f'Bloco encontrado: linhas {start+1} a {end+1}')

new_block = '''      {tab === "filtros" && (
        <div className="filtros-wrap">
          {filtros.length === 0 && (
            <p className="empty">Nenhum filtro cadastrado para este bot.</p>
          )}
          {(() => {
            const filtrosNumericos = filtros.filter((f) => f.valor !== null && f.valor_texto === null);
            const filtrosTexto = filtros.filter((f) => f.valor_texto !== null);
            return (
              <>
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
              </>
            );
          })()}
          <p className="footer-note">As alteracoes nos parametros numericos valem em ate 5 minutos.</p>
        </div>
      )}
'''

if start is None or end is None:
    print('ERRO: bloco nao encontrado')
else:
    result = lines[:start] + [new_block] + lines[end+1:]
    open('src/App.jsx', 'w').writelines(result)
    print('OK - ficheiro gravado')
