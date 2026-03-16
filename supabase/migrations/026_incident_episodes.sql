alter table public.incidents
  add column if not exists current_episode integer not null default 1,
  add column if not exists episode_count integer not null default 1,
  add column if not exists episode_history jsonb not null default '[]'::jsonb;
