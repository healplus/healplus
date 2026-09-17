# DicionÃ¡rio de dados e contratos persistidos

> Arquivo gerado a partir de `docs/data-dictionary.json`. NÃ£o edite manualmente.

Este documento descreve os dados persistidos pelo HEAL+, sua finalidade, classificaÃ§Ã£o, relacionamentos e controles. As migraÃ§Ãµes em `supabase/migrations/` continuam sendo a fonte executÃ¡vel do schema.

## Fontes versionadas

| Fonte | SHA-256 |
| --- | --- |
| `supabase/migrations/202608030001_initial_schema.sql` | `49ece4b9bd97d6053d01a9dfd10f2484acfc893b37d4f2e29bc4f0320182a778` |
| `supabase/migrations/202608040002_repair_clinical_rls_policies.sql` | `af1e61fc69144d2fd9ca8b649d23b4e4bdeef43d8c295e04416ae826e940c805` |
| `supabase/migrations/20260811005338_repair_storage_buckets_and_policies.sql` | `bccccc137ffc1f07f6070c76b9690af9e90abfa07d119208717c9ce424fbd112` |
| `supabase/migrations/20260811005855_allow_profile_photo_owner_select.sql` | `e5505cf9690597aa8595495d96cf4eb574159418aa3a224ceffda246e2698de2` |
| `supabase/migrations/202608130001_index_clinical_foreign_keys.sql` | `e924eaf15bb178d0dd40ab9cdac7d1a160203aef9a932c7718e34c6598cf2529` |

Contratos de aplicaÃ§Ã£o conferidos em: `src/lib/types.ts`, `src/features/auth/authService.ts`, `src/features/evaluations/evaluationSchema.ts`, `src/features/evaluations/evaluationService.ts`.

## ClassificaÃ§Ã£o

| Identificador | Classe | Tratamento |
| --- | --- | --- |
| `system` | Sistema interno | Metadado técnico sujeito a controle de acesso e minimização de logs. |
| `account` | Dados da conta profissional | Dado pessoal do profissional; acesso restrito ao titular e exposição mínima. |
| `personal-sensitive` | Dado pessoal sensível | Identifica ou contata o paciente; exige autenticação, RLS e evidências sintéticas. |
| `clinical-sensitive` | Dado clínico sensível | Informação de saúde; exige autenticação, RLS, acesso mínimo e ausência em logs. |

## Tabelas pÃºblicas

RLS e privilÃ©gios SQL sÃ£o camadas diferentes. As migraÃ§Ãµes atuais habilitam RLS e criam polÃ­ticas para `authenticated`, mas nÃ£o contÃªm `GRANT`/`REVOKE` explÃ­cito para estas tabelas; a exposiÃ§Ã£o pela Data API tambÃ©m depende dos privilÃ©gios configurados no ambiente Supabase.

### `public.users`

Mantém o perfil e as preferências do profissional vinculado à identidade do Supabase Auth.

- ClassificaÃ§Ã£o predominante: `account`
- ProprietÃ¡rio: `uid`
- RLS: habilitada; polÃ­tica `users_own_profile` para `authenticated` â€” o uid da sessão deve ser igual ao uid do perfil
- Realtime: nÃ£o publicada
- PrivilÃ©gios da Data API: authenticated recebe SELECT, INSERT, UPDATE e DELETE explícitos; anon não recebe acesso

| Campo | DefiniÃ§Ã£o PostgreSQL | ClassificaÃ§Ã£o | Finalidade |
| --- | --- | --- | --- |
| `uid` | `uuid primary key references auth.users(id) on delete cascade` | `system` | Identifica e vincula o perfil à conta autenticada. |
| `display_name` | `text not null default 'Profissional'` | `account` | Nome exibido do profissional na interface. |
| `email` | `text not null default ''` | `account` | Endereço de e-mail associado ao perfil profissional. |
| `photo_url` | `text` | `account` | URL pública opcional da foto de perfil profissional. |
| `provider_ids` | `text[] not null default '{}'` | `system` | Lista os provedores de autenticação vinculados à conta. |
| `role` | `text not null default 'professional'` | `system` | Registra o papel de aplicação permitido para o perfil. |
| `settings` | `jsonb not null default '{}'` | `account` | Persiste preferências de tema, notificações e privacidade visual. |
| `professional_area` | `text not null default ''` | `account` | Área de atuação informada pelo profissional. |
| `clinic_name` | `text not null default ''` | `account` | Nome da clínica ou organização informado no perfil. |
| `phone` | `text not null default ''` | `account` | Telefone de contato do profissional. |
| `onboarding_completed` | `boolean not null default false` | `system` | Indica se a configuração inicial do perfil foi concluída. |
| `created_at` | `timestamptz not null default timezone('utc', now())` | `system` | Registra em UTC a criação do perfil. |
| `updated_at` | `timestamptz not null default timezone('utc', now())` | `system` | Registra em UTC a última atualização do perfil. |

