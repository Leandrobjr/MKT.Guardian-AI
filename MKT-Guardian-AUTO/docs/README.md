# Documentos legais — Plataforma de Campanhas (MKT-GUARDIAN-AUTO)

Pasta com conteúdo pronto para publicar em:

| URL no site | Arquivo fonte |
|-------------|---------------|
| https://guardian-ai.app/MKT-GUARDIAN-AUTO | `web/index.html` |
| https://guardian-ai.app/MKT-GUARDIAN-AUTO/termos_mkt | `termos_mkt.md` + `web/termos_mkt.html` |
| https://guardian-ai.app/MKT-GUARDIAN-AUTO/privacidade_mkt | `privacidade_mkt.md` + `web/privacidade_mkt.html` |

## Arquivos

- `termos_mkt.md` — Termos de Uso (versão Markdown / revisão)
- `privacidade_mkt.md` — Política de Privacidade (versão Markdown / revisão)
- `avisos_ui.md` — textos curtos de login e rodapé
- `web/` — páginas HTML estáticas para deploy no site

## Operador

L&M ADMINISTRAÇÃO E PARTICIPAÇÕES LTDA  
CNPJ: 27.629.805/0001-55  
Contato: admin@guardian-ai.app  
Foro: Goiânia — GO

## Observação de deploy

O formulário de login em `web/index.html` está com `action="#"`. Conecte ao fluxo real de autenticação do site `guardian-ai.app` antes de colocar em produção. As páginas usam `noindex` para não indexar área interna.
