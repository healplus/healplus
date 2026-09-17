# HEAL+ · REDISUS

Plataforma de apoio ao acompanhamento clínico de feridas. Reúne cadastro de pacientes, avaliações, imagens, evolução e exportação de informações clínicas em um único projeto.

[![CI Web](https://github.com/healplus/healplus/actions/workflows/ci-web.yml/badge.svg)](https://github.com/healplus/healplus/actions/workflows/ci-web.yml)
[![CI Python](https://github.com/healplus/healplus/actions/workflows/ci-python.yml/badge.svg)](https://github.com/healplus/healplus/actions/workflows/ci-python.yml)
[![Licença Apache 2.0](https://img.shields.io/badge/Licen%C3%A7a-Apache%202.0-blue)](LICENSE)

## O projeto

- Cadastro e acompanhamento de pacientes com histórico de avaliações.
- Registro de imagens e delimitação manual da região da ferida.
- Agenda, relatórios e comparação da evolução.
- Autenticação, dados web e armazenamento no Supabase.
- API clínica em Python e contratos de interoperabilidade FHIR R4.
- Recursos experimentais de análise de imagens para pesquisa e apoio profissional.

O projeto está em desenvolvimento. Os recursos assistivos não substituem avaliação profissional e não representam validação para uso assistencial em produção.

## Tecnologias

| Camada | Tecnologias |
| --- | --- |
| Interface web | React 18, TypeScript, Vite e Tailwind CSS |
| Autenticação e dados web | Supabase Auth, PostgreSQL com RLS e Storage |
| API clínica | Python 3.11+, Flask e repositório clínico local SQLite |
| Imagens e pesquisa | OpenCV e módulos opcionais de aprendizado de máquina |
| Testes | Vitest, Playwright e pytest |

## Executar localmente

Requisitos: Node.js 22+, Python 3.11+ e um projeto Supabase configurado. Para o Supabase local, instale também Docker.

1. Copie `.env.example` para `.env.local` **na raiz do repositório**.
2. Preencha `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `VITE_SUPABASE_URL` e `VITE_SUPABASE_ANON_KEY` com os dados do mesmo projeto. O frontend recebe somente a chave pública.
3. Prepare o banco e os buckets conforme o [guia Supabase](docs/operations/supabase.md).

Em um terminal, inicie a API:

```bash
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements-api.txt
python -m apps.heal_plus.api.run
```

Em outro terminal, inicie o frontend:

```bash
cd apps/heal_plus/web
npm ci
npm run dev
```

O Vite informa o endereço da interface. O healthcheck da API fica em `http://localhost:5000/api/v1/health`.

## Estrutura

```text
apps/heal_plus/web/   Interface React
apps/heal_plus/api/   API Flask
backend/             Integração HTTP com Supabase
packages/            Domínio clínico e serviços compartilhados
src/                 Processamento, interoperabilidade e módulos clínicos
supabase/            Migrações, políticas de acesso e testes de banco
tests/               Testes Python
docs/                Documentação técnica e de produto
ml/                  Organização dos materiais de pesquisa
```

## Verificar alterações

```bash
# Na pasta apps/heal_plus/web
npm run lint
npm test
npm run build
npm run test:e2e

# Na raiz
python -m pip install -r requirements-ci.txt
python -m pytest tests/test_api_security.py tests/test_negative_authorization.py tests/test_supabase_client.py -q
npx supabase test db
```

## Documentação

- [Configuração do Supabase](docs/operations/supabase.md)
- [Frontend](apps/heal_plus/web/README.md) e [API](apps/heal_plus/api/README.md)
- [Arquitetura](docs/architecture/system-architecture.md)
- [Contratos FHIR R4](src/interoperability/fhir_r4/README.md)
- [Segurança](SECURITY.md) e [privacidade](docs/compliance/LGPD.md)
- [Estratégia de treinamento](docs/HEAL_ANALYZER_TRAINING_STRATEGY.md)

## Contribuir

Consulte as [diretrizes do projeto](AGENTS.md), abra uma [issue](https://github.com/healplus/healplus/issues) e envie alterações por pull request. Use apenas dados sintéticos em testes e exemplos; não inclua prontuários, imagens de pacientes ou credenciais no Git.

Licenciado sob a [Apache License 2.0](LICENSE).