Relacionamentos:

- `uid` referencia `auth.users.id` com exclusão em cascata.
- A mesma identidade é referenciada por `patients.user_id`, `evaluations.user_id` e `appointments.user_id`.

Ãndices:

- Apenas o Ã­ndice criado pela chave primÃ¡ria.

### `public.patients`

Mantém o cadastro e o estado de arquivamento de pacientes pertencentes a um profissional.

- ClassificaÃ§Ã£o predominante: `clinical-sensitive`
- ProprietÃ¡rio: `user_id`
- RLS: habilitada; polÃ­tica `patients_owned_by_professional` para `authenticated` â€” o uid da sessão deve ser igual ao user_id do paciente
- Realtime: publicada em `supabase_realtime`
- PrivilÃ©gios da Data API: authenticated recebe SELECT, INSERT, UPDATE e DELETE explícitos; anon não recebe acesso

| Campo | DefiniÃ§Ã£o PostgreSQL | ClassificaÃ§Ã£o | Finalidade |
| --- | --- | --- | --- |
| `id` | `uuid primary key default gen_random_uuid()` | `system` | Identifica o paciente dentro dos relacionamentos persistidos. |
| `user_id` | `uuid not null references auth.users(id) on delete cascade` | `system` | Define o profissional proprietário usado pela autorização RLS. |
| `name` | `text not null check (char_length(name) between 2 and 120)` | `personal-sensitive` | Nome do paciente exibido nos fluxos clínicos. |
| `phone` | `text not null default ''` | `personal-sensitive` | Telefone opcional de contato do paciente. |
| `email` | `text not null default ''` | `personal-sensitive` | E-mail opcional de contato do paciente. |
| `birth_date` | `text not null default ''` | `personal-sensitive` | Data de nascimento informada para identificação e contexto assistencial. |
| `notes` | `text not null default ''` | `clinical-sensitive` | Observações livres associadas ao cadastro do paciente. |
| `archived` | `boolean not null default false` | `system` | Indica ocultação operacional sem apagar o cadastro e o histórico. |
| `created_at` | `timestamptz not null default timezone('utc', now())` | `system` | Registra em UTC a criação do cadastro. |
| `updated_at` | `timestamptz not null default timezone('utc', now())` | `system` | Registra em UTC a última atualização do cadastro. |

Relacionamentos:

- `user_id` referencia `auth.users.id` com exclusão em cascata.
- `evaluations.patient_id` e `appointments.patient_id` referenciam `patients.id` com exclusão em cascata.

Ãndices:

- `patients_user_id_idx (user_id)`

### `public.evaluations`

Persiste avaliações estruturadas da ferida, observações clínicas, imagens e demarcações ROI.

- ClassificaÃ§Ã£o predominante: `clinical-sensitive`
- ProprietÃ¡rio: `user_id`
- RLS: habilitada; polÃ­tica `evaluations_owned_by_professional` para `authenticated` â€” a sessão deve possuir a avaliação e também o paciente relacionado
- Realtime: publicada em `supabase_realtime`
- PrivilÃ©gios da Data API: authenticated recebe SELECT, INSERT, UPDATE e DELETE explícitos; anon não recebe acesso

