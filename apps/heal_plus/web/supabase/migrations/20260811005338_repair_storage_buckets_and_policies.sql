-- Restaura privacidade, formatos e isolamento por pasta dos buckets do frontend.

begin;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values
  ('wound-images', 'wound-images', false, 10485760, array['image/jpeg', 'image/png', 'image/webp']),
  ('profile-photos', 'profile-photos', true, 10485760, array['image/jpeg', 'image/png', 'image/webp'])
on conflict (id) do update set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists "Allow anon select on wound-images" on storage.objects;
drop policy if exists "Allow anon uploads to wound-images" on storage.objects;
drop policy if exists wound_images_select_own on storage.objects;
drop policy if exists wound_images_insert_own on storage.objects;
drop policy if exists wound_images_update_own on storage.objects;
drop policy if exists wound_images_delete_own on storage.objects;

create policy wound_images_select_own on storage.objects
for select to authenticated
using (
  bucket_id = 'wound-images'
  and (storage.foldername(name))[1] = (select auth.uid())::text
);

create policy wound_images_insert_own on storage.objects
for insert to authenticated
with check (
  bucket_id = 'wound-images'
  and (storage.foldername(name))[1] = (select auth.uid())::text
);

create policy wound_images_update_own on storage.objects
for update to authenticated
using (
  bucket_id = 'wound-images'
  and (storage.foldername(name))[1] = (select auth.uid())::text
)
with check (
  bucket_id = 'wound-images'
  and (storage.foldername(name))[1] = (select auth.uid())::text
);

create policy wound_images_delete_own on storage.objects
for delete to authenticated
using (
  bucket_id = 'wound-images'
  and (storage.foldername(name))[1] = (select auth.uid())::text
);

drop policy if exists "Allow anon select on profile-photos" on storage.objects;
drop policy if exists "Allow anon uploads to profile-photos" on storage.objects;
drop policy if exists profile_photos_insert_own on storage.objects;
drop policy if exists profile_photos_update_own on storage.objects;
drop policy if exists profile_photos_delete_own on storage.objects;

create policy profile_photos_insert_own on storage.objects
for insert to authenticated
with check (
  bucket_id = 'profile-photos'
  and (storage.foldername(name))[1] = (select auth.uid())::text
);

create policy profile_photos_update_own on storage.objects
for update to authenticated
using (
  bucket_id = 'profile-photos'
  and (storage.foldername(name))[1] = (select auth.uid())::text
)
with check (
  bucket_id = 'profile-photos'
  and (storage.foldername(name))[1] = (select auth.uid())::text
);

create policy profile_photos_delete_own on storage.objects
for delete to authenticated
using (
  bucket_id = 'profile-photos'
  and (storage.foldername(name))[1] = (select auth.uid())::text
);

commit;
