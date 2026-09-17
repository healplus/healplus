# Supabase no HEAL+

O Supabase atende autenticação, perfis, pacientes e avaliações do frontend, agenda, resultados de análise, histórico de conversas e armazenamento de imagens. A API clínica mantém seu repositório SQLite e contratos FHIR; esta mudança não unifica automaticamente esses registros com os pacientes web.

## Configuração

- Na raiz, copie `.env.example` para `.env.local`; o Vite lê o ambiente da raiz.
- Configure `SUPABASE_URL` e `SUPABASE_PUBLISHABLE_KEY` para a API. `SUPABASE_ANON_KEY` aceita projetos com a chave pública legada.
- Configure `VITE_SUPABASE_URL` e `VITE_SUPABASE_ANON_KEY` para o mesmo projeto no frontend. A variável de nome legado também aceita a chave publishable.
- Ative e-mail/senha e, se necessário, Google no Auth. Adicione a origem da aplicação e `/auth/callback` às URLs permitidas.
- Nunca configure `service_role` ou chave secreta no frontend. A API também usa a chave pública e o JWT de cada requisição; não contorna RLS.

## Banco e armazenamento

A migração em `supabase/migrations` descreve as tabelas usadas pelos serviços web e as tabelas `analyses`, `ai_conversations` e `ai_messages` da integração Python. Perfis editáveis não concedem permissões clínicas: papéis e escopos da API são atribuídos por administradores em `app_metadata` do Supabase Auth.

As políticas exigem proprietário e sessão ativa. A função privada que consulta `auth.sessions` retorna somente um booleano relativo ao usuário e à sessão autenticados. O logout global remove sessões no Auth; a API, o banco e o Storage recusam sua reutilização.

Os buckets `wound-images` e `analysis-images` são privados. O frontend resolve imagens de avaliações por URLs assinadas de uma hora, renovadas ao carregar a avaliação. Depois desse prazo, recarregue a página. URLs assinadas já emitidas permanecem válidas até expirar, inclusive após logout; não as compartilhe. `profile-photos` permanece público para os avatares, com escrita restrita ao titular. Todos limitam uploads a 10 MiB e JPEG, PNG ou WebP.

## Validar e implantar

Para uma instância local nova, com Docker ativo:

```bash
npx supabase start
npx supabase test db
npx supabase db lint --local
```

Antes de aplicar em um projeto existente, faça backup, compare as tabelas/colunas, vínculos e políticas existentes com a migração e reconcilie eventuais diferenças. `CREATE TABLE IF NOT EXISTS` não adapta colunas de uma instalação anterior. Não execute reset em produção.

Depois de conferir o destino, vincule o projeto e aplique as migrações com a CLI (`supabase link` e `supabase db push`). Valide login, logout, upload e CRUD com duas contas de teste antes de liberar dados reais. A existência dos arquivos no Git não comprova aplicação no projeto remoto.

Dados e contas do provedor anterior não são transferidos nem excluídos automaticamente. Uma importação exige exportação autorizada, mapeamento de identidades e validação dos vínculos. Serviços e hospedagem externos precisam ser desativados separadamente, após validar o destino.

Falhas ao salvar análises são expostas por `persisted: false`. Histórico e gravação de conversas indisponíveis retornam `503`, em vez de simular sucesso.

Referências: [sessões](https://supabase.com/docs/guides/auth/sessions), [RLS](https://supabase.com/docs/guides/database/postgres/row-level-security) e [Storage](https://supabase.com/docs/guides/storage/security/access-control).