| Campo | DefiniÃ§Ã£o PostgreSQL | ClassificaÃ§Ã£o | Finalidade |
| --- | --- | --- | --- |
| `id` | `uuid primary key default gen_random_uuid()` | `system` | Identifica a avaliação clínica. |
| `patient_id` | `uuid not null references public.patients(id) on delete cascade` | `system` | Vincula a avaliação ao paciente autorizado. |
| `user_id` | `uuid not null references auth.users(id) on delete cascade` | `system` | Define o profissional proprietário usado pela autorização RLS. |
| `patient_name` | `text not null default ''` | `personal-sensitive` | Mantém um snapshot do nome para apresentação histórica. |
| `date` | `text not null` | `clinical-sensitive` | Data clínica informada para a avaliação. |
| `wound_location` | `text not null default ''` | `clinical-sensitive` | Descreve a localização anatômica da ferida. |
| `wound_etiology` | `text not null default ''` | `clinical-sensitive` | Registra a etiologia informada para a ferida. |
| `pain_level` | `integer not null default 0 check (pain_level between 0 and 10)` | `clinical-sensitive` | Registra a intensidade de dor em escala fechada de zero a dez. |
| `exudate_amount` | `text not null default ''` | `clinical-sensitive` | Registra a quantidade observada de exsudato. |
| `exudate_type` | `text not null default ''` | `clinical-sensitive` | Registra o tipo observado de exsudato. |
| `border_characteristics` | `text not null default ''` | `clinical-sensitive` | Descreve as características observadas das bordas da ferida. |
| `periwound_skin` | `text not null default ''` | `clinical-sensitive` | Descreve a condição observada da pele perilesional. |
| `infection_signs` | `text[] not null default '{}'` | `clinical-sensitive` | Lista sinais de infecção registrados pelo profissional. |
| `timers` | `jsonb not null default '{}'` | `clinical-sensitive` | Agrupa os registros textuais do framework TIMERS. |
| `comorbidities` | `text[] not null default '{}'` | `clinical-sensitive` | Lista comorbidades informadas no contexto da avaliação. |
| `medications` | `text[] not null default '{}'` | `clinical-sensitive` | Lista medicamentos informados no contexto da avaliação. |
| `notes` | `text not null default ''` | `clinical-sensitive` | Armazena observações clínicas livres da avaliação. |
| `images` | `jsonb not null default '[]'` | `clinical-sensitive` | Persiste metadados de imagens clínicas e regiões de interesse, sem binário. |
| `signature` | `text not null default ''` | `clinical-sensitive` | Registra a assinatura textual associada à avaliação. |
| `created_at` | `timestamptz not null default timezone('utc', now())` | `system` | Registra em UTC a criação da avaliação. |
| `updated_at` | `timestamptz not null default timezone('utc', now())` | `system` | Registra em UTC a última atualização da avaliação. |

Relacionamentos:

- `patient_id` referencia `public.patients.id` com exclusão em cascata.
- `user_id` referencia `auth.users.id` com exclusão em cascata.
- `patient_name` é um snapshot de apresentação; `patient_id` permanece o vínculo de autoridade.

Ãndices:

- `evaluations_user_patient_date_idx (user_id, patient_id, date desc)`

### `public.appointments`

Mantém compromissos de acompanhamento vinculados ao paciente e ao profissional proprietário.

- ClassificaÃ§Ã£o predominante: `clinical-sensitive`
- ProprietÃ¡rio: `user_id`
- RLS: habilitada; polÃ­tica `appointments_owned_by_professional` para `authenticated` â€” a sessão deve possuir o compromisso e também o paciente relacionado
- Realtime: publicada em `supabase_realtime`
- PrivilÃ©gios da Data API: authenticated recebe SELECT, INSERT, UPDATE e DELETE explícitos; anon não recebe acesso

| Campo | DefiniÃ§Ã£o PostgreSQL | ClassificaÃ§Ã£o | Finalidade |
| --- | --- | --- | --- |
| `id` | `uuid primary key default gen_random_uuid()` | `system` | Identifica o compromisso na agenda. |
| `user_id` | `uuid not null references auth.users(id) on delete cascade` | `system` | Define o profissional proprietário usado pela autorização RLS. |
| `patient_id` | `uuid not null references public.patients(id) on delete cascade` | `system` | Vincula o compromisso ao paciente autorizado. |
| `patient_name` | `text not null` | `personal-sensitive` | Mantém um snapshot do nome para apresentação na agenda. |
| `date` | `text not null` | `clinical-sensitive` | Data informada para o compromisso. |
| `time` | `text not null` | `clinical-sensitive` | Horário informado para o compromisso. |
| `type` | `text not null` | `clinical-sensitive` | Tipo de atendimento ou retorno agendado. |
| `status` | `text not null default 'Pendente' check (status in ('Confirmado', 'Pendente', 'Cancelado', 'Realizado'))` | `clinical-sensitive` | Estado operacional atual do compromisso. |
| `notes` | `text not null default ''` | `clinical-sensitive` | Observações livres associadas ao compromisso. |
| `created_at` | `timestamptz not null default timezone('utc', now())` | `system` | Registra em UTC a criação do compromisso. |
| `updated_at` | `timestamptz not null default timezone('utc', now())` | `system` | Registra em UTC a última atualização do compromisso. |

Relacionamentos:

- `patient_id` referencia `public.patients.id` com exclusão em cascata.
- `user_id` referencia `auth.users.id` com exclusão em cascata.
- `patient_name` é um snapshot de apresentação; `patient_id` permanece o vínculo de autoridade.

