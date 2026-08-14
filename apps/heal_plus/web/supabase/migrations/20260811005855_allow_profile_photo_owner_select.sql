-- Upsert de foto de perfil requer SELECT, além de INSERT e UPDATE.

begin;

drop policy if exists profile_photos_select_own on storage.objects;

create policy profile_photos_select_own on storage.objects
for select to authenticated
using (
  bucket_id = 'profile-photos'
  and (storage.foldername(name))[1] = (select auth.uid())::text
);

commit;
