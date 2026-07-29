# Relatório de prontidão do piloto técnico — 2026-07-27

## Decisão

| Uso | Decisão | Limite |
|---|---|---|
| Desenvolvimento e validação interna com dados sintéticos | **GO** | ambiente controlado, sem alegação clínica e sem integração produtiva |
| Piloto técnico com participantes externos ou dados reais | **NO-GO** | bloqueios P0 abaixo precisam ser encerrados com evidência |
| Uso assistencial ou decisão clínica | **NO-GO** | não há validação clínica, regulatória ou institucional suficiente |

Esta decisão não é aprovação regulatória, institucional nem evidência de
eficácia. Toda saída de IA continua sendo apoio à decisão e exige revisão
profissional.

## Versão avaliada

- Data da revisão: 2026-07-27.
- Branch de evidência: `codex/resolve-assigned-issues`.
- Pull request de evidência: [#73](https://github.com/healplus/healplus/pull/73).
- Frontend: `web/redisus-frontend/package.json`, versão `2.0.0`.
- API oficial: `apps/api/app.py`, versão declarada `2.0.0`.
- Contrato de análise de feridas: API `1.0.0`.
- Contrato de auditoria: `docs/security/audit-event-contract.v1.json`,
  versão `1.0`.
- Manifesto de evidências:
  `docs/operations/release-evidence/pilot-readiness-2026-07-27.json`.

O resultado dos checks remotos fica anexado à própria pull request. Enquanto
qualquer gate estiver pendente ou vermelho, a decisão permanece NO-GO fora do
desenvolvimento local sintético.

## Evidências

| Área | Evidência | Resultado |
|---|---|---|
| Python e segurança | `python -m pytest -m "not slow and not ml" -q` | 414 aprovados |
| Chat BYOK e prompt injection | `src/tests/unit/ai-chat-service.test.ts`, `ai-provider.test.ts`, `clinical-agent.test.ts` | normalização segura, fake provider, timeout, payload inválido e saída insegura cobertos |
| Shell autenticado | `src/tests/components/protected-route.test.tsx`, `app-shell.test.tsx` | sem flash, remontagem por usuário, breadcrumbs e foco cobertos |
| Frontend | `npm run lint`, `npm test`, `npm run build`, `npm run test:rules` | typecheck e build aprovados; 77 testes Vitest e 24 testes de regras aprovados |
| Jornadas negativas | `src/tests/e2e/smoke.spec.ts` | cinco jornadas sintéticas aprovadas em Chromium |
| Auditoria | `docs/security/audit-events.md` e contrato JSON v1 | append-only no SQLite, allowlist e consulta por caso autorizada |
| Incidente e direitos de dados | `docs/security/privacy-operations-exercise-2026-07-27.md` | revogação/exportação/troca aprovadas; exclusão falhou fechada |
| FHIR | `docs/architecture/fhir-publication-boundary.md` | consentimento, destino, idempotência, falha parcial e compensação definidos |
| Modelos e fallback | `packages/clinical_domain/wound_analysis.py` | estado por componente, reason codes e modo degradado exposto na UI |
| Artefatos | `docs/data/artifact-history-inventory.md` e `scripts/fetch_verified_artifact.py` | histórico inventariado; download sintético por checksum aprovado |
| Entrega | `.github/workflows/ci-web.yml`, `docs/operations/branch-policy.md` | gates definidos; proteção nativa indisponível no plano atual do repositório privado |

Comandos e contagens estão registrados no exercício operacional. Os logs e
artefatos de falha não devem ser usados para armazenar conteúdo clínico.

O lint Ruff dos arquivos Python alterados foi aprovado. A varredura global
continua encontrando sete referências indefinidas preexistentes em
`heal_analyzer.py`, arquivo não alterado nesta entrega; isso não foi ocultado nem
tratado como evidência verde.

## Bloqueios P0

| Bloqueio | Responsável pelo encerramento | Evidência exigida |
|---|---|---|
| #53 permanece aberto: consentimento e minimização devem ser concluídos em todos os caminhos BYOK, não apenas na jornada negativa coberta aqui | responsável do frontend e privacidade | teste de envio consentido e negado para cada provedor habilitado |
| #66 permanece aberto: o golden path ainda não prova revisão profissional obrigatória antes de salvar | responsável clínico do produto | E2E completo com origem IA, revisão, alteração e histórico |
| Supabase produtivo ainda não tem configuração Firebase Third-Party Auth e RLS versionadas/verificadas neste repositório | responsável de backend/dados | configuração do projeto, migrations RLS e testes com duas identidades |
| Retenção, descarte, exclusão definitiva e contatos institucionais não foram aprovados | privacidade e responsável clínico da instituição | política aprovada, contatos nomeados e exercício de exclusão verificável |

Qualquer bloqueio P0 aberto impede piloto externo ou assistencial.

## Riscos residuais P1/P2

| Risco | Responsável | Tratamento |
|---|---|---|
| #56: validação externa de bundles e terminologias FHIR incompleta | interoperabilidade | executar validador definido, broken references e snapshots |
| #61: teste moderado de usabilidade não executado | produto/acessibilidade | protocolo sintético, participantes-alvo e achados separados por severidade |
| Proteção de branch não aplicável via GitHub no plano atual do repositório privado | responsável do repositório | revisão manual documentada; habilitar ruleset quando o plano suportar |
| Migração dos blobs do histórico Git ainda não executada | responsável do repositório/dados | backup, espelho, dry-run e janela coordenada conforme inventário |
| Publicação FHIR produtiva não implementada nem aprovada | interoperabilidade e instituição | credencial server-side, ambiente homologado e runbook de compensação testado |
| Modelos opcionais podem operar em fallback determinístico | responsável de ML e clínico | manter banner degradado e impedir equivalência com modelo validado |

## Critério para mudar a decisão

Uma nova revisão deve:

1. referenciar uma pull request com todos os checks críticos verdes;
2. encerrar cada P0 com teste e artefato de evidência;
3. nomear responsáveis institucionais de privacidade e clínica;
4. repetir as jornadas negativas com duas identidades;
5. registrar separadamente autorização para piloto técnico e para qualquer uso
   assistencial.

Até lá, o produto pode evoluir apenas em validação interna sintética.
