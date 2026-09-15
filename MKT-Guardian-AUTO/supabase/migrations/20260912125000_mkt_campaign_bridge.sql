-- Ponte Linux ↔ Desktop para campanhas Guardian AI.
-- O Linux usa service_role; clientes autenticados só acessam campanhas/comandos
-- autorizados por perfil ADMIN. Tokens nunca são armazenados nestas tabelas.

create table if not exists public.profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    status text not null default 'PENDING'
        check (status in ('PENDING', 'ACTIVE', 'ABANDONED')),
    role text not null default 'ADMIN',
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

alter table public.profiles enable row level security;

drop policy if exists profiles_select_own on public.profiles;
create policy profiles_select_own
    on public.profiles for select to authenticated
    using (id = auth.uid());

create table if not exists public.mkt_campaigns (
    campaign_id text primary key,
    version integer not null default 0 check (version >= 0),
    status text not null check (status in (
        'GERANDO',
        'AGUARDANDO_APROVACAO_HISTORIA',
        'PRODUZIDA',
        'AGUARDANDO_APROVACAO_FINAL',
        'APROVADA',
        'PRONTA_PARA_PUBLICAR',
        'PUBLICANDO',
        'PUBLICADA',
        'ERRO_PUBLICACAO',
        'REJEITADA'
    )),
    publico text not null default '',
    golpe text not null default '',
    canal text not null default '',
    midia text not null default '',
    basename text not null default '',
    storage_bucket text not null default 'mkt-campaign-assets',
    storage_path text not null default '',
    legenda text not null default '',
    roteiro text not null default '',
    preset jsonb not null default '{}'::jsonb,
    metadata jsonb not null default '{}'::jsonb,
    plataforma text not null default '',
    id_retornado text not null default '',
    mensagem_erro text not null default '',
    aprovado_por uuid references auth.users(id),
    data_criacao timestamptz not null default timezone('utc', now()),
    data_aprovacao timestamptz,
    data_publicacao timestamptz,
    atualizado_em timestamptz not null default timezone('utc', now())
);

create index if not exists mkt_campaigns_status_idx
    on public.mkt_campaigns (status, atualizado_em desc);

create table if not exists public.mkt_campaign_commands (
    id uuid primary key default gen_random_uuid(),
    campaign_id text not null references public.mkt_campaigns(campaign_id) on delete cascade,
    action text not null check (action in ('PUBLISH', 'RETRY', 'REJECT')),
    status text not null default 'PENDING' check (
        status in ('PENDING', 'CLAIMED', 'SUCCEEDED', 'FAILED', 'CANCELLED')
    ),
    requested_by uuid not null references auth.users(id),
    payload jsonb not null default '{}'::jsonb,
    result jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default timezone('utc', now()),
    claimed_at timestamptz,
    completed_at timestamptz
);

create unique index if not exists mkt_campaign_commands_pending_publish_idx
    on public.mkt_campaign_commands (campaign_id, action)
    where status in ('PENDING', 'CLAIMED') and action = 'PUBLISH';

alter table public.mkt_campaigns enable row level security;
alter table public.mkt_campaign_commands enable row level security;

drop policy if exists mkt_campaigns_admin_select on public.mkt_campaigns;
create policy mkt_campaigns_admin_select
    on public.mkt_campaigns for select to authenticated
    using (
        exists (
            select 1 from public.profiles p
            where p.id = auth.uid()
              and p.status = 'ACTIVE'
              and p.role = 'ADMIN'
        )
    );

drop policy if exists mkt_campaign_commands_admin_select on public.mkt_campaign_commands;
create policy mkt_campaign_commands_admin_select
    on public.mkt_campaign_commands for select to authenticated
    using (
        exists (
            select 1 from public.profiles p
            where p.id = auth.uid()
              and p.status = 'ACTIVE'
              and p.role = 'ADMIN'
        )
    );

drop policy if exists mkt_campaign_commands_admin_insert on public.mkt_campaign_commands;
create policy mkt_campaign_commands_admin_insert
    on public.mkt_campaign_commands for insert to authenticated
    with check (
        requested_by = auth.uid()
        and exists (
            select 1 from public.profiles p
            where p.id = auth.uid()
              and p.status = 'ACTIVE'
              and p.role = 'ADMIN'
        )
    );

-- Alteração de comandos e resultados fica restrita ao service_role do Linux.
drop policy if exists mkt_campaign_commands_admin_update on public.mkt_campaign_commands;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
    'mkt-campaign-assets',
    'mkt-campaign-assets',
    false,
    1073741824,
    array['video/mp4', 'image/jpeg', 'image/png']
)
on conflict (id) do update set
    public = excluded.public,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists mkt_campaign_assets_admin_select on storage.objects;
create policy mkt_campaign_assets_admin_select
    on storage.objects for select to authenticated
    using (
        bucket_id = 'mkt-campaign-assets'
        and exists (
            select 1 from public.profiles p
            where p.id = auth.uid()
              and p.status = 'ACTIVE'
              and p.role = 'ADMIN'
        )
    );

-- Upload e substituição de assets ficam restritos ao service_role do Linux.
drop policy if exists mkt_campaign_assets_admin_insert on storage.objects;
drop policy if exists mkt_campaign_assets_admin_update on storage.objects;
