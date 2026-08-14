-- Schema persistido pelo frontend Heal+ integrado ao repositório REDI-SUS.
-- Os serviços FHIR/RNDS e o backend clínico permanecem fora desta migração.

create extension if not exists pgcrypto;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
  new.updated_at = timezone('utc', now());
  return new;
end;
$$;

create table if not exists public.users (
  uid uuid primary key references auth.users(id) on delete cascade,
  display_name text not null default 'Profissional',
  email text not null default '',
  photo_url text,
  provider_ids text[] not null default '{}',
  role text not null default 'professional',
  settings jsonb not null default '{}',
  professional_area text not null default '',
  clinic_name text not null default '',
  phone text not null default '',
  onboarding_completed boolean not null default false,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.patients (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  name text not null check (char_length(name) between 2 and 120),
  phone text not null default '',
  email text not null default '',
  birth_date text not null default '',
  notes text not null default '',
  archived boolean not null default false,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.evaluations (
  id uuid primary key default gen_random_uuid(),
  patient_id uuid not null references public.patients(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  patient_name text not null default '',
  date text not null,
  wound_location text not null default '',
  wound_etiology text not null default '',
  pain_level integer not null default 0 check (pain_level between 0 and 10),
  exudate_amount text not null default '',
  exudate_type text not null default '',
  border_characteristics text not null default '',
  periwound_skin text not null default '',
  infection_signs text[] not null default '{}',
  timers jsonb not null default '{}',
  comorbidities text[] not null default '{}',
  medications text[] not null default '{}',
  notes text not null default '',
  images jsonb not null default '[]',
  signature text not null default '',
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.appointments (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  patient_id uuid not null references public.patients(id) on delete cascade,
  patient_name text not null,
  date text not null,
  time text not null,
  type text not null,
  status text not null default 'Pendente'
    check (status in ('Confirmado', 'Pendente', 'Cancelado', 'Realizado')),
  notes text not null default '',
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create index if not exists patients_user_id_idx on public.patients(user_id);
create index if not exists evaluations_user_patient_date_idx on public.evaluations(user_id, patient_id, date desc);
create index if not exists appointments_user_date_idx on public.appointments(user_id, date, time);

drop trigger if exists users_set_updated_at on public.users;
create trigger users_set_updated_at before update on public.users
for each row execute function public.set_updated_at();
drop trigger if exists patients_set_updated_at on public.patients;
create trigger patients_set_updated_at before update on public.patients
for each row execute function public.set_updated_at();
drop trigger if exists evaluations_set_updated_at on public.evaluations;
create trigger evaluations_set_updated_at before update on public.evaluations
for each row execute function public.set_updated_at();
drop trigger if exists appointments_set_updated_at on public.appointments;
create trigger appointments_set_updated_at before update on public.appointments
for each row execute function public.set_updated_at();

alter table public.users enable row level security;
alter table public.patients enable row level security;
alter table public.evaluations enable row level security;
alter table public.appointments enable row level security;

revoke all on table public.users, public.patients, public.evaluations, public.appointments from anon;
grant usage on schema public to authenticated;
grant select, insert, update, delete on table
  public.users,
  public.patients,
  public.evaluations,
  public.appointments
to authenticated;
revoke execute on function public.set_updated_at() from public, anon;
grant execute on function public.set_updated_at() to authenticated;

drop policy if exists users_own_profile on public.users;
create policy users_own_profile on public.users
for all to authenticated
using ((select auth.uid()) = uid)
with check ((select auth.uid()) = uid);

drop policy if exists patients_owned_by_professional on public.patients;
create policy patients_owned_by_professional on public.patients
for all to authenticated
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);

drop policy if exists evaluations_owned_by_professional on public.evaluations;
create policy evaluations_owned_by_professional on public.evaluations
for all to authenticated
using (
  (select auth.uid()) = user_id
  and exists (
    select 1 from public.patients patient
    where patient.id = evaluations.patient_id
      and patient.user_id = (select auth.uid())
  )
)
with check (
  (select auth.uid()) = user_id
  and exists (
    select 1 from public.patients patient
    where patient.id = evaluations.patient_id
      and patient.user_id = (select auth.uid())
  )
);

drop policy if exists appointments_owned_by_professional on public.appointments;
create policy appointments_owned_by_professional on public.appointments
for all to authenticated
using (
  (select auth.uid()) = user_id
  and exists (
    select 1 from public.patients patient
    where patient.id = appointments.patient_id
      and patient.user_id = (select auth.uid())
  )
)
with check (
  (select auth.uid()) = user_id
  and exists (
    select 1 from public.patients patient
    where patient.id = appointments.patient_id
      and patient.user_id = (select auth.uid())
  )
);

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values
  ('wound-images', 'wound-images', false, 10485760, array['image/jpeg', 'image/png', 'image/webp']),
  ('profile-photos', 'profile-photos', true, 10485760, array['image/jpeg', 'image/png', 'image/webp'])
on conflict (id) do update set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists wound_images_select_own on storage.objects;
create policy wound_images_select_own on storage.objects
for select to authenticated
using (bucket_id = 'wound-images' and (storage.foldername(name))[1] = (select auth.uid())::text);
drop policy if exists wound_images_insert_own on storage.objects;
create policy wound_images_insert_own on storage.objects
for insert to authenticated
with check (bucket_id = 'wound-images' and (storage.foldername(name))[1] = (select auth.uid())::text);
drop policy if exists wound_images_update_own on storage.objects;
create policy wound_images_update_own on storage.objects
for update to authenticated
using (bucket_id = 'wound-images' and (storage.foldername(name))[1] = (select auth.uid())::text)
with check (bucket_id = 'wound-images' and (storage.foldername(name))[1] = (select auth.uid())::text);
drop policy if exists wound_images_delete_own on storage.objects;
create policy wound_images_delete_own on storage.objects
for delete to authenticated
using (bucket_id = 'wound-images' and (storage.foldername(name))[1] = (select auth.uid())::text);

drop policy if exists profile_photos_insert_own on storage.objects;
create policy profile_photos_insert_own on storage.objects
for insert to authenticated
with check (bucket_id = 'profile-photos' and (storage.foldername(name))[1] = (select auth.uid())::text);
drop policy if exists profile_photos_update_own on storage.objects;
create policy profile_photos_update_own on storage.objects
for update to authenticated
using (bucket_id = 'profile-photos' and (storage.foldername(name))[1] = (select auth.uid())::text)
with check (bucket_id = 'profile-photos' and (storage.foldername(name))[1] = (select auth.uid())::text);
drop policy if exists profile_photos_delete_own on storage.objects;
create policy profile_photos_delete_own on storage.objects
for delete to authenticated
using (bucket_id = 'profile-photos' and (storage.foldername(name))[1] = (select auth.uid())::text);

do $$
begin
  if not exists (
    select 1 from pg_publication_tables
    where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = 'patients'
  ) then
    alter publication supabase_realtime add table public.patients;
  end if;
  if not exists (
    select 1 from pg_publication_tables
    where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = 'evaluations'
  ) then
    alter publication supabase_realtime add table public.evaluations;
  end if;
  if not exists (
    select 1 from pg_publication_tables
    where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = 'appointments'
  ) then
    alter publication supabase_realtime add table public.appointments;
  end if;
end;
$$;
