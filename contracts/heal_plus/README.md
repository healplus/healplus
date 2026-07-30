# Contratos lógicos do Heal+

Os schemas deste diretório documentam a fronteira mostrada no diagrama do
cluster:

| Fluxo lógico | Contrato | Estado |
|---|---|---|
| Integration Service → tópico de entrada → Heal+ | `fhir-message-envelope.schema.json` com direção `cluster-to-heal-plus` | schema versionado; transporte não implementado |
| Heal+ → tópico de saída → Integration Service | `fhir-message-envelope.schema.json` com direção `heal-plus-to-cluster` | schema versionado; transporte não implementado |
| Takere referencia uma imagem sob custódia do Heal+ | `takere-image-reference.schema.json` | schema versionado; endpoint/autenticação pendentes |
| Resultado técnico de validação de imagem | `image-validation-result.schema.json` | schema versionado; não é diagnóstico |

## Regras obrigatórias

- bundles clínicos são dados pessoais sensíveis e nunca devem ser persistidos em
  logs, filas de erro sem proteção ou fixtures do repositório;
- `message_id`, `correlation_id` e hashes são identificadores técnicos, não
  identificadores de paciente;
- o Heal+ não recebe certificado da RNDS e não chama a API RNDS diretamente;
- nomes de tópicos, broker, autenticação, retry e dead-letter queue dependem de
  definição do cluster e não são inventados neste repositório;
- referências de imagem não carregam URL assinada, token, prontuário ou conteúdo
  binário;
- validação de imagem informa qualidade técnica e nunca produz diagnóstico ou
  conduta clínica autônoma.
