# Changelog

Todas as mudanças relevantes deste repositório devem ser registradas aqui.

O formato segue a ideia de *Keep a Changelog* e versionamento semântico quando aplicável.

## [Unreleased]

### Added

- fila de PRs para governanca, seguranca, CI, testes, dados, entrypoints, cobertura e release alpha;
- notas versionadas para `v0.1.0-alpha`.
- perfis oficiais e separados para API, web, desktop e ML, com contrato
  verificável em `runtime-profiles.toml`;
- gate de piloto versionado, com bloqueio de P0, aprovações obrigatórias,
  limitações nas notas, rollback, Artifact Guard e Secret Scan.

## [0.1.0-alpha] - 2026-04-24

### Added

- nova estrutura documental em `docs/`;
- roadmap executivo do módulo de diagnóstico;
- dataset card, model card e baseline report;
- política inicial de segurança e LGPD;
- templates de issue e workflows do GitHub.

### Changed

- README principal reescrito para onboarding técnico;
- arquivos legados e logs históricos movidos para `artifacts/`;
- documentação de arquitetura antiga preservada como legado;
- scripts de treino ajustados para gravar logs em `artifacts/logs/`.

### Notes

- a base ainda está em consolidação e não deve ser tratada como produto clínico final.
