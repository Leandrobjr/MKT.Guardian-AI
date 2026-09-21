# Ponte Supabase — Linux ↔ Desktop

## Fluxo

1. O Linux gera a campanha e sincroniza `mkt_campaigns`.
2. O asset é enviado para o bucket privado `mkt-campaign-assets`.
3. O Desktop autenticado consulta campanhas com status e metadata.
4. Após a confirmação humana, o Desktop insere um comando `PUBLISH`.
5. O processo Linux reivindica comandos com `claim_pending_commands()`.
6. O Linux publica e registra o resultado com `complete_command()`.

Para conferir a fila sem alterar nada:

```bash
python3 campaign_command_worker.py
```

Esse comando executa `dry-run` por padrão. A opção `--execute` é necessária
para uma publicação real e exige que a aprovação humana já esteja registrada.
Além da aprovação humana, o worker exige `metadata.qa.multimodal_passed=true`.
Campanhas sem QA multimodal aprovada são bloqueadas, mesmo que estejam em
`APROVADA` ou `PRONTA_PARA_PUBLICAR`.
O worker automatiza Meta/Instagram; TikTok continua exigindo o pacote manual.

## Configuração do Linux

Preencher somente no `.env` do backend:

```text
SUPABASE_CAMPAIGN_SYNC=true
SUPABASE_URL=https://<projeto>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<segredo-do-backend>
SUPABASE_CAMPAIGN_BUCKET=mkt-campaign-assets
```

`SUPABASE_SERVICE_ROLE_KEY` não pode ser usado no Desktop, navegador, logs ou
repositório. A sincronização permanece desativada por padrão.

## Contrato do Desktop

O Desktop deve usar sessão autenticada e chave publishable. O perfil precisa
estar `ACTIVE` e ter `role = ADMIN`.

O módulo `desktop_campaign_client.py` implementa esse contrato para uma
interface Python/Desktop existente:

- `list_campaigns()` para a tela de campanhas;
- `create_asset_url()` para visualização temporária;
- `request_publication(..., confirmed=True)` para confirmação humana;
- `list_commands()` para acompanhar o resultado.

No ambiente do Desktop, configure apenas:

```text
SUPABASE_URL=https://<projeto>.supabase.co
SUPABASE_PUBLISHABLE_KEY=<chave-publicável>
```

- leitura: `public.mkt_campaigns`;
- leitura e criação de comando: `public.mkt_campaign_commands`;
- leitura de asset: Storage `mkt-campaign-assets`;
- ação de publicação: inserir `{ campaign_id, action: "PUBLISH", requested_by: user.id }`.

O Desktop não atualiza o status do comando e não faz upload. O backend Linux
reivindica e finaliza o comando, evitando dupla execução pelo índice único de
publicações pendentes.

## Segurança

- As tabelas e o bucket são privados e têm RLS habilitado.
- O Linux é o único caminho para gravar campanha, asset e resultado.
- Caminhos locais são confinados ao diretório do projeto e extensões/tamanho
  são validados antes do upload.
- O resultado persistido aceita somente identificadores e estados mínimos; não
  grava tokens nem respostas brutas das APIs.
