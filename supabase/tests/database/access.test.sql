begin;
create extension if not exists pgtap with schema extensions;
select plan(22);

insert into auth.users(id, email) values
 ('00000000-0000-0000-0000-000000000001', 'alice@example.test'),
 ('00000000-0000-0000-0000-000000000002', 'bob@example.test');
insert into auth.sessions(id, user_id, created_at, updated_at) values
 ('10000000-0000-0000-0000-000000000001','00000000-0000-0000-0000-000000000001', now(), now()),
 ('10000000-0000-0000-0000-000000000002','00000000-0000-0000-0000-000000000002', now(), now());
insert into public.patients(id, user_id, name) values
 ('20000000-0000-0000-0000-000000000001','00000000-0000-0000-0000-000000000001','Synthetic A'),
 ('20000000-0000-0000-0000-000000000002','00000000-0000-0000-0000-000000000002','Synthetic B');
insert into storage.objects(bucket_id, name) values
 ('wound-images', '00000000-0000-0000-0000-000000000001/a.png'),
 ('wound-images', '00000000-0000-0000-0000-000000000002/b.png');

select is((select public from storage.buckets where id = 'wound-images'), false, 'Clinical images are private');
select is((select public from storage.buckets where id = 'analysis-images'), false, 'Analysis images are private');
select is((select file_size_limit from storage.buckets where id = 'wound-images'), 10485760::bigint, 'Upload size limited');
select ok(not has_table_privilege('anon', 'public.patients', 'SELECT'), 'Guests cannot read patients');
select ok(not has_function_privilege('anon', 'public.current_session_is_active()', 'EXECUTE'), 'Guests cannot inspect sessions');

set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"00000000-0000-0000-0000-000000000001","role":"authenticated","session_id":"10000000-0000-0000-0000-000000000001"}', true);
select ok(public.current_session_is_active(), 'Active session accepted');
select is((select count(*) from public.patients), 1::bigint, 'Only own patient visible');
select is((select count(*) from public.patients where id = '20000000-0000-0000-0000-000000000002'), 0::bigint, 'Known foreign ID hidden');
select throws_ok($$insert into public.patients(user_id,name) values ('00000000-0000-0000-0000-000000000002','Denied')$$, '42501', null, 'Cannot create a patient for another user');
select throws_ok($$update public.patients set user_id='00000000-0000-0000-0000-000000000002' where id='20000000-0000-0000-0000-000000000001'$$, '42501', null, 'Cannot transfer ownership');
select throws_ok($$insert into public.evaluations(user_id,patient_id,date) values ('00000000-0000-0000-0000-000000000001','20000000-0000-0000-0000-000000000002','2026-09-17')$$, '23503', null, 'Cannot link evaluation to foreign patient');
select lives_ok($$insert into public.evaluations(user_id,patient_id,date) values ('00000000-0000-0000-0000-000000000001','20000000-0000-0000-0000-000000000001','2026-09-17')$$, 'Own evaluation allowed');
select is((select count(*) from storage.objects where bucket_id='wound-images'), 1::bigint, 'Only own image visible');
select throws_ok($$insert into storage.objects(bucket_id,name) values ('wound-images','00000000-0000-0000-0000-000000000002/denied.png')$$, '42501', null, 'Cannot write foreign image');
select lives_ok($$select public.append_chat_turn('conversation-a','Synthetic question','Synthetic answer')$$, 'Chat turn saved atomically');
select is((select message_count from public.ai_conversations where id='conversation-a'), 2, 'Both messages counted');
select is((select count(*) from public.ai_messages), 2::bigint, 'Both messages present');

select set_config('request.jwt.claims', '{"sub":"00000000-0000-0000-0000-000000000002","role":"authenticated","session_id":"10000000-0000-0000-0000-000000000002"}', true);
select is((select count(*) from public.ai_messages), 0::bigint, 'Other user cannot read chat');
select throws_ok($$select public.append_chat_turn('conversation-a','Denied','Denied')$$, '42501', null, 'Cannot overwrite foreign conversation');

reset role;
delete from auth.sessions where id='10000000-0000-0000-0000-000000000002';
set local role authenticated;
select ok(not public.current_session_is_active(), 'Revoked session rejected');
select is((select count(*) from public.patients), 0::bigint, 'Revoked session cannot read data');
select is((select count(*) from storage.objects where bucket_id='wound-images'), 0::bigint, 'Revoked session cannot read images');
select * from finish();
rollback;
