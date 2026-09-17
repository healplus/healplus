# Backlog do teste de usabilidade do golden path

## Regras

- P0 impede a sessão e o piloto.
- P1 impede a tarefa afetada ou a participação acessível.
- Nenhuma ação P0/P1 pode ficar apenas neste documento; ela precisa de issue e
  responsável por função.
- O fechamento técnico não autoriza uso clínico ou dados reais.

## Ações abertas

| Prioridade | Achado | Issue | Responsável por função | Evidência para encerrar |
|---|---|---|---|---|
| P0 | Consentimento, destino e minimização antes de provedor externo | [#53](https://github.com/healplus/healplus/issues/53) | privacidade e frontend | teste de negação, cancelamento, troca de provedor e payload mínimo |
| P0 | Revisão profissional obrigatória antes do salvamento | [#66](https://github.com/healplus/healplus/issues/66) | produto clínico e frontend | E2E com origem IA, alteração/rejeição e histórico |
| P1 | Stepper, foco em erro, teclado, leitor de tela e movimento reduzido | [#59](https://github.com/healplus/healplus/issues/59) | acessibilidade e frontend | teste por teclado, leitor de tela, axe e redução de movimento |
| P1 | Estados de loading, vazio, erro, consentimento e retry | [#60](https://github.com/healplus/healplus/issues/60) | frontend | latência, timeout, duplo clique, retry e anúncio por leitor de tela |

## Ações concluídas neste pacote

| Prioridade | Ação | Evidência |
|---|---|---|
| P2 | Definir participantes-alvo e minimização dos registros | `golden-path-moderated-test-protocol.md` |
| P2 | Versionar caso único com campos e imagem sintéticos | `golden-path-synthetic-case.md` |
| P2 | Ensaiar consentimento, tarefas, métricas e condições de parada | `golden-path-pilot-rehearsal-2026-07-29.md` |
| P2 | Separar achados de usabilidade e segurança | relatório e evidência JSON versionada |
| P2 | Revisar acessibilidade do material de pesquisa | checklist do relatório de ensaio |

## Próxima execução

Após os P0:

1. obter aprovação clínica e de privacidade;
2. executar de 5 a 8 sessões;
3. registrar apenas métricas agregadas;
4. criar issues para novos P0/P1 antes de qualquer recomendação de piloto;
5. publicar relatório final distinguindo usabilidade, segurança e limitações.

