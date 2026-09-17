-- Repara somente autorização e privilégios; não altera registros clínicos.
-- Casts textuais mantêm compatibilidade com ambientes legados que usavam IDs text.

begin;

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

drop policy if exists users_own_profile on public.users;
create policy users_own_profile on public.users
for all to authenticated
using ((select auth.uid())::text = uid::text)
with check ((select auth.uid())::text = uid::text);

drop policy if exists patients_owned_by_professional on public.patients;
create policy patients_owned_by_professional on public.patients
for all to authenticated
using ((select auth.uid())::text = user_id::text)
with check ((select auth.uid())::text = user_id::text);

drop policy if exists evaluations_owned_by_professional on public.evaluations;
create policy evaluations_owned_by_professional on public.evaluations
for all to authenticated
using (
  (select auth.uid())::text = user_id::text
  and exists (
    select 1
    from public.patients patient
    where patient.id::text = evaluations.patient_id::text
      and patient.user_id::text = (select auth.uid())::text
  )
)
with check (
  (select auth.uid())::text = user_id::text
  and exists (
    select 1
    from public.patients patient
    where patient.id::text = evaluations.patient_id::text
      and patient.user_id::text = (select auth.uid())::text
  )
);

drop policy if exists appointments_owned_by_professional on public.appointments;
create policy appointments_owned_by_professional on public.appointments
for all to authenticated
using (
  (select auth.uid())::text = user_id::text
  and exists (
    select 1
    from public.patients patient
    where patient.id::text = appointments.patient_id::text
      and patient.user_id::text = (select auth.uid())::text
  )
)
with check (
  (select auth.uid())::text = user_id::text
  and exists (
    select 1
    from public.patients patient
    where patient.id::text = appointments.patient_id::text
      and patient.user_id::text = (select auth.uid())::text
  )
);

commit;
