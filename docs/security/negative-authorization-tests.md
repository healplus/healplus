# Testes de autorização

Os testes usam somente dados sintéticos. Tokens e conteúdo clínico não devem aparecer nos logs.

| Camada | Contrato | Verificação |
| --- | --- | --- |
| API clínica | Pacientes e recursos derivados respeitam proprietário, papel e escopo | `tests/test_negative_authorization.py` |
| Supabase Auth | Token validado no Auth; sessão ativa; permissões apenas em `app_metadata` | `tests/test_supabase_client.py` |
| PostgreSQL | RLS por titular e sessão; vínculos entre registros do mesmo usuário | `supabase/tests/database/access.test.sql` |
| Storage | Imagens clínicas privadas no prefixo do titular; MIME e limite de 10 MiB no bucket | `supabase/tests/database/access.test.sql` |

A API responde `404` tanto para um recurso inexistente como para um identificador fora do escopo. Falhas de infraestrutura retornam erro genérico, sem expor respostas internas do provedor.

Execute `python -m pytest tests/test_api_security.py tests/test_negative_authorization.py tests/test_supabase_client.py -q` e, com o ambiente Supabase local iniciado, `npx supabase test db`.

A configuração e as limitações de implantação estão em [Supabase](../operations/supabase.md).
