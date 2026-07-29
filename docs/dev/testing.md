# Estratégia de testes

O objetivo da suíte é proteger o fluxo clínico principal:

`paciente -> lesão -> imagem -> IA -> avaliação -> evolução -> plano -> acompanhamento`

## Perfis de teste

- `unit`: regras puras, validações, serialização e utilitários.
- `contract`: contratos HTTP, payloads de inferência, erros e schemas.
- `fhir`: recursos e bundles HL7 FHIR R4.
- `integration`: API, banco temporário, uploads e fluxo clínico.
- `smoke`: entrypoints mínimos usados pela CI.
- `security`: autenticação, autorização, RBAC e headers.
- `e2e`: jornadas completas.
- `ml`: testes que dependem de modelos, datasets ou treinamento.
- `slow`: testes longos ou sensíveis a ambiente.

## Comandos

```powershell
python scripts/check_runtime_profiles.py
python -m ruff check apps packages src tests scripts main.py heal_platform.py realtime_app.py
python -m ruff check --select E,F,I,UP,B,SIM apps packages src tests scripts main.py heal_platform.py realtime_app.py
python -m ruff format --check apps packages src tests scripts main.py heal_platform.py realtime_app.py
python -m pytest
python -m pytest -m "not slow and not ml"
python -m pytest -m contract
python -m pytest -m fhir
python -m pytest tests/test_clinical_api_contracts.py tests/test_fhir_client.py tests/test_risk_stratification.py tests/test_official_api_factory.py tests/test_api_security.py -q
python -m pytest tests/test_runtime_profiles.py tests/test_pilot_gate.py -q
python -m pytest --cov=apps --cov=packages --cov=src/interoperability --cov=src/risk --cov-report=term-missing --cov-report=xml
```

Frontend:

```powershell
Set-Location web/redisus-frontend
npm run lint
npm test
npm run build
npm run test:rules
npx playwright install chromium
npm run test:e2e
```

## Cobertura

Meta inicial:

- 45% no smoke gate da CI, para não bloquear a limpeza inicial do repositório.
- 60% após remover artefatos e estabilizar fixtures.
- 80% nos módulos críticos: segurança, domínio clínico, contratos FHIR e validação de payloads.

Cobertura baixa em código legado não deve bloquear a migração, mas código novo em API, segurança, FHIR e domínio clínico deve entrar com teste.

## Lint e formatação

O gate inicial da CI usa Ruff apenas para erros fatais de sintaxe/importação indefinida. O lint completo e a formatação ainda encontram dívida técnica histórica e devem ser tratados em PRs dedicados, para evitar um commit mecânico grande misturado com mudanças de governança.

## Dados de teste

Use fixtures sintéticas, imagens pequenas e bancos temporários. Dados clínicos reais, datasets completos e checkpoints não devem entrar em `tests/`.

O Playwright usa `.env.e2e`, Firebase Auth Emulator e respostas Supabase
simuladas. As jornadas cobrem:

- cancelamento do consentimento antes de contexto clínico;
- deep link com sessão ausente/expirada;
- identificador pertencente a outro usuário;
- timeout/erro do provedor sem ecoar segredo e com mensagem preservada.

Screenshots e traces são retidos somente em falha, por sete dias na CI, e
contêm exclusivamente identidades e conteúdo sintéticos definidos na suíte.

## Ambientes limpos

O job `CI Python / api-minimal` instala apenas `requirements-api.txt`, importa o
analisador headless sem PyQt e chama `GET /api/v1/health`. Esse job protege a
separação entre API, desktop e ML. O job Python principal usa
`requirements-ci.txt`, que acrescenta pytest, cobertura, Ruff e mypy.
