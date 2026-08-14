# Operação da camada web

Esta documentação cobre o frontend React e seu uso de Supabase dentro do
repositório integrado. Backend, Firebase, Heal Analyzer e integrações
REDI-SUS/FHIR/RNDS continuam documentados nos diretórios canônicos do repositório.

- [Segurança e privacidade](security-and-privacy.md)
- [Estratégia de ambientes](environments.md)
- [Backup e recuperação](backup-and-recovery.md)
- [Dicionário de dados](data-dictionary.md)
- [Capacidade do PostgreSQL](postgres-capacity.md)
- [ADR de preparo de imagens clínicas](decisions/0003-clinical-image-preparation.md)
- [Migrações, RLS e Storage](../supabase/README.md)

Ao alterar schema, políticas, bucket ou contrato persistido, atualize
`data-dictionary.json` e execute `npm run docs:data:refresh`. A CI usa
`npm run docs:data:check` para impedir divergência entre o JSON, o Markdown
gerado e os hashes das migrações.
