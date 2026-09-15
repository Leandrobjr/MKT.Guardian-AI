# Interface Desktop — Guardian AI

Dashboard web responsivo para revisão de campanhas no Desktop.

## Segurança

O navegador usa somente:

- `SUPABASE_URL`;
- `SUPABASE_PUBLISHABLE_KEY`;
- sessão autenticada do usuário.

Nunca use `SUPABASE_SERVICE_ROLE_KEY` nesta interface. A chave é digitada
apenas em memória e não é salva no navegador.

## Executar localmente

Na pasta `MKT-Guardian-AUTO`:

```bash
python3 -m http.server 8080 --bind 127.0.0.1 --directory desktop
```

Abra `http://127.0.0.1:8080`.

No formulário inicial, informe a URL do projeto Supabase e a chave
publishable. Depois entre com um usuário Supabase cujo perfil esteja
`ACTIVE` e tenha `role = ADMIN`.

O navegador não publica diretamente. Ele cria o comando `PUBLISH`; o worker
Linux executa a publicação após a confirmação:

```bash
python3 campaign_command_worker.py
```

O comando acima faz apenas `dry-run`. A execução real exige `--execute`.

Em produção, hospede a interface em HTTPS e fixe a versão do cliente
`supabase-js` no processo de build.
