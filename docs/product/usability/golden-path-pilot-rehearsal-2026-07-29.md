# Ensaio piloto do teste moderado — 2026-07-29

## Resultado

**Aprovado com bloqueios para uso como roteiro; NO-GO para sessões moderadas
com profissionais-alvo neste estado.**

Foi realizado um ensaio de mesa do protocolo, das tarefas, do caso sintético,
das métricas e das condições de interrupção. Não houve participante externo,
gravação, dado real nem alegação de eficácia. Portanto, este documento valida o
material de pesquisa, não a usabilidade do produto.

## Escopo executado

- leitura sequencial do consentimento e das seis tarefas;
- conferência dos campos com o formulário atual;
- conferência da fixture `examples/synthetic_wound.jpg`;
- revisão de riscos já registrados nas issues dependentes;
- revisão de acessibilidade do material em Markdown;
- validação automatizada da evidência versionada.

## Resultado por tarefa

| Tarefa | Ensaio do roteiro | Condição para sessão |
|---|---|---|
| T1 — entrar e localizar | instrução e sucesso são observáveis | usar conta e caso exclusivos |
| T2 — iniciar avaliação | campos existem no fluxo atual | anunciar etapa e erros conforme #59 |
| T3 — registrar mínimo | valores correspondem às opções do formulário | não permitir dado inventado ou real |
| T4 — imagem e região | fixture sintética existe no repositório | oferecer caminho sem gesto exclusivo |
| T5 — análise segura | condição de interrupção está definida | bloqueada enquanto #53 estiver aberta |
| T6 — revisar e salvar | correção sintética está definida | bloqueada enquanto #66 estiver aberta |

Tempos, taxa de conclusão, erros e confiança aparecem como `não medidos`, pois
fabricar métricas sem participantes seria evidência enganosa.

## Achados de segurança

| ID | Severidade | Achado | Ação registrada |
|---|---|---|---|
| `SAF-01` | P0 | O golden path ainda não comprova revisão profissional obrigatória antes do salvamento. | [#66](https://github.com/healplus/healplus/issues/66), responsável clínico/produto |
| `SAF-02` | P0 | Consentimento, destino e minimização ainda não estão comprovados em todos os fluxos com provedor externo. | [#53](https://github.com/healplus/healplus/issues/53), responsável de privacidade/frontend |

## Achados de usabilidade

| ID | Severidade | Achado | Ação registrada |
|---|---|---|---|
| `USA-01` | P1 | O stepper atual apresenta estado principalmente por estilo visual e não anuncia etapa atual/concluída; o avanço inválido também não direciona foco ao erro. | [#59](https://github.com/healplus/healplus/issues/59), responsável de acessibilidade/frontend |
| `USA-02` | P1 | Loading, vazio, erro, consentimento e retry ainda não têm evidência uniforme no fluxo completo. | [#60](https://github.com/healplus/healplus/issues/60), responsável de frontend |
| `USA-03` | P1 | A assinatura desenhada em canvas não oferece alternativa operável por teclado no formulário atual. | [#59](https://github.com/healplus/healplus/issues/59), responsável de acessibilidade/frontend |
| `USA-04` | P2 | O roteiro de demonstração não possuía um caso sintético único e reproduzível. | Resolvido por `golden-path-synthetic-case.md` |

Os achados não são observações de participantes. Eles vieram da inspeção do
roteiro e da interface atual e servem para impedir que o estudo comece ocultando
riscos conhecidos.

## Revisão de acessibilidade do material

- [x] hierarquia de títulos é sequencial;
- [x] tarefas usam instrução, sucesso e condição de parada explícitos;
- [x] severidade não depende apenas de cor;
- [x] links têm texto identificável;
- [x] abreviações e escalas são explicadas;
- [x] o moderador possui instruções para teclado e leitor de tela;
- [x] o consentimento está em linguagem direta e pode ser lido em voz alta;
- [x] nenhuma animação ou interação é necessária para consumir o material.

Esta revisão cobre os documentos do estudo, não certifica a acessibilidade da
aplicação. A validação da interface permanece em #59 e #60.

## Decisão e próximo gate

O pacote está pronto para revisão clínica e de privacidade. Sessões moderadas
permanecem `NO-GO` até o encerramento de #53 e #66. Depois disso, a execução
deve usar de 5 a 8 profissionais-alvo e substituir este ensaio por um relatório
agregado, sem identidade, transcrição integral ou dado clínico.

