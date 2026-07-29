# Pacote de evidências de release

Cada candidato a release deve possuir um manifesto JSON versionado nesta pasta.
Para uma tag `v0.2.0`, o arquivo esperado é `v0.2.0.json`.

O manifesto registra:

- commit avaliado;
- decisão `GO` ou `NO-GO`;
- aprovações clínica, de privacidade e de release;
- limitações identificáveis nas notas;
- alvo e procedimento de rollback;
- gates P0/P1/P2, estado e referências de evidência.

Validação estrutural de uma decisão, inclusive `NO-GO`:

```powershell
python scripts/validate_pilot_gate.py docs/operations/release-evidence/pilot-readiness-2026-07-27.json
```

Validação de uma candidata autorizada:

```powershell
python scripts/validate_pilot_gate.py `
  docs/operations/release-evidence/v0.2.0.json `
  --require-go `
  --expected-candidate v0.2.0 `
  --expected-release-notes docs/operations/releases/v0.2.0.md
```

Com `--require-go`, qualquer P0 diferente de `pass`, aprovação obrigatória
pendente ou limitação ausente das notas encerra o comando com falha. Evidência
local deve existir no repositório; evidência remota deve usar HTTPS.

O workflow `Pilot Gate` repete essa validação, executa o Artifact Guard e roda o
Secret Scan. O workflow `Release` só publica depois que esse gate reutilizável
termina com sucesso.
