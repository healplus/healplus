# Processo de release

O Redisus deve usar versionamento semântico.

A política obrigatória de branches, checks, revisão, exceções e promoção está em
[`branch-policy.md`](branch-policy.md).

## Canais

- `v0.1.x`: governança, reprodutibilidade e demo técnica.
- `v0.2.x`: contratos de API, cobertura e smoke tests estáveis.
- `v0.3.x`: FHIR/RNDS, benchmark mínimo e model registry externo.
- `v1.0.0`: piloto técnico com limites clínicos documentados.

## Critérios mínimos

Antes de criar uma tag:

1. CI Python verde.
2. CI Web verde.
3. Artifact Guard verde.
4. CodeQL e Secret Scan sem achados críticos abertos.
5. `CHANGELOG.md` atualizado.
6. `ml/registry/models.yaml` sem apontar para artefatos versionados obrigatórios.
7. Limitações clínicas documentadas.
8. PR de promoção `develop -> main` aprovado conforme o risco.
9. Relatório de prontidão sem bloqueio P0.
10. Manifesto `docs/operations/release-evidence/<tag>.json` validado pelo
    workflow `Pilot Gate`.

## Como publicar

Antes da tag, valide localmente o pacote:

```powershell
python scripts/validate_pilot_gate.py `
  docs/operations/release-evidence/v0.2.0.json `
  --require-go `
  --expected-candidate v0.2.0 `
  --expected-release-notes docs/operations/releases/v0.2.0.md
```

Somente depois de uma decisão `GO` válida:

```powershell
git tag v0.2.0
git push origin v0.2.0
```

O workflow `Release` chama o `Pilot Gate`, que valida a evidência versionada,
repete o Artifact Guard e o Secret Scan, e só então publica
`docs/operations/releases/<tag>.md`. O mantenedor deve revisar notas, riscos
conhecidos e artefatos antes de criar e enviar a tag.

## Rollback

Como o projeto ainda está antes de `v1.0.0`, mudanças incompatíveis podem ocorrer em `0.x`, mas devem estar explícitas no changelog. Em piloto, rollback deve ser operacional: voltar para a tag anterior e preservar dados de avaliação em backup seguro.
