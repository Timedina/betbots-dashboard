content = open('src/App.jsx', 'r').read()

old = '''      {tab === "filtros" && (() => {
        const estrategia = bot?.estrategia || "CORRECT_SCORE";
        const usaGruposFixos = estrategia === "CORRECT_SCORE" || !estrategia;
        if (usaGruposFixos) {
          return (
            <div className="filtros-wrap">
              {FILTROS_GRUPOS.map((grupo) => (
                <div className="filtro-grupo" key={grupo.nome}>
                  <h3 className="filtro-grupo-titulo">{grupo.nome}</h3>
                  {grupo.campos.map((meta) => {
                    const linha = filtros.find((f) => f.chave === meta.chave);
                    return (
                      <CampoFiltro key={meta.chave} meta={meta} linha={linha}
                        onSalvar={salvarFiltro} salvando={salvandoChave === meta.chave} />
                    );
                  })}
                </div>
              ))}
              <p className="footer-note">As alteracoes valem em ate 5 minutos.</p>
            </div>
          );
        }
        const filtrosNumericos = filtros.filter((f) => f.valor !== null && f.valor_texto === null);
        const filtrosTexto = filtros.filter((f) => f.valor_texto !== null);
        return (
          <div className="filtros-wrap">
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
            <p className="footer-note">As alteracoes nos parametros numericos valem em ate 5 minutos.</p>
          </div>
        );
      })()}'''

new = '''      {tab === "filtros" && (
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
      )}'''

n = content.count(old)
print(f'Patch filtros dinamicos: {n}')
if n == 1:
    content = content.replace(old, new, 1)
    open('src/App.jsx', 'w').write(content)
    print('OK - ficheiro gravado')
else:
    print('ERRO nao encontrado')
    idx = content.find('tab === "filtros"')
    print(repr(content[idx:idx+300]))
