# Resposta a incidentes

## Quando acionar

- suspeita de acesso indevido a paciente
- exposição de token, credencial BYOK, secret ou service account
- upload malicioso com impacto operacional
- envio indevido de contexto clínico para terceiro

Não abra issue pública com detalhes sensíveis. Use o canal privado definido em
`SECURITY.md`. Antes de qualquer piloto institucional, devem estar designados um
contato de privacidade e um responsável clínico da instituição.

## Papéis

- Plantão técnico: contenção, revogação, isolamento do ambiente e preservação
  mínima de evidência.
- Responsável do repositório: correção, revisão e testes de regressão.
- Privacidade institucional: identidade do solicitante, escopo, base legal,
  retenção, notificação e direitos do titular.
- Responsável clínico institucional: avaliação de impacto assistencial e
  continuidade segura do cuidado.

O papel técnico não substitui decisões institucionais, clínicas ou regulatórias.

## Passos imediatos

1. conter o acesso, revogar sessões/credenciais e interromper publicação externa;
2. preservar somente IDs técnicos, timestamps, `request_id`, ação, resultado e
   hashes necessários;
3. não copiar token, chave, prompt, imagem, nota ou prontuário para evidência;
4. identificar escopo e ambientes afetados por consulta autorizada;
5. corrigir a causa raiz e adicionar teste de regressão;
6. documentar linha do tempo, decisões, responsáveis e risco residual.

Se uma integração externa tiver recebido dados, acione o processo institucional
antes de qualquer tentativa de exclusão ou compensação. Uma resposta `2xx` não
garante reversão no sistema de destino.

## Pós-incidente

- rotacionar segredos
- revisar regras de acesso
- adicionar teste de regressão
- atualizar documentação e controles
- verificar que dados minimizados e temporários foram descartados conforme a
  política aplicável

O exercício sintético mais recente está em
[`privacy-operations-exercise-2026-07-27.md`](privacy-operations-exercise-2026-07-27.md).
