content = open('src/App.jsx', 'r').read()

# Substitui a aba de filtros estatica por uma dinamica
old = '''      {tab === "filtros" && (
          <div className="filtros-wrap">
            {FILTROS_GRUPOS.map((grupo) => (
              <div className="filtro-grupo" key={grupo.nome}>
                <h3 className="filtro-grupo-titulo">{grupo.nome}</h3>
                {grupo.campos.map((meta) => {
                  const linha = filtros.find((f) => f.chave === meta.chave);
                  return (
                    <CampoFiltro
                      key={meta.chave}
                      meta={meta}
                      linha={linha}
                      onSalvar={salvarFiltro}
                      salvando={salvandoChave === meta.chave}
                    />
                  );
                })}
              </div>
            ))}
            <p className="footer-note">
              As alteracoes valem em ate 5 minutos (o bot recarrega os filtros
              periodicamente).
            </p>
          </div>
        )}'''

new = '''      {tab === "filtros" && (
          <div className="filtros-wrap">
            {filtros.length === 0 && (
              <p className="empty">Nenhum filtro cadastrado para este bot.</p>
            )}
            {filtros.map((f) => (
              <div className="filtro-grupo" key={f.chave}>
                <div className="filtro-row">
                  <div className="filtro-label">
                    <span>{f.chave}</span>
                    {f.descricao && <span className="filtro-desc">{f.descricao}</span>}
                  </div>
                  <div className="filtro-inputs">
                    <CampoFiltroSimples
                      filtro={f}
                      onSalvar={salvarFiltro}
                      salvando={salvandoChave === f.chave}
                    />
                  </div>
                </div>
              </div>
            ))}
            <p className="footer-note">
              As alteracoes valem em ate 5 minutos (o bot recarrega os filtros
              periodicamente).
            </p>
          </div>
        )}'''

n = content.count(old)
print(f'Patch filtros dinamicos: {n}')
if n == 1:
    content = content.replace(old, new, 1)
    print('OK')
else:
    print('ERRO nao encontrado')
    # mostra contexto para debug
    idx = content.find('tab === "filtros"')
    print(repr(content[idx:idx+200]))

open('src/App.jsx', 'w').write(content)
