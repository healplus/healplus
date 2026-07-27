## O que mudou

Descreva de forma curta o problema e a solução aplicada.

## Evidências

- [ ] testes executados
- [ ] typecheck/lint e build executados quando há mudança no frontend
- [ ] jornadas negativas afetadas foram executadas
- [ ] screenshots anexados quando aplicável
- [ ] docs atualizadas
- [ ] não foram adicionados datasets, checkpoints, bancos locais, runs ou artefatos gerados

Informe comandos, versões e links para os checks. Não anexe logs com dados clínicos ou segredos.

## Segurança

- [ ] Você validou tudo no backend?
- [ ] Este endpoint depende de algum dado do frontend para auth/authz?
- [ ] Há ownership check de recurso?
- [ ] Campos inesperados são rejeitados?
- [ ] Upload foi validado no backend?
- [ ] Há teste negativo de bypass/IDOR?
- [ ] Não há dados clínicos reais, identificáveis ou sensíveis no PR?
- [ ] Logs/auditoria usam somente metadata allowlisted e `request_id`?
- [ ] Credenciais BYOK permanecem em memória/sessionStorage e somem na troca de usuário?
- [ ] Integrações externas exigem ação e consentimento explícitos?

## Dados e modelos

- [ ] Se o PR altera ML, `ml/registry/models.yaml` e model cards foram atualizados.
- [ ] Se o PR altera datasets, o dataset card/manifest foi atualizado.
- [ ] Artefatos binários estão em storage externo ou cache local ignorado pelo Git.

## Riscos

Liste impactos, limitações ou pontos que ainda exigem acompanhamento.

- Classificação: `P0`, `P1`, `P2` ou `P3`
- Responsável funcional:
- Risco residual:
- Rollback/compensação:
- Decisão: `go`, `no-go` ou `go técnico condicionado`
