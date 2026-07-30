# Evidências de usabilidade

Este diretório concentra o pacote versionado para o teste moderado do golden
path. Ele usa somente dados sintéticos e não representa autorização para uso
assistencial, pesquisa com dados reais ou alegação de eficácia clínica.

## Artefatos

- [Protocolo, consentimento, participantes e tarefas](golden-path-moderated-test-protocol.md)
- [Caso e imagem sintéticos](golden-path-synthetic-case.md)
- [Ensaio piloto e revisão de acessibilidade](golden-path-pilot-rehearsal-2026-07-29.md)
- [Backlog priorizado](golden-path-action-backlog.md)
- [Evidência legível por máquina](evidence/golden-path-pilot-rehearsal-2026-07-29.json)

## Validação

```powershell
python scripts/validate_usability_evidence.py `
  docs/product/usability/evidence/golden-path-pilot-rehearsal-2026-07-29.json

python -m pytest tests/test_usability_evidence.py -q
```

O status `pilot-rehearsal-complete` significa que o material foi ensaiado sem
participantes. O status `moderated-sessions-complete` só é aceito pelo validador
quando o número mínimo de sessões ao vivo estiver registrado.

