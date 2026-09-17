# Exercício de incidente e direitos de dados — 2026-07-27

## Escopo e regra de segurança

Este exercício usa exclusivamente identidades e conteúdo sintéticos. Nenhum
token, chave, prompt completo, imagem ou registro clínico é incluído nas
evidências. O objetivo é validar o comportamento operacional, não declarar
conformidade regulatória.

## Papéis e contatos

| Papel | Responsabilidade | Canal |
|---|---|---|
| Pessoa de plantão técnico | conter acesso, revogar sessão e preservar evidência mínima | reporte privado previsto em `SECURITY.md` |
| Responsável pelo repositório | coordenar correção, regressão e publicação técnica | `CODEOWNERS` e pull request restrita |
| Encarregado de privacidade institucional | validar identidade, base legal, exportação, retenção e descarte | canal institucional a ser designado antes do piloto |
| Responsável clínico institucional | avaliar impacto assistencial e orientar comunicação segura | canal institucional a ser designado antes do piloto |

A ausência dos dois contatos institucionais nomeados é um bloqueio para uso
assistencial, não uma permissão para o papel técnico assumir essas atribuições.

## Cenário 1 — exposição de token

1. Classificar o evento sem copiar o token para issue, chat, log ou screenshot.
2. Encerrar a sessão local e solicitar revogação remota.
3. Se a revogação remota falhar, manter o aviso visível e orientar a revogação
   no provedor antes de reutilizar dispositivo compartilhado.
4. Registrar apenas `request_id`, ator interno, ação `session_revoked` ou
   `authorization_denied`, alvo técnico, resultado e `reason_code`.
5. Rotacionar a credencial no provedor e adicionar teste de regressão.

Resultado exercitado: `tests/test_api_security.py` confirma que logout revoga a
sessão e que a reutilização do token falha com `401`. O contrato
`packages/shared/audit.py` recusa chaves e campos sensíveis.

## Cenário 2 — exportação sintética

1. Autenticar a pessoa solicitante.
2. Revalidar ownership ou atribuição do recurso no servidor.
3. Diferenciar exportação local de publicação externa.
4. Para publicação FHIR, exigir destino exato, ação explícita, referência e
   escopo de consentimento, aprovação institucional e referência de
   compensação.
5. Registrar apenas hash, destino técnico, status e identificadores mínimos.

Resultado exercitado: `tests/test_api_security.py` prova que exportação sem
autenticação é negada; `tests/test_fhir_publication.py` prova fail-closed sem
ação, consentimento, destino ou aprovação e verifica que a auditoria não guarda
o bundle nem a resposta clínica.

## Cenário 3 — exclusão sintética

O pedido foi autenticado e classificado, mas a exclusão definitiva permaneceu
negada. O contrato provisório `docs/security/access-control.md` desabilita hard
delete até haver decisão institucional sobre retenção, descarte, continuidade
assistencial e obrigações legais.

Resultado verificável: nenhum registro foi apagado e nenhuma rota administrativa
foi criada para contornar a política. A solicitação deve ficar em fila
institucional fora do repositório, com identidade validada, escopo enumerado e
decisão registrada. Este resultado é um bloqueio P0 para piloto com dados reais.

## Cenário 4 — revogação e troca de usuário

1. Limpar chave BYOK e histórico clínico do `sessionStorage` antes de qualquer
   chamada de rede.
2. Remover canais em tempo real da identidade anterior.
3. Remontar a área protegida para descartar estado React em memória.
4. Redirecionar deep links sem sessão sem renderizar conteúdo protegido.

Resultado exercitado: a suíte Playwright em
`apps/heal_plus/web/src/tests/e2e/smoke.spec.ts` valida deep link sem sessão,
limpeza de estado sensível e acesso cruzado sem enumeração. Os testes de
`ProtectedRoute` validam ausência de flash e remontagem na troca de usuário.

## Evidências executadas

Em 2026-07-27, no commit de trabalho desta entrega:

- `python -m pytest tests/test_audit_contract.py tests/test_fetch_verified_artifact.py tests/test_fhir_publication.py tests/test_wound_analysis_api.py tests/test_api_security.py -q`
  — 54 testes aprovados;
- `python -m pytest -m "not slow and not ml" -q` — 414 testes aprovados;
- `npx vitest run src/tests/unit/ai-chat-service.test.ts src/tests/unit/ai-provider.test.ts src/tests/unit/clinical-agent.test.ts src/tests/components/app-shell.test.tsx src/tests/components/protected-route.test.tsx --reporter=verbose`
  — 22 testes aprovados;
- `npm test` — 77 testes unitários e de componentes aprovados;
- `npm run test:rules` — 24 testes de isolamento Firestore/Storage aprovados;
- `npm run lint` e `npm run build` — typecheck e build de produção aprovados;
- `npm run test:e2e` — cinco jornadas sintéticas aprovadas em Chromium;
- equivalente local do Artifact Guard — aprovado, sem artefato proibido
  atualmente rastreado.

Traces e screenshots são produzidos somente em falha, usam fixtures sintéticas
e têm retenção de sete dias na CI.

## Resultado

O exercício de contenção, exportação, revogação e troca de usuário passou nos
controles técnicos testados. A exclusão definitiva falhou fechada por decisão de
governança pendente. Portanto, o resultado é adequado para continuar testes
técnicos sintéticos e é **NO-GO para dados reais ou uso assistencial**.
