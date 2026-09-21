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

O fluxo editorial é:

1. O Desktop exibe a imagem/vídeo, headline, roteiro e evidência da QA.
2. O revisor escolhe `Aprovar`, `Rejeitar` ou `Solicitar ajuste`.
3. O navegador cria apenas um comando assinado pela sessão; ele não altera
   diretamente a campanha.
4. O worker Linux executa a decisão e registra usuário, versão e motivo.
   Em `Solicitar ajuste`, ele usa o motivo para regenerar o visual, executa
   QA multimodal obrigatória (com até uma nova tentativa orientada pelos
   achados) e devolve a campanha para `AGUARDANDO_APROVACAO_FINAL`.
5. Somente depois de aprovada a campanha pode receber um comando `PUBLISH`.

Para testar decisões editoriais sem alterar o Supabase:

```bash
python3 campaign_command_worker.py
```

Para processar decisões e publicar de fato, use `--execute` somente após
aplicar a migração editorial e validar o ambiente. Mesmo com confirmação
humana, o worker bloqueia campanhas sem QA multimodal aprovada registrada no
metadata.

Para manter o worker ativo automaticamente no Ubuntu, instale a unidade
`deploy/guardian-campaign-worker.service` no systemd do usuário:

```bash
mkdir -p ~/.config/systemd/user
cp deploy/guardian-campaign-worker.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now guardian-campaign-worker.service
systemctl --user status guardian-campaign-worker.service
```

O modo contínuo recupera comandos `CLAIMED` abandonados após 30 minutos,
impede dois workers do mesmo projeto com lock local e não repete comandos já
concluídos. `--execute` não publica automaticamente: a publicação só ocorre
quando existe um comando `PUBLISH` confirmado no Desktop.

Em produção, hospede a interface em HTTPS e fixe a versão do cliente
`supabase-js` no processo de build.
