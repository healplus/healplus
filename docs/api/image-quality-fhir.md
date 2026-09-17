# API de qualidade técnica de imagens — FHIR R4

Esta API implementa uma operação **experimental** para triagem técnica de fotografias,
com processamento determinístico em CPU. Não usa IA generativa, não corrige pixels e
não produz diagnóstico, classificação de tecidos ou prescrição. Os limites abaixo
são hipóteses de engenharia versionadas; **a validação externa pela RUTE ainda não
foi realizada**. `accepted` não significa imagem clinicamente adequada.

## Execução e autenticação

Na `main`, a aplicação oficial está em `apps/api`:

```powershell
python -m pip install -r requirements-ci.txt
python -m pip install 'firebase-admin>=6.0.0'
$env:CLINICAL_API_REQUIRE_AUTH = '1'
$env:FLASK_ENV = 'production'
$env:FIREBASE_SERVICE_ACCOUNT_FILE = 'C:/secrets/firebase-service-account.json'
python -m apps.api.app
```

Para testes locais use somente imagens sintéticas. Em servidor, use um servidor
WSGI de produção atrás de gateway HTTPS, desative debug e configure timeout,
limite de corpo e rate limit global no gateway. A configuração Firebase é a mesma
da API clínica existente; a credencial de serviço permanece exclusivamente no
servidor. O consumidor envia um **ID token Firebase** em `Authorization: Bearer`.
Tokens expirados/revogados são rejeitados; a verificação Firebase inclui revogação.
Adaptadores injetados por `REDISUS_AUTH_VERIFIER` devem cumprir a mesma garantia.
Papéis permitidos são os de escrita clínica já definidos em
`packages/shared/security.py`; pacientes e pesquisadores não têm acesso.

O endpoint falha fechado se a autenticação estiver ausente ou se
`CLINICAL_API_REQUIRE_AUTH=0`. Essa variável não permite acesso anônimo à nova API.
O serviço não consulta imagens armazenadas de outros usuários nem aceita um
identificador de paciente; o chamador deve estar autorizado a fornecer a imagem.

## Endpoints

Todos usam `/api/v1/fhir`, com autenticação e autorização:

| Método e caminho | Resultado |
|---|---|
| `POST /$validate-image` | `Parameters` com decisão, métricas, motivos e limites |
| `GET /metadata` | `CapabilityStatement`, FHIR `4.0.1` |
| `GET /OperationDefinition/validate-image` | Contrato computável da operação |

Use `Content-Type: application/fhir+json` e `Accept: application/fhir+json`.
XML, multipart, query strings, URLs de imagens e parâmetros desconhecidos não são
aceitos. É uma operação customizada do Heal+, não uma operação padrão HL7 nem o
`$validate` de validação estrutural de recursos FHIR. Os identificadores canônicos
`https://healplus.local/fhir/...` são namespaces lógicos locais, não URLs de produção.
Não implementa armazenamento FHIR, broker do cluster, Takere ou envio RNDS.

Corpo da requisição (substitua `BASE64_DA_IMAGEM`):

```json
{
  "resourceType": "Parameters",
  "parameter": [
    {"name": "imageId", "valueString": "capture-synthetic-001"},
    {"name": "consent", "valueBoolean": true},
    {"name": "image", "valueAttachment": {
      "contentType": "image/jpeg",
      "data": "BASE64_DA_IMAGEM"
    }}
  ]
}
```

`imageId` é uma correlação técnica opaca (`[A-Za-z0-9._:-]{8,128}`), nunca nome,
prontuário ou CPF. `consent=true` confirma a ação e o consentimento para este
processamento; não é substituto de um registro institucional de consentimento.
Sem essa confirmação a imagem não é decodificada. Não são aceitos campos extras,
parâmetros repetidos, chaves JSON duplicadas ou coerção de tipos como `"true"`.

## Resposta e interpretação

Uma avaliação concluída retorna **HTTP 200**, mesmo se a imagem for rejeitada:

- `status=accepted`: nenhuma regra técnica sinalizou problema;
- `status=rejected`: pelo menos uma regra de bloqueio sinalizou problema;
- `status=indeterminate`: somente alertas, exigindo revisão/repetição da captura.

`Parameters.parameter` inclui `contractVersion=1.0`, `requestId` (UUID criado pelo
servidor), `imageId`, `status`, `algorithmVersion=healplus-iqa-1.0.0`,
`validationStage=experimental`, `limitation` e `measurement` (recurso `Observation`).
`reason` é repetível e contém partes `code`, `severity` e `message` em português.
`threshold` contém partes `name` e `value`, explicitando os limites aplicados.
O `Observation.status=final` significa que a medição foi concluída, não que foi
homologada clinicamente. Não tem `id` persistente, referência a paciente ou imagem.
Os códigos pertencem ao namespace local `https://healplus.local/fhir/CodeSystem/image-quality`;
não são apresentados como códigos LOINC/SNOMED ou terminologia clínica validada.

O resultado lógico preserva os campos do contrato técnico 1.0 existente na
`develop`: `contract_version`, `request_id`, `image_id`, `status`, `reasons`.
No transporte FHIR eles correspondem a `contractVersion`, `requestId` (remova o
prefixo `urn:uuid:` se precisar do UUID simples), `imageId`, `status` e às mensagens
de cada `reason`. O HTTP não retorna o envelope de mensageria do cluster.

### Métricas e regras da versão 1.0.0

