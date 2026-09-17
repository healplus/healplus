-- Baseline matching the web services and the authenticated Python integration.
-- Existing installations must reconcile their schema before applying this baseline.
create schema if not exists private;
revoke all on schema private from public;
grant usage on schema private to authenticated;

-- The only elevated lookup is in a non-exposed schema. It cannot inspect another
-- user's session and returns no session identifiers or credentials.
create or replace function private.current_session_is_active()
returns boolean language sql stable security definer set search_path = '' as $$
  select exists (
    select 1 from auth.sessions
    where id::text = (select auth.jwt()->>'session_id')
      and user_id = (select auth.uid())
      and (not_after is null or not_after > now())
  );
$$;
revoke all on function private.current_session_is_active() from public, anon;
grant execute on function private.current_session_is_active() to authenticated;
create or replace function public.current_session_is_active()
returns boolean language sql stable security invoker set search_path = '' as $$
  select private.current_session_is_active();
$$;
revoke all on function public.current_session_is_active() from public, anon;
grant execute on function public.current_session_is_active() to authenticated;

create table if not exists public.users (
  uid uuid primary key references auth.users(id) on delete cascade,
  display_name text not null default '', email text not null default '', photo_url text,
  provider_ids jsonb not null default '[]', role text not null default 'professional' check (role = 'professional'),
  settings jsonb not null default '{}', professional_area text not null default '',
  clinic_name text not null default '', phone text not null default '', onboarding_completed boolean not null default false,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create table if not exists public.patients (
  id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
  name text not null, phone text not null default '', email text not null default '', birth_date text not null default '',
  notes text not null default '', archived boolean not null default false,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  unique (id, user_id)
);
create table if not exists public.evaluations (
  id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
  patient_id uuid not null, patient_name text not null default '', date text not null,
  wound_location text not null default '', wound_etiology text not null default '', pain_level integer not null default 0,
  exudate_amount text not null default '', exudate_type text not null default '', border_characteristics text not null default '',
  periwound_skin text not null default '', infection_signs jsonb not null default '[]', timers jsonb not null default '{}',
  comorbidities jsonb not null default '[]', medications jsonb not null default '[]', notes text not null default '',
  images jsonb not null default '[]', signature text not null default '',
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  unique (id, patient_id, user_id), foreign key (patient_id, user_id) references public.patients(id, user_id) on delete cascade,
  check (pain_level between 0 and 10)
);
create table if not exists public.appointments (
  id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
  patient_id uuid not null, patient_name text not null default '', date text not null, time text not null,
  type text not null, status text not null check (status in ('Confirmado', 'Pendente', 'Cancelado', 'Realizado')),
  notes text not null default '', created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  foreign key (patient_id, user_id) references public.patients(id, user_id) on delete cascade
);
create table if not exists public.analysis_results (
  id text primary key, user_id uuid not null references auth.users(id) on delete cascade,
  patient_id uuid, assessment_id uuid, result_data jsonb not null,
  created_at timestamptz not null default now(),
  foreign key (patient_id, user_id) references public.patients(id, user_id) on delete cascade,
  foreign key (assessment_id, patient_id, user_id) references public.evaluations(id, patient_id, user_id) on delete cascade,
  check (assessment_id is null or patient_id is not null)
);
-- These analyses may refer to patients in the separate clinical API repository.
create table if not exists public.analyses (
  id text primary key, owner_uid uuid not null references auth.users(id) on delete cascade,
  patient_id text, image_path text not null, result_data jsonb not null,
  created_at timestamptz not null default now()
);
create table if not exists public.ai_conversations (
  id text primary key, owner_uid uuid not null references auth.users(id) on delete cascade,
  last_message text not null default '', message_count integer not null default 0,
  updated_at timestamptz not null default now(), unique (id, owner_uid)
);
create table if not exists public.ai_messages (
  id bigint generated always as identity primary key, conversation_id text not null,
  owner_uid uuid not null references auth.users(id) on delete cascade,
  role text not null check (role in ('user', 'assistant')), content text not null,
  timestamp timestamptz not null default now(),
  foreign key (conversation_id, owner_uid) references public.ai_conversations(id, owner_uid) on delete cascade
);

create index if not exists patients_owner_created on public.patients(user_id, created_at desc);
create index if not exists evaluations_patient_owner_date on public.evaluations(patient_id, user_id, date desc);
create index if not exists appointments_owner_date on public.appointments(user_id, date);
create index if not exists appointments_patient_owner on public.appointments(patient_id, user_id);
create index if not exists analysis_results_owner on public.analysis_results(user_id);
create index if not exists analysis_results_assessment on public.analysis_results(assessment_id, patient_id, user_id);
create index if not exists analyses_owner on public.analyses(owner_uid, created_at desc);
create index if not exists conversations_owner_updated on public.ai_conversations(owner_uid, updated_at desc);
create index if not exists messages_conversation on public.ai_messages(conversation_id, owner_uid, timestamp, id);

-- Restrictive policies also constrain pre-existing permissive policies on upgrades.
do $$
declare item record;
begin
  for item in select * from (values
    ('users', 'uid'), ('patients', 'user_id'), ('evaluations', 'user_id'), ('appointments', 'user_id'),
    ('analysis_results', 'user_id'), ('analyses', 'owner_uid'), ('ai_conversations', 'owner_uid'), ('ai_messages', 'owner_uid')
  ) as tables(name, owner_column) loop
    execute format('alter table public.%I enable row level security', item.name);
    execute format('revoke all on public.%I from anon', item.name);
    execute format('grant select, insert, update, delete on public.%I to authenticated', item.name);
    execute format('create policy own_records on public.%I for all to authenticated using ((select auth.uid()) = %I) with check ((select auth.uid()) = %I)', item.name, item.owner_column, item.owner_column);
    execute format('create policy session_owner_boundary on public.%I as restrictive for all to authenticated using ((select auth.uid()) = %I and (select private.current_session_is_active())) with check ((select auth.uid()) = %I and (select private.current_session_is_active()))', item.name, item.owner_column, item.owner_column);
  end loop;
end $$;
grant usage, select on sequence public.ai_messages_id_seq to authenticated;

-- One transaction prevents partial turns and serializes concurrent appends.
create or replace function public.append_chat_turn(conversation text, user_content text, assistant_content text)
returns void language plpgsql security invoker set search_path = '' as $$
begin
  if auth.uid() is null or length(conversation) not between 1 and 200
     or length(user_content) not between 1 and 20000 or length(assistant_content) not between 1 and 100000 then
    raise exception 'Invalid conversation input';
  end if;
  insert into public.ai_conversations(id, owner_uid, last_message, message_count)
    values (conversation, auth.uid(), left(user_content, 100), 2)
    on conflict (id) do update set last_message = excluded.last_message,
      message_count = public.ai_conversations.message_count + 2, updated_at = now();
  insert into public.ai_messages(conversation_id, owner_uid, role, content)
    values (conversation, auth.uid(), 'user', user_content), (conversation, auth.uid(), 'assistant', assistant_content);
end $$;
revoke all on function public.append_chat_turn(text, text, text) from public, anon;
grant execute on function public.append_chat_turn(text, text, text) to authenticated;

insert into storage.buckets(id, name, public, file_size_limit, allowed_mime_types)
values ('wound-images', 'wound-images', false, 10485760, array['image/jpeg','image/png','image/webp']),
       ('analysis-images', 'analysis-images', false, 10485760, array['image/jpeg','image/png','image/webp']),
       ('profile-photos', 'profile-photos', true, 10485760, array['image/jpeg','image/png','image/webp'])
on conflict (id) do update set public = excluded.public, file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;
create policy owned_images on storage.objects for all to authenticated
using (bucket_id in ('wound-images','analysis-images','profile-photos') and (storage.foldername(name))[1] = (select auth.uid())::text)
with check (bucket_id in ('wound-images','analysis-images','profile-photos') and (storage.foldername(name))[1] = (select auth.uid())::text);
create policy image_session_boundary on storage.objects as restrictive for all to authenticated
using (bucket_id not in ('wound-images','analysis-images','profile-photos') or ((storage.foldername(name))[1] = (select auth.uid())::text and (select private.current_session_is_active())))
with check (bucket_id not in ('wound-images','analysis-images','profile-photos') or ((storage.foldername(name))[1] = (select auth.uid())::text and (select private.current_session_is_active())));
create policy no_anonymous_clinical_images on storage.objects as restrictive for all to anon
using (bucket_id not in ('wound-images','analysis-images'))
with check (bucket_id not in ('wound-images','analysis-images'));

do $$
declare table_name text;
begin
  foreach table_name in array array['users','patients','evaluations','appointments'] loop
    if not exists (select 1 from pg_publication_tables where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = table_name) then
      execute format('alter publication supabase_realtime add table public.%I', table_name);
    end if;
  end loop;
end $$;
