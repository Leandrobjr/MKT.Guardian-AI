-- Fluxo de aprovação editorial pelo Desktop.

alter table public.mkt_campaigns
    drop constraint if exists mkt_campaigns_status_check;

alter table public.mkt_campaigns
    add constraint mkt_campaigns_status_check check (status in (
        'GERANDO',
        'AGUARDANDO_APROVACAO_HISTORIA',
        'PRODUZIDA',
        'AGUARDANDO_APROVACAO_FINAL',
        'AJUSTE_SOLICITADO',
        'APROVADA',
        'PRONTA_PARA_PUBLICAR',
        'PUBLICANDO',
        'PUBLICADA',
        'ERRO_PUBLICACAO',
        'REJEITADA'
    ));

alter table public.mkt_campaign_commands
    drop constraint if exists mkt_campaign_commands_action_check;

alter table public.mkt_campaign_commands
    add constraint mkt_campaign_commands_action_check check (
        action in ('PUBLISH', 'RETRY', 'APPROVE', 'REJECT', 'REQUEST_REVISION')
    );

create unique index if not exists mkt_campaign_commands_pending_editorial_idx
    on public.mkt_campaign_commands (campaign_id)
    where status in ('PENDING', 'CLAIMED')
      and action in ('APPROVE', 'REJECT', 'REQUEST_REVISION');