A orientação EXIF é aplicada; o conteúdo é convertido para RGB de 8 bits sem
reter EXIF. Não há realce, correção de cor ou salvamento de imagem. Reduzimos
proporcionalmente o maior lado para no máximo 1024 pixels, sem ampliar, antes
das métricas. Resolução usa as dimensões originais já orientadas.

| Métrica | Unidade / cálculo | Regra |
|---|---|---|
| `width`, `height` | Pixels após orientação | Menor lado <480 ou maior <640 rejeita |
| `analysis-width`, `analysis-height` | Pixels efetivamente analisados | Maior lado ≤1024 |
| `sharpness` | Variância do Laplaciano após Gaussiano 3×3, σ=0,5 | <45 rejeita; [45,90) alerta |
| `brightness` | Média de luminância OpenCV RGB→cinza, escala 0–255 | <35 ou >220 rejeita |
| `dark-fraction` | Fração de pixels com luminância ≤15 | >0,35 rejeita |
| `bright-fraction` | Fração de pixels com luminância ≥245 | >0,20 rejeita |
| `contrast` | Percentil 95 − percentil 5 de luminância | <25 rejeita |
| `glare-fraction` | Fração HSV com V≥245 e S≤30 | >0,05 alerta de possível reflexo |
| `lighting-spread` | Diferença entre maior/menor média em grade 3×3, dividida por 255 | >0,35 alerta |
| `noise` | Mediana do resíduo absoluto ao filtro mediano 3×3, nos 50% de pixels com menor gradiente Sobel | >12 alerta |

Fotografias monocromáticas geram alerta. Métricas são medidas na imagem inteira:
fundo, texturas e bordas podem influenciar os resultados. Ruído pode simular foco;
áreas naturalmente claras podem simular reflexos; diferenças de cor podem simular
iluminação desigual. Redimensionamento afeta ruído/foco. Não há detecção de ferida,
ROI automática, garantia de fidelidade de cor, distância ou escala física.

### Erros e limites

Erros retornam `OperationOutcome` em `application/fhir+json`, incluindo falhas
de autenticação, autorização e método HTTP. Não incluem corpo, token, base64,
EXIF, traceback ou mensagem interna do provedor. Cabeçalhos incluem `no-store`,
`nosniff` e UUID de correlação; `429` traz `Retry-After` e `401`, `WWW-Authenticate`.

| HTTP | Significado |
|---|---|
| 400 | JSON, parâmetros ou base64 inválidos |
| 401 / 403 | Token ausente/inválido ou papel/consentimento insuficiente |
| 404 / 405 / 406 | Caminho, método ou formato de resposta não suportado |
| 413 | Corpo >14 MiB, imagem >10 MiB ou >12 megapixels |
| 415 | Tipo HTTP/imagem incompatível, animação ou modo de cor não suportado |
| 422 | Arquivo corrompido, transparência ou dimensão <16 pixels |
| 429 | Limite de frequência ou capacidade simultânea |
| 500 / 503 | Erro de processamento seguro ou autenticação indisponível/desabilitada |

Aceita somente JPEG e PNG estáticos e íntegros. As dimensões são verificadas
**antes** da descompressão completa. Até duas operações de qualidade por processo;
30 requisições/minuto por usuário por padrão. Configurações existentes:
`REDISUS_RATE_LIMIT_IMAGE_QUALITY` e `REDISUS_RATE_LIMIT_WINDOW_SECONDS`.
Os limites locais não são distribuídos entre workers; use o gateway para limitar
globalmente. Uploads e resultados não são persistidos pela operação nem enviados
a serviços externos. Autenticação pode consultar o provedor Firebase.
Desative captura de corpos/Authorization no proxy, APM e rastreamento HTTP.

## Validação e preparação para a RUTE

```powershell
python -m pytest tests/test_image_quality.py -q
python scripts/check_image_quality_fhir.py
```

O segundo comando baixa exclusivamente o schema público oficial HL7 R4 4.0.1,
confere seu SHA-256 fixado e valida recursos sintéticos localmente. Não envia
imagens. Isso cobre estrutura JSON; não equivale a homologação de perfis,
terminologias ou precisão clínica. O CI executa ambos junto às regressões da API.

Antes de uso clínico, a RUTE deve avaliar um conjunto autorizado e representativo
de câmeras, resoluções, tons de pele e condições de captura, com revisores
independentes e registro da versão. Comparar repetição necessária, falsos aceites,
falsas rejeições e indeterminados, estratificar por condições de captura, definir
critérios institucionais de aceitação e recalibrar limites em conjunto separado.
Versionar qualquer mudança dos limites. Não versionar fotografias clínicas no Git.

Publicar código na `main` não provisiona um servidor. A unidade de testes precisa
receber uma URL HTTPS real, identidades/papéis autorizados, limites no gateway e
o contrato da operação. Broker, credenciais e aprovação da RUTE não são inferidos.

Referências: [operações FHIR R4](https://hl7.org/fhir/R4/operations.html),
[Parameters](https://hl7.org/fhir/R4/parameters.html),
[OperationDefinition](https://hl7.org/fhir/R4/operationdefinition.html),
[Observation](https://hl7.org/fhir/R4/observation.html),
[Pillow Image](https://pillow.readthedocs.io/en/stable/reference/Image.html) e
[Laplaciano OpenCV](https://docs.opencv.org/4.x/d5/db5/tutorial_laplace_operator.html).
