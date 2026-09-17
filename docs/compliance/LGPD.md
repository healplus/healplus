# LGPD e Privacidade

## Princípio

O projeto lida com contexto potencialmente sensível de saúde. Portanto, qualquer imagem clínica, identificador de paciente ou metadado associado deve ser tratado como dado sensível.

## Regras Operacionais

- não versionar dados reais de pacientes;
- usar identificadores sintéticos em testes e demos;
- separar ambientes de desenvolvimento e dados de pesquisa autorizados;
- manter evidência de consentimento e base legal fora do código-fonte;
- evitar screenshots com dados identificáveis.

## Exportação, correção e exclusão

- A identidade da pessoa solicitante e seu escopo de acesso são revalidados no
  servidor; conhecer um identificador não autoriza a operação.
- A exportação local não autoriza publicação em destino externo. Publicação FHIR
  exige ação explícita, consentimento aplicável, destino apresentado e aprovação
  institucional.
- O conjunto de recursos da solicitação deve ser enumerado e o resultado deve
  ser verificável sem replicar conteúdo clínico em logs.
- Exclusão definitiva permanece desabilitada enquanto a instituição não definir
  retenção, descarte, continuidade assistencial, base legal e responsáveis.
- Revogar acesso ou arquivar um recurso não deve ser apresentado como exclusão
  definitiva.

Solicitações reais não devem ser registradas em issues públicas. O fluxo
institucional deve manter a evidência de identidade, decisão e atendimento fora
do repositório, com acesso restrito.

## Medidas Prioritárias

- centralizar política de anonimização;
- mapear retenção de dados;
- revisar storage e controle de acesso;
- auditar integrações com Supabase e relatórios exportáveis.

## Situação Atual

- o repositório já contém mecanismos úteis de documentação e persistência;
- há controles técnicos para autenticação de exportação, revogação de sessão,
  minimização de auditoria e publicação FHIR explícita;
- ainda falta um pacote formal de governança de dados, contatos institucionais e
  política definitiva de retenção/exclusão para pilotos com dados reais.

O exercício sintético de 2026-07-27 e seus bloqueios estão documentados em
[`../security/privacy-operations-exercise-2026-07-27.md`](../security/privacy-operations-exercise-2026-07-27.md).
