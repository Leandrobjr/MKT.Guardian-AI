-- Fila única para solicitações de criação vindas do Desktop ou Telegram.

create table if not exists public.mkt_campaign_creation_requests (
    id uuid primary key default gen_random_uuid(),
    status text not null default 'PENDING' check (
        status in ('PENDING', 'CLAIMED', 'SUCCEEDED', 'FAILED', 'CANCELLED')
    ),
    source text not null default 'DESKTOP' check (
        source in ('DESKTOP', 'TELEGRAM')
    ),
    requested_by uuid references auth.users(id),
    requester_label text not null default '',
    config jsonb not null default '{}'::jsonb,
    result jsonb not null default '{}'::jsonb,
    error_message text not null default '',
    created_at timestamptz not null default timezone('utc', now()),
    claimed_at timestamptz,
    completed_at timestamptz
);

create index if not exists mkt_campaign_creation_requests_status_idx
    on public.mkt_campaign_creation_requests (status, created_at);
create index if not exists mkt_campaign_creation_requests_requested_by_idx
    on public.mkt_campaign_creation_requests (requested_by);

alter table public.mkt_campaign_creation_requests enable row level security;

drop policy if exists mkt_campaign_creation_requests_admin_select
    on public.mkt_campaign_creation_requests;
create policy mkt_campaign_creation_requests_admin_select
    on public.mkt_campaign_creation_requests for select to authenticated
    using (
        requested_by = (select auth.uid())
        or exists (
            select 1 from public.profiles p
            where p.id = (select auth.uid())
              and p.status = 'ACTIVE'
              and p.role = 'ADMIN'
        )
    );

drop policy if exists mkt_campaign_creation_requests_admin_insert
    on public.mkt_campaign_creation_requests;
create policy mkt_campaign_creation_requests_admin_insert
    on public.mkt_campaign_creation_requests for insert to authenticated
    with check (
        requested_by = (select auth.uid())
        and exists (
            select 1 from public.profiles p
            where p.id = (select auth.uid())
              and p.status = 'ACTIVE'
              and p.role = 'ADMIN'
        )
    );

-- Alterações de estado e resultados ficam restritas ao worker service_role.
