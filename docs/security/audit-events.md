# Contrato de auditoria clínica e de segurança

Status: decisão provisória para o piloto técnico. Não define prazo regulatório definitivo.

## Objetivo

Registrar quem realizou qual ação, sobre qual alvo, quando, com qual resultado e em qual requisição, sem transformar a auditoria em cópia de prontuário, prompt, imagem ou credencial.

O contrato canônico é `audit_events_v1`, implementado em `packages/shared/audit.py` e validado por `tests/test_audit_contract.py`.

## Campos obrigatórios

| Campo | Regra |
| --- | --- |
| `contract_version` | `1.0` |
| `actor_type` | `human` ou `system` |
| `actor_id` | identificador técnico; não usar nome, e-mail ou telefone |
| `actor_role` | papel efetivo no momento da ação |
| `action` | vocabulário `snake_case` |
| `target_type` | tipo técnico do recurso |
| `target_id` | identificador técnico do recurso |
| `request_id` | correlação entre resposta, logs operacionais e evento |
| `outcome` | `succeeded`, `denied` ou `failed` |
| `created_at` | timestamp UTC |
| `metadata` | objeto restrito pela allowlist |

`patient_id` e `case_id` são opcionais e servem apenas para autorização e consulta por escopo. Não substituem o alvo.

## Vocabulário inicial de ações

- sessão e autorização: `session_revoked`, `authorization_denied`;
- caso clínico: `case_claimed`, `case_handoff`;
- plano: `care_plan_created`, `care_plan_updated`, `care_plan_created_from_reviewed_ai`;
- acompanhamento: `follow_up_created`, `follow_up_completed`, `follow_up_scheduled_from_reviewed_ai`;
- alertas: `alert_claimed`, `alert_handoff`, `alert_acknowledged`, `alert_resolved`, `alert_created_from_reviewed_ai`;
- avaliação e imagem: `evaluation_created`, `clinical_image_uploaded`;
- IA: `analysis_requested`, `analysis_completed`, `analysis_failed`,
  `inference_result_created`, `inference_result_reviewed`;
- interoperabilidade: `fhir_publication_started`, `fhir_publication_succeeded`, `fhir_publication_failed`.

Novas ações devem representar um fato concluído ou negado, não conteúdo clínico.

## Allowlist de metadata

Somente escalares nos campos abaixo:

`attempts`, `bundle_hash`, `consent_scope`, `degraded`, `http_status`, `mode`, `model`, `provider`, `publication_id`, `reason_code`, `review_required`, `run_id`, `severity`, `source`, `status`, `target_role`.

Campos desconhecidos são descartados por chamadores legados e rejeitados nos novos limites de confiança.

## Conteúdo proibido

- `before`/`after` completos;
- notas, anamneses, laudos, recomendações e prontuários;
- nomes, e-mails, telefones e outros identificadores diretos;
- imagens, base64, arquivos ou URLs assinadas;
- prompts, mensagens ou respostas de IA;
- chaves, tokens, credenciais, cookies e cabeçalhos de autorização;
- corpo completo de request/response ou erro de terceiro.

## Imutabilidade

O fluxo normal oferece somente inserção e consulta. Triggers SQLite bloqueiam `UPDATE` e `DELETE` em `audit_events_v1`. Correção de um evento exige novo evento correlacionado; não altera o original.

## Acesso e retenção provisória

- A consulta clínica exige autenticação e autorização para o caso.
- Eventos sem caso, como negações e revogação de sessão, não possuem rota pública de consulta.
- Exportação em massa e administração de retenção permanecem desabilitadas até aprovação de governança.
- Para o piloto técnico, a retenção operacional proposta é de 180 dias, sujeita a revisão da pessoa responsável por privacidade e da instituição antes de qualquer dado real.
- O armazenamento SQLite local é evidência de desenvolvimento; não é ledger institucional de produção.

## Verificação

`python -m pytest tests/test_audit_contract.py tests/test_api_security.py -q`

Os testes cobrem eventos válidos, rejeição de metadata proibida, ausência de snapshots e tentativa de alteração/exclusão.
