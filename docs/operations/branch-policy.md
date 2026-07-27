# Política de branches e merge

Status: decisão aplicável ao plano atual do repositório.

## Fluxo

- `develop` é a branch padrão e de integração.
- Toda mudança entra em `develop` por pull request de branch curta.
- `main` recebe somente PR de promoção originado de `develop`.
- Push direto, force-push e exclusão de `develop`/`main` são proibidos pelo processo.
- Merge padrão: squash para mudanças isoladas; merge commit somente quando preservar a topologia for parte da evidência.
- Branches de trabalho são removidas após merge.

## Checks obrigatórios

Um PR não pode ser aprovado para merge enquanto falhar ou não executar:

- `CI Python / python-smoke`;
- `CI Web / web`;
- `CI Web / web-e2e`;
- `Artifact Guard / block-generated-artifacts`;
- `Secret Scan / gitleaks`;
- CodeQL;
- Dependency Review quando houver mudança de dependência.

Checks adiados por indisponibilidade externa precisam de issue, responsável funcional, impacto e data de reavaliação. Um check P0 de segurança, privacidade, autorização, consentimento ou segurança clínica não pode ser dispensado para piloto.

## Revisão proporcional ao risco

| Risco | Revisão mínima |
| --- | --- |
| Documentação sem decisão clínica | autor + CI |
| Código comum | CODEOWNER da superfície |
| Segurança, privacidade, auth, RLS, FHIR externo ou auditoria | CODEOWNER + revisão de segurança/privacidade |
| Prompt clínico, interpretação, fallback ou decisão assistencial | CODEOWNER + revisão clínica |
| Promoção para `main` | evidências completas + aprovação de release |

Autorrevisão não equivale a aprovação independente. Se ainda não houver segunda pessoa habilitada, a exceção pode permitir integração técnica em `develop`, mas bloqueia promoção assistencial para `main`.

## Estado da proteção automática

Em 2026-07-27, a API do GitHub respondeu `403` para branch protection e rulesets porque o repositório é privado e o plano atual não oferece o recurso. A limitação foi verificada com permissão `ADMIN`.

Enquanto essa limitação existir:

- a política é normativa e revisada em cada PR;
- os workflows executam também em push para detectar violação;
- `CODEOWNERS` define responsabilidade, mas não substitui proteção;
- qualquer push direto é incidente de processo e deve gerar registro e revisão;
- a promoção para `main` permanece bloqueada sem PR e evidência, mesmo que a plataforma aceite o push.

Ao habilitar suporte, configurar:

1. impedir exclusão e force-push;
2. exigir PR e resolução de conversas;
3. exigir branch atualizada e todos os checks acima;
4. exigir CODEOWNER;
5. não permitir bypass, exceto conta de recuperação documentada;
6. aplicar a `develop` e `main`, com aprovação adicional em `main`.

## Exceção emergencial

Somente para contenção de incidente:

1. abrir issue de incidente sem conteúdo sensível;
2. registrar responsável, justificativa e `request_id`/referência segura;
3. aplicar a menor mudança possível;
4. executar Secret Scan, CI Python, CI Web e testes afetados;
5. abrir PR retrospectivo em até um dia útil;
6. adicionar teste de regressão e revisar a causa.

Exceção não autoriza desativar revisão humana, consentimento, isolamento ou logs seguros.

## Promoção e rollback

O PR `develop -> main` referencia relatório de prontidão, versão dos artefatos, checks, riscos residuais e plano de rollback. Falha P0 resulta em `no-go`. Rollback usa tag anterior e migração reversível; nunca reescreve dados clínicos silenciosamente.
