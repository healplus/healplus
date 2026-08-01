# Heal+ Web

Versão web do Heal+ reconstruída em React + TypeScript + Vite + Supabase. O app usa Supabase Auth (e-mail/senha + Google OAuth) e Supabase Database/Storage como fonte de dados. Não há banco mockado como origem principal.

## Stack

- React, TypeScript, Vite e React Router
- Tailwind CSS e Lucide React
- React Hook Form + Zod
- Supabase JS SDK: Auth (e-mail/senha, Google OAuth), Postgres Database e Storage
- Vitest + React Testing Library
- Playwright opcional para E2E

## Funcionalidades

- Landing Page moderna com fundo de partículas interativo (`<DotField />` do React Bits)
- Header inteligente flutuante e retrátil (estilo Aurelis) com transição suave ao rolar a página
- Suporte a temas dinâmicos (Modo Claro e Modo Escuro) no Hero, Header e em toda a aplicação
- Cadastro, login, recuperação de senha, logout remoto e rotas protegidas
- OAuth com Google (redirect/PKCE via `/auth/callback`)
- Perfil em `users` (Supabase Postgres)
- Dashboard com pacientes ativos, avaliações, agenda e arquivados
- CRUD de pacientes e avaliações no Supabase
- Upload de imagens para Supabase Storage
- Editor de ROI web com polígono e caneta fina, coordenadas normalizadas
- Relatório imprimível ou salvável como PDF pelo navegador
- Comparativo de duas avaliações reais
- Assistente de análise clínica (HEAL Analyzer) com token de autorização Supabase

## Configuração Supabase

1. Crie um projeto no Supabase.
2. Ative Authentication com E-mail/Senha e Google Provider.
   - Adicione `${ORIGIN}/auth/callback` nas Redirect URLs de Auth.
3. Copie `.env.example` para `.env.local`.
4. Preencha as variáveis `VITE_SUPABASE_URL` e `VITE_SUPABASE_ANON_KEY`.

Nunca coloque chaves privadas ou service accounts no código. As chaves anon do Supabase não são segredo, mas devem ficar em variáveis de ambiente.

## Variáveis

```bash
VITE_SUPABASE_URL=
VITE_SUPABASE_ANON_KEY=
VITE_CLINICAL_API_URL=/api/clinical
VITE_HEAL_ANALYZER_LOCAL_MODE=false
VITE_HEAL_ANALYZER_ENABLE_SERVER_INFERENCE=true
VITE_HEAL_ANALYZER_ENABLE_VALIDATED_TISSUE_MODEL=false
VITE_MAX_IMAGE_UPLOAD_MB=10
```

## Rodar localmente

```bash
npm install
npm run dev
```

Abra `http://127.0.0.1:5173`.

## Testes

```bash
npm run test
npm run test:coverage
```

Os testes cobrem:
- Validações de login, cadastro, recuperação de senha e callback
- Provider de sessão Supabase e isolamento de estado
- Módulos e componentes principais

## Segurança

- Cada usuário acessa somente seus dados vinculados ao `uid` do Supabase.
- Endpoints clínicos exigem token Bearer válido emitido pelo Supabase Auth.
- Upload limitado a 10 MB por validação no cliente.
- Segredos não ficam no repositório.
