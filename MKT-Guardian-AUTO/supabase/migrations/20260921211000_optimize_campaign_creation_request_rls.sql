-- Otimiza a política e a consulta por solicitante da fila de criação.

create index if not exists mkt_campaign_creation_requests_requested_by_idx
    on public.mkt_campaign_creation_requests (requested_by);

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
