# Critérios de release piloto

O piloto não deve ser tratado como liberação assistencial irrestrita. Ele é uma etapa técnica supervisionada.

## v0.1.0-alpha

- Repositório sem datasets, checkpoints, runs e bancos versionados.
- README alinhado com arquitetura real.
- `SECURITY.md`, `CODEOWNERS`, templates e branch protection documentados.
- CI Python, CI Web, CodeQL, Secret Scan e Artifact Guard ativos.
- Documentação de setup, testes, releases e política de artefatos.
- Changelog e notas em `docs/operations/releases/v0.1.0-alpha.md`.
- Aviso claro de que o release nao e liberacao assistencial.

## v0.2.0

- OpenAPI inicial publicado.
- Testes de contrato para rotas clínicas principais.
- Cobertura mínima global de 60% no recorte crítico.
- DB temporário em testes.
- Frontend validado contra contrato da API.

## v0.3.0

- FHIR R4 com validação estrutural dos bundles principais.
- Model registry com URIs externas e checksums.
- Dataset cards e manifests completos.
- Benchmark mínimo reproduzível para inferência e pipeline de imagem.

## Piloto técnico

- Fluxo paciente-lesão-imagem-avaliação-plano testado ponta a ponta.
- Limitações clínicas explícitas na interface e na documentação.
- Revisão humana obrigatória para qualquer saída de IA.
- Política LGPD revisada por responsável institucional.
- Plano de incidentes e rollback documentado.

## Gate versionado

Cada candidata deve possuir
`docs/operations/release-evidence/<tag>.json`, conforme
[`docs/operations/release-evidence/README.md`](../operations/release-evidence/README.md).
O manifesto liga cada gate à sua evidência, registra limitações, rollback,
aprovações obrigatórias e a decisão `GO` ou `NO-GO`.

```powershell
python scripts/validate_pilot_gate.py `
  docs/operations/release-evidence/<tag>.json `
  --require-go `
  --expected-candidate <tag> `
  --expected-release-notes docs/operations/releases/<tag>.md
```

Uma candidata não pode ser publicada quando:

- algum P0 não estiver em `pass`;
- as aprovações clínica, de privacidade ou de release estiverem pendentes;
- uma limitação não aparecer nas notas pelo mesmo identificador;
- o Artifact Guard ou o Secret Scan falhar;
- não houver procedimento e alvo explícitos de rollback.

## Decisão vigente

O relatório de 2026-07-27 autoriza somente desenvolvimento e validação interna
com dados sintéticos. Piloto com dados reais e uso assistencial permanecem
NO-GO enquanto houver bloqueio P0:
[`pilot-readiness-report-2026-07-27.md`](pilot-readiness-report-2026-07-27.md).
O registro legível por máquina da mesma decisão está em
[`pilot-readiness-2026-07-27.json`](../operations/release-evidence/pilot-readiness-2026-07-27.json).