Ãndices:

- `appointments_user_date_idx (user_id, date, time)`

## Contratos JSON persistidos

### `public.users.settings` â€” UserProfile.settings

Contrato de preferências persistidas para aparência, notificações e privacidade visual.

Fonte TypeScript: `src/lib/types.ts`.

| Caminho | Tipo | ObrigatÃ³rio | ClassificaÃ§Ã£o | Finalidade |
| --- | --- | --- | --- | --- |
| `theme` | `'light' \| 'dark'` | sim | `account` | Seleciona o tema visual preferido. |
| `notificationsEnabled` | `boolean` | sim | `account` | Controla a habilitação geral de notificações. |
| `emailNotificationsEnabled` | `boolean` | nÃ£o | `account` | Controla notificações enviadas por e-mail. |
| `agendaRemindersEnabled` | `boolean` | nÃ£o | `account` | Controla lembretes relacionados à agenda. |
| `hideEmailPreview` | `boolean` | nÃ£o | `account` | Controla a ocultação visual da prévia do e-mail. |
| `showProfilePhoto` | `boolean` | nÃ£o | `account` | Controla a exibição da foto do perfil. |

- Novos perfis recebem todos os campos preenchidos por `defaultSettings`; campos opcionais mantêm compatibilidade com perfis anteriores.

### `public.evaluations.timers` â€” Evaluation.timers

Contrato textual estruturado das seis dimensões usadas na avaliação TIMERS.

Fonte TypeScript: `src/features/evaluations/evaluationSchema.ts`.

| Caminho | Tipo | ObrigatÃ³rio | ClassificaÃ§Ã£o | Finalidade |
| --- | --- | --- | --- | --- |
| `tissue` | `string (máximo 600 caracteres)` | sim | `clinical-sensitive` | Registra a observação sobre tecido. |
| `infection` | `string (máximo 600 caracteres)` | sim | `clinical-sensitive` | Registra a observação sobre infecção ou inflamação. |
| `moisture` | `string (máximo 600 caracteres)` | sim | `clinical-sensitive` | Registra a observação sobre umidade. |
| `edge` | `string (máximo 600 caracteres)` | sim | `clinical-sensitive` | Registra a observação sobre bordas. |
| `repair` | `string (máximo 600 caracteres)` | sim | `clinical-sensitive` | Registra a observação sobre reparo ou regeneração. |
| `social` | `string (máximo 600 caracteres)` | sim | `clinical-sensitive` | Registra fatores sociais relacionados ao cuidado. |

- O banco garante apenas que o valor seja JSON; o limite e a forma são validados pelo schema Zod do frontend.

### `public.evaluations.images` â€” WoundImage[] com Roi[]

Contrato dos metadados persistidos para imagens da ferida e demarcações de regiões de interesse.

Fonte TypeScript: `src/lib/types.ts`.

| Caminho | Tipo | ObrigatÃ³rio | ClassificaÃ§Ã£o | Finalidade |
| --- | --- | --- | --- | --- |
| `[].id` | `string` | sim | `system` | Identifica o item de imagem dentro da avaliação. |
| `[].storagePath` | `string` | sim | `clinical-sensitive` | Localiza o objeto privado no bucket de imagens clínicas. |
| `[].downloadURL` | `string vazio na persistência` | sim | `clinical-sensitive` | Mantém compatibilidade do contrato sem persistir a URL assinada temporária. |
| `[].fileName` | `string` | sim | `clinical-sensitive` | Registra o nome do arquivo enviado. |
| `[].contentType` | `string` | sim | `system` | Registra o tipo MIME validado da imagem. |
| `[].size` | `number` | sim | `system` | Registra o tamanho do arquivo em bytes. |
| `[].uploadedAt` | `string ISO 8601` | sim | `system` | Registra quando a imagem foi enviada. |
| `[].rois` | `Roi[]` | sim | `clinical-sensitive` | Agrupa regiões de interesse desenhadas sobre a imagem. |
| `[].rois[].id` | `string` | sim | `system` | Identifica a região de interesse. |
| `[].rois[].label` | `string` | sim | `clinical-sensitive` | Descreve a região demarcada pelo profissional. |
| `[].rois[].type` | `'polygon' \| 'freehand' \| 'circle'` | sim | `system` | Define a geometria usada para desenhar a região. |
| `[].rois[].points` | `Array<{ x: number; y: number }>` | sim | `clinical-sensitive` | Persiste as coordenadas que formam a região demarcada. |
| `[].rois[].color` | `string` | sim | `system` | Define a cor de apresentação da demarcação. |
| `[].rois[].createdAt` | `string ISO 8601` | sim | `system` | Registra quando a região foi criada. |
| `[].rois[].normalized` | `true` | nÃ£o | `system` | Indica que as coordenadas estão normalizadas em relação à imagem. |
| `[].rois[].updatedAt` | `string ISO 8601` | nÃ£o | `system` | Registra quando a região foi atualizada. |
| `[].rois[].createdBy` | `string` | nÃ£o | `account` | Identifica o profissional que criou a região quando disponível. |
| `[].rois[].updatedBy` | `string` | nÃ£o | `account` | Identifica o profissional que atualizou a região quando disponível. |
| `[].rois[].roiVersion` | `string` | nÃ£o | `system` | Registra a versão lógica do contrato da região. |
| `[].rois[].imageId` | `string` | nÃ£o | `system` | Repete o identificador da imagem para rastreabilidade interna. |
| `[].rois[].assessmentId` | `string` | nÃ£o | `system` | Registra o identificador de avaliação associado quando disponível. |
| `[].rois[].patientId` | `string` | nÃ£o | `system` | Registra o identificador do paciente associado quando disponível. |
| `[].rois[].verifiedByProfessional` | `boolean` | nÃ£o | `clinical-sensitive` | Indica confirmação explícita da demarcação por profissional. |

