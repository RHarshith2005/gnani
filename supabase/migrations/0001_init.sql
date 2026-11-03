-- NegoAI — Postgres/Supabase schema.
-- Mirrors api/db.py (SQLite local store) so the demo runs with or without keys.
-- Every number in the UI comes from these rows; vendor floors never land here.

create table if not exists communities (
  id text primary key,
  name text not null,
  households integer not null default 0,
  created_at timestamptz not null default now()
);

create table if not exists residents (
  id text primary key,
  community_id text not null references communities(id) on delete cascade,
  auth_user_id uuid,
  flat_number text,
  language text,
  role text not null default 'resident' check (role in ('resident', 'admin')),
  created_at timestamptz not null default now()
);

create table if not exists demand_requests (
  id text primary key,
  resident_id text references residents(id) on delete set null,
  community_id text not null references communities(id) on delete cascade,
  product text not null,
  qty integer not null check (qty > 0),
  frequency text not null default 'weekly',
  delivery_day text,
  language text,
  status text not null default 'confirmed' check (status in ('draft', 'confirmed', 'cancelled')),
  created_at timestamptz not null default now()
);

create table if not exists vendors (
  id text primary key,
  name text not null,
  persona text not null,
  product text not null,
  free_delivery_qty integer,
  delivery_days integer,
  delivery_charge numeric(10, 2) not null default 0,
  created_at timestamptz not null default now()
);

create table if not exists vendor_offers (
  id text primary key default gen_random_uuid()::text,
  negotiation_id text,
  vendor_id text not null references vendors(id) on delete cascade,
  product text not null,
  unit_price numeric(10, 2) not null,
  delivery_charge numeric(10, 2) not null default 0,
  min_qty integer,
  valid_days integer,
  source text not null default 'simulated',
  round integer not null default 0,
  eligible boolean not null default false,
  created_at timestamptz not null default now()
);

create table if not exists negotiations (
  id text primary key,
  community_id text not null references communities(id) on delete cascade,
  vendor_id text references vendors(id) on delete set null,
  product text not null,
  qty integer not null,
  state text not null default 'ASK_QUOTE',
  round integer not null default 0,
  max_rounds integer not null default 3,
  language text,
  first_quote numeric(10, 2),
  best_quote numeric(10, 2),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Append-only. Replay and the dashboard both read this table.
create table if not exists negotiation_events (
  id bigserial primary key,
  negotiation_id text not null references negotiations(id) on delete cascade,
  ts timestamptz not null default now(),
  actor text not null,
  type text not null,
  payload jsonb not null default '{}'::jsonb
);

create index if not exists idx_negotiation_events_neg
  on negotiation_events (negotiation_id, id);

create table if not exists approvals (
  id text primary key default gen_random_uuid()::text,
  negotiation_id text not null references negotiations(id) on delete cascade,
  offer_id text references vendor_offers(id) on delete set null,
  admin_id text,
  decision text not null check (decision in ('approved', 'rejected')),
  note text,
  created_at timestamptz not null default now()
);

-- Append-only guard: never update or delete an event.
create or replace function reject_event_mutation() returns trigger as $$
begin
  raise exception 'negotiation_events is append-only';
end;
$$ language plpgsql;

drop trigger if exists negotiation_events_no_update on negotiation_events;
create trigger negotiation_events_no_update
  before update or delete on negotiation_events
  for each row execute function reject_event_mutation();

-- ---------------------------------------------------------------------- RLS
alter table communities enable row level security;
alter table residents enable row level security;
alter table demand_requests enable row level security;
alter table vendors enable row level security;
alter table vendor_offers enable row level security;
alter table negotiations enable row level security;
alter table negotiation_events enable row level security;
alter table approvals enable row level security;

create or replace function is_admin(community text) returns boolean as $$
  select exists (
    select 1 from residents r
    where r.community_id = community
      and r.role = 'admin'
      and r.auth_user_id = auth.uid()
  );
$$ language sql stable security definer;

create policy "read community" on communities for select to authenticated using (true);
create policy "read vendors" on vendors for select to authenticated using (true);

create policy "residents read own rows" on residents
  for select to authenticated
  using (auth_user_id = auth.uid() or is_admin(community_id));

create policy "residents insert own demand" on demand_requests
  for insert to authenticated
  with check (exists (
    select 1 from residents r
    where r.id = resident_id and r.auth_user_id = auth.uid()
  ));

create policy "community reads confirmed demand" on demand_requests
  for select to authenticated
  using (status = 'confirmed');

create policy "residents read offers" on vendor_offers
  for select to authenticated using (true);

create policy "admins read negotiations" on negotiations
  for select to authenticated using (is_admin(community_id));

create policy "community reads events" on negotiation_events
  for select to authenticated using (true);

create policy "admins insert approvals" on approvals
  for insert to authenticated
  with check (is_admin((select community_id from negotiations n where n.id = negotiation_id)));

create policy "community reads approvals" on approvals
  for select to authenticated using (true);

-- ------------------------------------------------------------------- realtime
alter publication supabase_realtime add table negotiation_events;
alter publication supabase_realtime add table vendor_offers;
