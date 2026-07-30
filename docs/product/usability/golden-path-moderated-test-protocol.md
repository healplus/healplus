# Protocolo de teste moderado do golden path

## Finalidade e limite da evidência

Este protocolo avalia a compreensão, a navegabilidade e os riscos percebidos no
fluxo principal do Heal+ com dados exclusivamente sintéticos. O estudo não
avalia eficácia clínica, não autoriza uso assistencial e não substitui revisão
ética, institucional, de privacidade ou de segurança clínica.

O ensaio de mesa do material foi concluído em 2026-07-29. Sessões moderadas com
profissionais-alvo só podem começar depois que os bloqueios P0 de consentimento
e revisão humana estiverem encerrados, conforme as issues
[#53](https://github.com/healplus/healplus/issues/53) e
[#66](https://github.com/healplus/healplus/issues/66).

## Perguntas de pesquisa

1. A pessoa identifica o paciente, o caso e a avaliação em edição sem ajuda?
2. A sequência paciente, clínica, imagem, análise, revisão e histórico é
   compreensível?
3. A pessoa reconhece que uma saída de IA é sugestão e exige revisão
   profissional?
4. Erros, bloqueios e pedidos de consentimento deixam clara a próxima ação?
5. O fluxo pode ser concluído com teclado e tecnologia assistiva sem depender
   de cor, gesto ou animação?

## Participantes-alvo

- entre 5 e 8 profissionais de saúde;
- pelo menos 3 com experiência no registro ou acompanhamento de feridas;
- pelo menos 2 profissionais generalistas que não tenham participado do
  desenvolvimento do Heal+;
- diversidade de experiência digital, incluindo ao menos uma pessoa que use
  teclado como principal meio de navegação ou tecnologia assistiva, quando a
  participação for voluntária e institucionalmente autorizada.

Não registrar nome, telefone, e-mail, conselho profissional, matrícula,
instituição ou informação sobre pacientes. Cada sessão usa apenas um código
efêmero, de `P01` a `P08`, e uma faixa de experiência profissional.

## Pré-condições para iniciar sessões

- [ ] #53 encerrada com evidência de consentimento e minimização;
- [ ] #66 encerrada com revisão profissional obrigatória antes do salvamento;
- [ ] riscos conhecidos de #59 e #60 apresentados à moderação;
- [ ] responsável clínico e responsável de privacidade autorizam a sessão;
- [ ] ambiente isolado sem integração produtiva;
- [ ] conta, paciente, imagem e conteúdo clínico são sintéticos;
- [ ] gravação desativada, salvo aprovação institucional separada.

Se qualquer pré-condição falhar, a decisão é `NO-GO` para a sessão. O
facilitador registra somente o bloqueio e não improvisa um caminho alternativo.

## Consentimento de pesquisa

O facilitador lê o texto abaixo e registra apenas `aceitou: sim/não` associado
ao código da sessão:

> Estamos avaliando a facilidade de uso de um protótipo, não o seu desempenho
> profissional. O cenário e todos os dados são sintéticos. O Heal+ não será
> usado para diagnóstico ou atendimento. A participação é voluntária; você
> pode pular uma tarefa ou encerrar a sessão sem justificativa. Registraremos
> conclusão das tarefas, tempo, pedidos de ajuda, dificuldades e comentários
> sem seu nome ou registro profissional. Não informe dados de pacientes,
> credenciais ou segredos. Você concorda em participar nessas condições?

Consentimento para a pesquisa não equivale a consentimento para transmitir
dados a provedor de IA. Qualquer tarefa que envolva serviço externo precisa de
uma ação e um consentimento próprios, com destino, finalidade e campos exibidos.

## Ambiente e caso

- navegador moderno com zoom em 100%;
- opção de repetir a sessão com zoom em 200%;
- navegação por teclado disponível;
- leitor de tela quando fizer parte do perfil voluntário;
- conta local exclusiva da sessão;
- caso definido em
  [`golden-path-synthetic-case.md`](golden-path-synthetic-case.md);
- imagem `examples/synthetic_wound.jpg`;
- telemetria, analytics, gravação e integrações produtivas desativadas.

## Roteiro do moderador

1. Confirmar as pré-condições e ler o consentimento.
2. Explicar o método de pensar em voz alta sem ensinar a interface.
3. Entregar uma tarefa por vez, sem antecipar o caminho esperado.
4. Usar primeiro uma pergunta neutra: “O que você espera encontrar aqui?”.
5. Ajudar somente após 30 segundos sem progresso ou diante de risco.
6. Interromper a tarefa se houver tentativa de usar dado real, salvar saída de
   IA sem revisão, transmitir conteúdo sem consentimento ou operar no paciente
   errado.
7. Fazer o debrief e apagar os dados locais da sessão.

## Tarefas

### T1 — Entrar e localizar o caso

**Instrução:** entre no Heal+ e encontre a pessoa sintética indicada no cartão
do cenário.

**Sucesso:** identifica a conta ativa, abre `SYN-GP-001` e confirma que o caso é
sintético sem ajuda.

### T2 — Iniciar uma avaliação

**Instrução:** crie uma nova avaliação para o caso e confirme data e contexto.

**Sucesso:** seleciona o paciente correto, identifica a etapa atual e não cria
registro duplicado.

### T3 — Registrar o mínimo clínico

**Instrução:** registre somente os campos fornecidos no cartão do cenário.

**Sucesso:** preenche localização, etiologia declarada como sintética, dor,
exsudato, bordas e pele perilesional sem inventar informação.

### T4 — Adicionar imagem e revisar a região

**Instrução:** envie a imagem fornecida e localize os controles de região de
interesse, sem interpretar o conteúdo como evidência clínica.

**Sucesso:** usa somente a fixture sintética, entende a finalidade da região e
consegue continuar sem gesto exclusivo.

### T5 — Solicitar análise com segurança

**Instrução:** localize a análise e explique o que seria transmitido antes de
confirmar qualquer envio.

**Sucesso:** identifica destino, finalidade, campos mínimos e opção de cancelar.
Se #53 estiver aberta, a tarefa deve ser interrompida e marcada como bloqueada.

### T6 — Revisar, salvar e localizar no histórico

**Instrução:** revise a sugestão, corrija um campo conforme o cartão e salve a
avaliação; depois localize o resultado no histórico.

**Sucesso:** distingue sugestão de IA e registro profissional, realiza revisão
explícita, identifica a alteração e encontra o histórico. Se #66 estiver
aberta, a tarefa deve ser interrompida e marcada como bloqueada.

## Métricas por tarefa

- conclusão: `sem ajuda`, `com ajuda`, `falha` ou `bloqueada por segurança`;
- tempo em segundos, excluindo explicações do moderador;
- erros recuperáveis e erros críticos;
- número e momento dos pedidos de ajuda;
- confiança após a tarefa, de 1 a 5;
- comentário livre resumido sem transcrição identificável.

Um erro crítico inclui operar no caso errado, tentar usar dado real, transmitir
sem consentimento ou salvar saída automatizada sem revisão.

## Debrief

1. Em qual momento você teve menos certeza sobre a próxima ação?
2. O que indicou que a análise era apenas apoio à decisão?
3. O que você esperava revisar antes de salvar?
4. Houve mensagem, etapa ou controle difícil de perceber ou operar?
5. Que informação você removeria ou acrescentaria ao fluxo?

## Classificação dos achados

| Severidade | Critério |
|---|---|
| P0 | Pode causar exposição de dado, operação no caso errado, salvamento sem revisão ou interpretação clínica insegura. |
| P1 | Impede tarefa essencial, teclado/leitor de tela ou recuperação segura de erro. |
| P2 | Gera atraso, ajuda frequente ou ambiguidade sem risco imediato. |
| P3 | Ajuste de clareza ou consistência sem impacto relevante na conclusão. |

Cada achado recebe uma categoria primária `usabilidade` ou `segurança`, evidência
observável, responsável por função e uma issue para qualquer ação P0 ou P1.

## Critério de encerramento

O protocolo só pode registrar `sessões moderadas concluídas` quando:

- ao menos 5 participantes-alvo concluírem ou tentarem todas as tarefas;
- consentimento e descarte estiverem registrados sem identidade;
- métricas agregadas estiverem disponíveis;
- achados de usabilidade e segurança estiverem separados;
- toda ação P0/P1 possuir responsável e issue;
- limitações declararem que não houve validação de eficácia clínica.