- O binário permanece no bucket privado `wound-images`; a coluna contém somente metadados.
- `evaluationService` grava `downloadURL` como string vazia e cria uma URL assinada de uma hora somente na leitura.
- `imageUploadStatus`, `imageUploadError`, `updatedBy` e `auditLog` pertencem ao tipo de interface `Evaluation`, mas não possuem colunas nem são enviados no payload persistido atual.

## Valores fechados

| Contrato | Valores | Origem |
| --- | --- | --- |
| `users.role` | `professional` | Contrato atual de `UserProfile.role`; o banco integrado não restringe papéis futuros por CHECK |
| `appointments.status` | `Confirmado`, `Pendente`, `Cancelado`, `Realizado` | CHECK da migração e `AppointmentStatus` |
| `users.settings.theme` | `light`, `dark` | `ThemePreference` no frontend |
| `evaluations.images[].rois[].type` | `polygon`, `freehand`, `circle` | `RoiType` no frontend |

## Storage

| Bucket | Visibilidade | Limite | MIME | ClassificaÃ§Ã£o | Finalidade e acesso |
| --- | --- | --- | --- | --- | --- |
| `wound-images` | privado | 10485760 bytes (10 MB) | `image/jpeg`, `image/png`, `image/webp` | `clinical-sensitive` | Armazena os binários privados das imagens de feridas. SELECT, INSERT, UPDATE e DELETE exigem sessão autenticada e primeiro segmento do caminho igual ao uid. |
| `profile-photos` | pÃºblico | 10485760 bytes (10 MB) | `image/jpeg`, `image/png`, `image/webp` | `account` | Armazena fotos públicas de perfil profissional; não aceita imagens clínicas. INSERT, UPDATE e DELETE exigem sessão autenticada e primeiro segmento do caminho igual ao uid; leitura é pública pela configuração do bucket. |

## Objetos auxiliares

- `public.set_updated_at()`: Atualiza `updated_at` em UTC antes de alterações nas quatro tabelas.
- `users_set_updated_at, patients_set_updated_at, evaluations_set_updated_at, appointments_set_updated_at`: Triggers que executam `public.set_updated_at()` antes de cada UPDATE.
- `supabase_realtime`: Publicação que inclui `patients`, `evaluations` e `appointments`; eventos provocam nova leitura sujeita a RLS.

## Como manter

1. Crie uma nova migraÃ§Ã£o; nÃ£o altere uma migraÃ§Ã£o jÃ¡ aplicada.
2. Atualize campos, contratos, relaÃ§Ãµes e classificaÃ§Ãµes em `docs/data-dictionary.json`.
3. Execute `npm run docs:data:refresh` para renovar os hashes e gerar este Markdown.
4. Execute `npm run docs:data:check` e os demais testes obrigatÃ³rios.

A validaÃ§Ã£o falha quando uma migraÃ§Ã£o muda, surge ou remove uma tabela/campo, uma definiÃ§Ã£o SQL diverge, ou o Markdown gerado fica desatualizado. MudanÃ§as de polÃ­tica, Storage e Realtime tambÃ©m alteram o hash e exigem revisÃ£o consciente do dicionÃ¡rio.
