# Fronteira de publicação FHIR

Status: decisão para o piloto técnico. Exportar não significa publicar.

## Modos

| Modo | Efeito | Consentimento | Destino externo |
| --- | --- | --- | --- |
| Visualização local | monta e valida o bundle em memória | não envia dados | não |
| Download autorizado | entrega o bundle à pessoa autenticada com acesso ao caso | ação explícita de download | não |
| Publicação externa | transmite ao FHIR Store configurado | ação explícita, consentimento registrado e aprovação institucional | sim |

`GET /api/v1/lesions/<case_id>/fhir` continua sendo apenas exportação local. Não há publicação automática após análise, salvamento ou geração de relatório.

## Pré-condições de publicação

`FHIRPublicationService` falha fechado sem `FHIRPublicationAuthorization` válido:

- pessoa autenticada e autorizada para o caso;
- ação explícita na interface;
- referência de consentimento com escopo `fhir_publication`;
- finalidade declarada;
- destino exatamente igual ao endpoint configurado;
- aprovação institucional do destino;
- referência do plano de rollback/compensação;
- bundle estruturalmente válido;
- chave de idempotência e hash calculados antes do envio.

Nenhuma credencial de destino pode vir do frontend, do bundle, de notas ou de outro conteúdo clínico.

## Idempotência, retry e falha parcial

- A chave combina destino, caso, avaliação e hash lógico do bundle.
- Repetir a mesma publicação concluída retorna `skipped`.
- Retries são limitados e aplicados somente pelo serviço de publicação.
- Uma resposta parcial, sem status por entrada ou com qualquer status fora de
  `2xx` falha fechada, entra no retry limitado e nunca grava estado `published`.
  Após esgotar as tentativas, o operador deve reconciliar o destino antes de
  repetir ou iniciar a compensação.
- Falha esgotada gera erro fechado; não substitui o destino e não converte publicação em download.

## Auditoria mínima

O ledger local guarda somente identificadores técnicos, hash, destino, número de tentativas, referência de consentimento, finalidade, referência de rollback e resumo técnico da resposta. Bundle, recurso `Patient`, prompt, token e detalhe bruto do erro externo não entram na auditoria.

O ledger atual é baseado em arquivo e serve ao desenvolvimento. Publicação institucional depende de ledger transacional com acesso controlado.

## Rollback e compensação

FHIR não oferece rollback universal para uma transação já aceita por outro sistema. Antes de habilitar um destino, a instituição deve escolher e testar uma destas estratégias:

1. transação compensatória versionada;
2. correção do recurso com `meta.versionId`/ETag;
3. exclusão lógica permitida pelo destino;
4. marcação de entrada em erro e reconciliação manual.

A referência registrada em `rollback_reference` aponta para o procedimento aprovado. O Heal+ não promete apagar dados do sistema receptor quando esse sistema não oferecer a operação.

## Responsabilidades

- Responsável de interoperabilidade: perfil, terminologia, destino e reconciliação.
- Responsável de privacidade: consentimento, finalidade, minimização e contrato com operador.
- Responsável clínico: revisão do conteúdo e impacto de correção.
- Pessoa operadora: confirma destino e ação, acompanha resultado e inicia compensação quando necessário.

## Evidência

`python -m pytest tests/test_fhir_publication.py tests/test_fhir_case_export_api.py -q`

Os testes cobrem idempotência, retry, resposta parcial, ausência de
consentimento, destino divergente, aprovação institucional e auditoria sem
payload clínico.
