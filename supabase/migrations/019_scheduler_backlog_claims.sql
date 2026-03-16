alter table public.scheduler_backlog
  drop constraint if exists scheduler_backlog_status_check;

alter table public.scheduler_backlog
  add constraint scheduler_backlog_status_check
  check (status in ('pending', 'claimed', 'completed', 'expired'));

alter table public.scheduler_backlog
  add column if not exists claimed_by text,
  add column if not exists claimed_at timestamptz,
  add column if not exists claim_expires_at timestamptz;

create index if not exists scheduler_backlog_claim_expires_idx
  on public.scheduler_backlog (status, claim_expires_at);
