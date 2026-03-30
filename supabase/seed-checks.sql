-- Seed verification checks for realistic app data in supabase/seed.sql.
-- Run after migrations + seed apply.

-- 1) Expected realistic dataset size
select
  count(*) as tenant_alpha_demo_call_count
from public.call_records
where tenant_id = '00000000-0000-0000-0000-000000000001'
  and call_id like 'demo-call-%';

-- 2) No duplicate call_ids in demo namespace
select
  call_id,
  count(*) as duplicate_count
from public.call_records
where tenant_id = '00000000-0000-0000-0000-000000000001'
  and call_id like 'demo-call-%'
group by call_id
having count(*) > 1;

-- 3) Bucket representation sanity check
with demo as (
  select *
  from public.call_records
  where tenant_id = '00000000-0000-0000-0000-000000000001'
    and call_id like 'demo-call-%'
)
select
  count(*) filter (where callback_outcome in ('reached_customer','scheduled','resolved_elsewhere')) as terminal_callback_outcomes,
  count(*) filter (where end_call_reason in ('wrong_number','out_of_area')) as wrong_number_or_out_of_area,
  count(*) filter (where coalesce((extracted_fields->>'appointment_booked')::boolean, false) = true) as appointment_booked,
  count(*) filter (where end_call_reason in ('callback_later','booking_failed')) as callback_later_or_booking_failed
from demo;

-- 4) callback window valid vs expired examples
with demo as (
  select
    call_id,
    extracted_fields->>'callback_window_end' as callback_window_end
  from public.call_records
  where tenant_id = '00000000-0000-0000-0000-000000000001'
    and call_id like 'demo-call-%'
)
select
  count(*) filter (where callback_window_end is not null and (callback_window_end)::timestamptz > now()) as windows_valid,
  count(*) filter (where callback_window_end is not null and (callback_window_end)::timestamptz <= now()) as windows_expired
from demo;

-- 5) Follow-up calls with touch history
select
  cr.call_id,
  count(ct.id) as touch_count
from public.call_records cr
left join public.callback_touches ct
  on ct.tenant_id = cr.tenant_id
 and ct.call_id = cr.call_id
where cr.tenant_id = '00000000-0000-0000-0000-000000000001'
  and cr.call_id in ('demo-call-009','demo-call-010','demo-call-011','demo-call-012','demo-call-013','demo-call-014')
group by cr.call_id
order by cr.call_id;
