set statement_timeout = '30s';

begin;

insert into auth.users (
  id,
  aud,
  role,
  email,
  email_confirmed_at,
  raw_app_meta_data,
  raw_user_meta_data,
  created_at,
  updated_at,
  is_sso_user,
  is_anonymous
)
values (
  '00000000-0000-4000-8000-000000000102',
  'authenticated',
  'authenticated',
  'restore-drill@example.invalid',
  timezone('utc', now()),
  '{"provider":"email","providers":["email"]}'::jsonb,
  '{}'::jsonb,
  timezone('utc', now()),
  timezone('utc', now()),
  false,
  false
);

insert into public.users (
  uid,
  display_name,
  email,
  onboarding_completed
)
values (
  '00000000-0000-4000-8000-000000000102',
  'Profissional Sintético de Restauração',
  'restore-drill@example.invalid',
  true
);

insert into public.patients (
  id,
  user_id,
  name,
  notes
)
values (
  '10000000-0000-4000-8000-000000000102',
  '00000000-0000-4000-8000-000000000102',
  'Paciente Sintético de Restauração',
  'Registro gerado exclusivamente pelo exercício automatizado.'
);

insert into public.evaluations (
  id,
  patient_id,
  user_id,
  patient_name,
  date,
  wound_location,
  pain_level,
  images,
  notes
)
values (
  '20000000-0000-4000-8000-000000000102',
  '10000000-0000-4000-8000-000000000102',
  '00000000-0000-4000-8000-000000000102',
  'Paciente Sintético de Restauração',
  '2026-08-10',
  'Área sintética',
  0,
  '[{"id":"restore-drill-image","path":"00000000-0000-4000-8000-000000000102/10000000-0000-4000-8000-000000000102/20000000-0000-4000-8000-000000000102/restore-drill.webp","name":"restore-drill.webp","type":"image/webp","size":42,"downloadURL":""}]'::jsonb,
  'Sem conteúdo clínico real.'
);

insert into public.appointments (
  id,
  user_id,
  patient_id,
  patient_name,
  date,
  time,
  type,
  status,
  notes
)
values (
  '30000000-0000-4000-8000-000000000102',
  '00000000-0000-4000-8000-000000000102',
  '10000000-0000-4000-8000-000000000102',
  'Paciente Sintético de Restauração',
  '2026-08-11',
  '09:00',
  'Retorno sintético',
  'Pendente',
  'Registro gerado exclusivamente pelo exercício automatizado.'
);

commit;
