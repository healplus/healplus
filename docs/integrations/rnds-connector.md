# Conector RNDS em Python

## Escopo

O repositório contém um adaptador server-side para o contrato HTTP/FHIR da Rede
Nacional de Dados em Saúde (RNDS). Ele foi inspirado na separação de
responsabilidades do projeto
[`wolleyws/rnds-connector`](https://github.com/wolleyws/rnds-connector), sem
copiar sua implementação Java:

- o modelo clínico e o transporte FHIR permanecem separados;
- autenticação, submissão e resposta ficam em um adaptador de saída;
- identificadores são estáveis;
- falhas, tentativas e protocolo retornado têm tratamento explícito.

O código está em
`src/interoperability/fhir_r4/adapters/rnds/` e usa a linguagem atual do backend,
Python 3.11+, com `requests`.

## Estado de prontidão

O adaptador está implementado e coberto por testes com respostas sintéticas. Ele
não foi homologado com credenciais reais da RNDS neste repositório e não está
ligado automaticamente à API ou ao frontend do Heal+.

Antes de qualquer uso com dados clínicos, a instituição precisa:

1. concluir credenciamento e obter o identificador do solicitante;
2. obter acesso ao ambiente de homologação;
3. confirmar com o DATASUS o perfil computacional aceito para o documento;
4. validar o Bundle contra os artefatos nacionais aplicáveis;
5. aprovar finalidade, consentimento, profissional solicitante e procedimento de
   reconciliação;
6. homologar a integração antes de habilitar produção.

Referências oficiais:

- [ambientes e endereços RNDS](https://rnds-guia.saude.gov.br/docs/rnds/ambientes/);
- [serviços RNDS](https://rnds-guia.saude.gov.br/docs/rnds/servicos/);
- [roteiro, certificado e headers de segurança](https://rnds-guia.saude.gov.br/docs/publico-alvo/ti/conhecer/);
- [homologação e identificador retornado](https://rnds-guia.saude.gov.br/docs/publico-alvo/ti/homologar/);
- [modelo de informação do RAC](https://rnds-guia.saude.gov.br/docs/rac/mi-rac/).

## Fronteira com o Heal+

O módulo `apps/heal_plus/` não recebe o certificado, não monta headers RNDS e não
chama a RNDS após upload, análise ou salvamento. Na arquitetura do cluster, a
instanciação deste adaptador pertence ao Integration Service/RNDS Dispatcher.

O Bundle genérico exportado atualmente pelo Heal+ usa `collection` ou
`transaction`; ele **não é um documento RNDS** e é rejeitado pelo adaptador. A
submissão exige:

- `Bundle.type=document`;
- `Bundle.identifier.system` vinculado ao identificador do solicitante;
- `Composition` como primeira entrada;
- `Composition.status=final`;
- perfil documental incluído na allowlist aprovada pela instituição.

Essa checagem não substitui validação completa contra o Implementation Guide e
as terminologias da versão homologada.

## Autenticação e transporte

O fluxo segue o contrato documentado pela RNDS:

1. `GET /api/token` no host Auth, usando certificado de cliente;
2. cache somente em memória durante a validade retornada;
3. envio ao EHR com `X-Authorization-Server: Bearer <token>`;
4. identificação do profissional por CNS ou CPF no header `Authorization`;
5. `POST /api/fhir/r4/Bundle` com `application/fhir+json`;
6. captura do identificador RNDS em `Location` ou `Content-Location`.

O certificado de cliente é enviado somente ao host Auth. O adaptador usa TLS
verificado e não permite trocar hosts RNDS por configuração de ambiente.

O guia oficial normalmente entrega certificado A1 em PKCS#12/PFX. O processo de
deploy deve expor o certificado e a chave como dois arquivos PEM absolutos,
montados por secret manager em volume efêmero e legíveis somente pelo processo.
Conversão, senha e chave privada não pertencem ao repositório, imagem de
container, variáveis `VITE_*`, logs ou histórico do terminal.

## Configuração

Todas as variáveis são exclusivas do backend/serviço de integração:

| Variável | Obrigatória | Uso |
|---|---:|---|
| `REDISUS_RNDS_ENVIRONMENT` | não | `homologation` por padrão ou `production` |
| `REDISUS_RNDS_REQUESTER_ID` | sim | identificador fornecido no credenciamento |
| `REDISUS_RNDS_CERTIFICATE_PEM_PATH` | sim | caminho absoluto do certificado público |
| `REDISUS_RNDS_PRIVATE_KEY_PEM_PATH` | sim | caminho absoluto da chave privada montada |
| `REDISUS_RNDS_DOCUMENT_PROFILES` | sim | URLs canônicas aprovadas, separadas por vírgula |
| `REDISUS_RNDS_CA_BUNDLE_PATH` | não | CA bundle adicional; TLS nunca é desabilitado |
| `REDISUS_RNDS_TIMEOUT_SECONDS` | não | entre 1 e 60; padrão 30 |
| `REDISUS_RNDS_STATE` | produção | UF usada para selecionar o EHR estadual |
| `REDISUS_RNDS_PRODUCTION_APPROVED` | produção | precisa ser `true` após homologação institucional |

Homologação usa os hosts nacionais oficiais. Produção exige simultaneamente UF e
aprovação explícita; sem ambos a configuração falha fechada.

O CNS/CPF não vem de variável global. Ele deve ser obtido do contexto
autenticado e autorizado e usado para criar uma instância curta do adaptador:

```python
from src.interoperability.fhir_r4 import (
    FHIRPublicationAuthorization,
    FHIRPublicationService,
    RNDSFHIRAdapter,
)

adapter = RNDSFHIRAdapter.from_environment(
    professional_cns_or_cpf=verified_professional_identifier,
)
publisher = FHIRPublicationService(adapter)
authorization = FHIRPublicationAuthorization(
    actor_id=authenticated_actor_id,
    consent_reference=consent_record_id,
    consent_scope="fhir_publication",
    destination=adapter.destination,
    purpose="care_coordination",
    rollback_reference=reconciliation_runbook_id,
    user_action_confirmed=True,
    institution_approved=True,
)
result = publisher.publish_bundle(
    validated_rnds_document_bundle,
    publication_key=stable_local_document_id,
    authorization=authorization,
)
```

O exemplo contém nomes de variáveis, não credenciais ou identificadores reais.

## Retry, idempotência e reconciliação

- O token é renovado uma vez quando o EHR responde `401`.
- Falha para obter token pode ser repetida, pois nenhum Bundle foi enviado.
- Timeout ou quebra de conexão durante `POST` produz estado desconhecido e **não
  é repetido automaticamente**.
- HTTP `422`, inclusive identificador já utilizado, exige consulta/reconciliação
  operacional antes de novo envio.
- O identificador local do Bundle e a chave de publicação devem permanecer
  estáveis.
- Resposta `201` sem `Location` válido também exige reconciliação.

Logs de auditoria guardam hash, contagem, destino e resumo de status. Eles não
guardam token, certificado, chave, CNS/CPF, Bundle, `OperationOutcome.diagnostics`
ou texto clínico.

## Validação local

```powershell
python -m pytest tests/test_rnds_connector.py tests/test_fhir_publication.py -q
```

Os testes cobrem homologação/produção, cache de token, mTLS no Auth, headers do
EHR, renovação após `401`, allowlist de perfil, sanitização de erros e bloqueio de
retry quando o resultado da submissão é ambíguo.
