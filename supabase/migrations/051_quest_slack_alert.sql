-- 051_quest_slack_alert.sql
-- High-urgency quest alerting to Slack via database webhook trigger.
--
-- Runtime prerequisites:
-- 1. Provide the Slack incoming webhook URL as either:
--    - a database setting:  app.settings.slack_webhook_url
--    - or a Supabase Vault secret named: SLACK_WEBHOOK_URL
-- 2. Optionally provide the dashboard URL as either:
--    - a database setting:  app.settings.office_dashboard_url
--    - or a Supabase Vault secret named: OFFICE_DASHBOARD_URL
--
-- In hosted Supabase, wire these from the corresponding environment secrets.

create extension if not exists pg_net;
create extension if not exists vault;

create or replace function public.quest_slack_secret(secret_name text)
returns text
language plpgsql
security definer
set search_path = public, vault
as $$
declare
  secret_value text;
begin
  select decrypted_secret
    into secret_value
    from vault.decrypted_secrets
   where name = secret_name
   limit 1;

  return secret_value;
exception
  when undefined_table then
    return null;
end;
$$;

create or replace function public.humanize_identifier(value text)
returns text
language sql
immutable
as $$
  select initcap(replace(replace(coalesce(value, 'unknown'), '_', ' '), '-', ' '));
$$;

create or replace function public.notify_high_urgency_quest_to_slack()
returns trigger
language plpgsql
security definer
set search_path = public, net
as $$
declare
  webhook_url text;
  dashboard_url text;
  agent_name text;
  department_name text;
  payload jsonb;
begin
  webhook_url := coalesce(
    nullif(current_setting('app.settings.slack_webhook_url', true), ''),
    nullif(public.quest_slack_secret('SLACK_WEBHOOK_URL'), '')
  );

  if webhook_url is null then
    raise log 'high urgency quest slack alert skipped: SLACK_WEBHOOK_URL is not configured';
    return new;
  end if;

  dashboard_url := coalesce(
    nullif(current_setting('app.settings.office_dashboard_url', true), ''),
    nullif(public.quest_slack_secret('OFFICE_DASHBOARD_URL'), ''),
    'http://localhost:3000'
  );

  agent_name := public.humanize_identifier(new.agent_id);
  department_name := public.humanize_identifier(new.department);

  payload := jsonb_build_object(
    'text',
    format(
      'High urgency quest: %s | %s | %s | %s | %s',
      agent_name,
      department_name,
      upper(new.urgency),
      new.summary,
      dashboard_url
    ),
    'blocks',
    jsonb_build_array(
      jsonb_build_object(
        'type', 'header',
        'text', jsonb_build_object(
          'type', 'plain_text',
          'text', 'High Urgency Quest'
        )
      ),
      jsonb_build_object(
        'type', 'section',
        'fields', jsonb_build_array(
          jsonb_build_object(
            'type', 'mrkdwn',
            'text', format('*Agent*\n%s', agent_name)
          ),
          jsonb_build_object(
            'type', 'mrkdwn',
            'text', format('*Department*\n%s', department_name)
          ),
          jsonb_build_object(
            'type', 'mrkdwn',
            'text', format('*Urgency*\n%s', upper(new.urgency))
          )
        )
      ),
      jsonb_build_object(
        'type', 'section',
        'text', jsonb_build_object(
          'type', 'mrkdwn',
          'text', format('*Summary*\n%s', new.summary)
        )
      ),
      jsonb_build_object(
        'type', 'section',
        'text', jsonb_build_object(
          'type', 'mrkdwn',
          'text', format('<%s|Open dashboard>', dashboard_url)
        )
      )
    )
  );

  perform net.http_post(
    url := webhook_url,
    headers := jsonb_build_object('Content-Type', 'application/json'),
    body := payload
  );

  return new;
end;
$$;

drop trigger if exists quest_log_high_urgency_slack_alert on public.quest_log;

create trigger quest_log_high_urgency_slack_alert
after insert on public.quest_log
for each row
when (new.urgency = 'high')
execute function public.notify_high_urgency_quest_to_slack();
