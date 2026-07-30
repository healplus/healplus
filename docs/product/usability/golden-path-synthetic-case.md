# Caso sintético do golden path

## Regras de uso

Este cartão é uma fixture de demonstração. Não representa uma pessoa, um
prontuário ou uma recomendação clínica. Não substituir nenhum valor por dado
real e não usar a saída para diagnóstico, prescrição ou conduta.

## Identidade sintética

| Campo | Valor |
|---|---|
| Código do caso | `SYN-GP-001` |
| Nome exibido | `Pessoa Sintética Alfa` |
| Data de nascimento | `1980-01-01` — valor fictício |
| Telefone | `00000000` |
| E-mail | `synthetic-patient-a@healplus.invalid` |
| Observação | `Fixture sintética para teste de usabilidade; sem valor clínico.` |

## Avaliação sintética

| Campo | Valor |
|---|---|
| Localização | `Perna Esquerda` |
| Etiologia | `Outra` |
| Dor | `2/10` |
| Exsudato | `Pequeno` e `Seroso` |
| Bordas | `Regulares` |
| Pele perilesional | `Íntegra` |
| Sinais de infecção | nenhum |
| Observação | `Conteúdo criado somente para exercitar o fluxo.` |
| Imagem | `examples/synthetic_wound.jpg` |

Os valores não devem ser interpretados em conjunto como caso clínico plausível.
Eles existem somente para preencher os controles obrigatórios.

## Correção solicitada na revisão

Na tarefa T6, alterar a observação para:

> Revisado no ensaio sintético; nenhum dado clínico real foi utilizado.

O teste deve verificar se a origem automatizada, a revisão profissional e a
alteração ficam distinguíveis antes do salvamento e no histórico.

## Dados proibidos

- nome, contato, matrícula ou conselho profissional reais;
- imagem, prontuário, nota ou identificador de paciente;
- chave de API, token, prompt completo ou endpoint confidencial;
- gravação, transcrição integral ou captura que exponha outra conta.

