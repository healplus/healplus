-- Índices das chaves estrangeiras usados em consultas e exclusões em cascata.
-- A migração é aditiva e pode ser reaplicada com segurança.

create index if not exists evaluations_patient_id_idx
  on public.evaluations(patient_id);

create index if not exists appointments_patient_id_idx
  on public.appointments(patient_id);
