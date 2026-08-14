set statement_timeout = '30s';

do $$
begin
  if (select count(*) from public.users where uid = '00000000-0000-4000-8000-000000000102') <> 1 then
    raise exception 'synthetic professional was not restored';
  end if;

  if (select count(*) from public.patients where id = '10000000-0000-4000-8000-000000000102') <> 1 then
    raise exception 'synthetic patient was not restored';
  end if;

  if (
    select count(*)
    from public.evaluations
    where id = '20000000-0000-4000-8000-000000000102'
      and images -> 0 ->> 'path' = '00000000-0000-4000-8000-000000000102/10000000-0000-4000-8000-000000000102/20000000-0000-4000-8000-000000000102/restore-drill.webp'
  ) <> 1 then
    raise exception 'synthetic evaluation or image reference was not restored';
  end if;

  if (select count(*) from public.appointments where id = '30000000-0000-4000-8000-000000000102') <> 1 then
    raise exception 'synthetic appointment was not restored';
  end if;

  if (
    select count(*)
    from storage.objects
    where (bucket_id, name) in (
      (
        'wound-images',
        '00000000-0000-4000-8000-000000000102/10000000-0000-4000-8000-000000000102/20000000-0000-4000-8000-000000000102/restore-drill.webp'
      ),
      ('profile-photos', '00000000-0000-4000-8000-000000000102/restore-drill.webp')
    )
  ) <> 2 then
    raise exception 'synthetic storage metadata was not restored';
  end if;
end;
$$;
