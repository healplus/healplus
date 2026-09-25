# Recepção FHIR e fila de análise do Heal+

A API FastAPI recebe imagens, completa o contexto do paciente, valida o FHIR
R4 e a qualidade técnica, persiste os originais e coloca o lote na fila local
do Heal+. O processamento clínico ocorre em um processo worker separado.
O retorno `202` só ocorre depois do commit da transação que grava imagens,
metadados e tarefa. Não significa que a análise já terminou.

## Endpoints

| Método e caminho | Comportamento |
|---|---|
| `POST /api/v1/analyses` | Recebe `Media`, `Bundle collection` ou `Task` com imagens contidas; retorna `202` e `analysisId` |
| `GET /api/v1/analyses/{analysisId}` | Status, histórico de transições, qualidade e recurso FHIR `Task` |
| `GET /api/v1/analyses/{analysisId}/result` | Resultado do motor Heal+; `202` enquanto pendente; `409` em falha/rejeição |
| `GET /api/v1/analyses/{analysisId}/payload` | Bundle validado, com paciente completado e referências privadas às imagens |
| `GET /api/v1/analyses/{analysisId}/images/{mediaId}` | Download autenticado dos bytes originais |

Essas rotas pertencem a `apps.quality_api.main:app`, porta 8000 por padrão.
Os endpoints Flask existentes e `/api/v1/quality/assess` mantêm seu contrato.
A nova fila e seu armazenamento são separados do histórico da API antiga.
O Swagger fica em `/docs`; o contrato gerado está em `/openapi.json`.

## Contrato de envio

- `Authorization: Bearer <access token Supabase>`: sessão ativa e papel clínico
  autorizado em `app_metadata`, usando o verificador existente do Heal+.
- `Content-Type: application/fhir+json`, FHIR R4 4.0.1, sem compressão HTTP.
- `X-Patient-Consent: true`: confirmação explícita de consentimento para cada
  envio. Ausência ou qualquer outro valor resulta em `403` antes da leitura.
- `Idempotency-Key`: recomendado, 8–128 caracteres alfanuméricos, ponto,
  sublinhado ou hífen. Reenvio do mesmo payload pelo mesmo usuário reutiliza
  a tarefa; conteúdo diferente com a mesma chave retorna `409`.
- Até 8 JPEGs, 10 MiB e 12 megapixels por imagem; até 28 MiB por corpo HTTP.
  PNG permanece disponível no endpoint antigo de qualidade, mas o perfil
  de recepção desta integração exige JPEG conforme a referência do projeto.
- Cada `Media` exige `status: completed`, `createdDateTime` com horário e fuso,
  `subject.reference: Patient/{id}` e `content.contentType/data`.
  `encounter`, `operator`, `device` e `bodySite` podem acompanhar a imagem.
- Todo lote pertence a um único paciente e, quando informado, um atendimento.
  `Media.subject` pode ser completado a partir de um `Patient` único no Bundle
  ou de `Task.for`. A tarefa de entrada exige `status: requested` e `intent: order`.
  `Task.input.valueReference` deve apontar para uma imagem contida no envio.
- A API consulta `patients` com o JWT do solicitante, RLS e filtro explícito
  de proprietário. Completa somente `id`, nome e data de nascimento cadastrados.
  Dados demográficos enviados pelo cliente não substituem o cadastro.
  Paciente ausente, arquivado ou inacessível retorna `404`.
- Referências de atendimento são contexto informado pela integração; um
  `Encounter` incluído deve apontar para o mesmo paciente. A API não cria nem
  consulta atendimentos em um servidor FHIR remoto.
- URLs de upload e referências externas de paciente/atendimento são recusadas.
  Nenhuma validação envia imagens ou dados clínicos a HAPI ou a terceiros.
  O schema HL7 R4 é versionado localmente, com hash da fonte e script de extração.
  Essa validação cobre estrutura e regras do perfil local, não homologação RNDS
  nem resolução de terminologias institucionais.

## Persistência e processamento

`HEAL_INTAKE_DB_PATH` aponta para um banco SQLite exclusivo da fila; padrão:
`data/intake/analyses.db`. A migração versionada
`src/analysis_intake/migrations/001_intake.sql` cria imagens, tarefas e eventos.
Os originais JPEG são BLOBs: imagem, metadados e enfileiramento têm a mesma
transação, sem janela entre upload e publicação de mensagem.

Os metadados incluem Media/Bundle FHIR, dimensões após orientação, tamanho,
MIME, SHA-256 do original, métricas e versão do avaliador. O campo FHIR
`Attachment.hash` usa SHA-1 em base64 conforme R4; o controle interno de
integridade usa SHA-256. O worker verifica a integridade, normaliza orientação
EXIF em memória e chama `WoundAnalysisService`/`ClinicalWoundAnalyzer`.
O original permanece inalterado.

| Estado local | `Task.status` | Significado |
|---|---|---|
| `ACCEPTED` | `accepted` | Evento de aceitação registrado na transação |
| `QUEUED` | `ready` | Pronto para o worker; estado retornado no primeiro `202` |
| `PROCESSING` | `in-progress` | Worker possui uma reserva temporária da tarefa |
| `COMPLETED` | `completed` | Resultado persistido e disponível |
| `FAILED` | `failed` | Três tentativas esgotadas |
| `REJECTED` | `rejected` | Qualidade reprovada ou indeterminada; não vai para a fila |

Qualidade reprovada em qualquer imagem rejeita o lote inteiro com `422`.
Ficam somente metadados e motivos de rejeição; nenhum JPEG é persistido.
Erros de estrutura, acesso e decodificação não criam tarefa.
Há duas admissões simultâneas por processo HTTP e limite de 100 tarefas
pendentes por usuário. Dimensione também limites e cotas no gateway.

Workers disputam tarefas por transação `BEGIN IMMEDIATE`. A reserva dura
120 segundos e é renovada durante a execução; interrupções permitem retomada.
Um token de reserva impede que um worker antigo sobrescreva o resultado de
outro. Falhas recebem até três tentativas, com espera crescente de 5 segundos
por tentativa; após a última, passam a `FAILED`. O processamento tem semântica
de pelo menos uma tentativa: uma interrupção pode repetir computação, mas
somente o detentor da reserva pode publicar o resultado.

Todas as consultas verificam proprietário e acesso atual ao paciente. Tokens,
base64, dados clínicos e mensagens internas de exceção não são registrados
pelo fluxo de recepção. Respostas usam `Cache-Control: no-store`.
O resultado preserva as limitações do motor e exige revisão profissional.

## Execução no Windows

Instale `requirements-api.txt`. Configure no ambiente do backend
`SUPABASE_URL` e `SUPABASE_PUBLISHABLE_KEY` (ou `SUPABASE_ANON_KEY`). A função
`current_session_is_active` e as políticas já versionadas do projeto devem
estar disponíveis. Não use `CLINICAL_API_REQUIRE_AUTH=0`: a recepção falha
fechada nesse modo.

Na raiz do repositório, abra dois terminais com o mesmo caminho absoluto:

```powershell
$env:HEAL_INTAKE_DB_PATH = Join-Path $PWD 'data/intake/analyses.db'
python -m uvicorn apps.quality_api.main:app --host 127.0.0.1 --port 8000
```

```powershell
$env:HEAL_INTAKE_DB_PATH = Join-Path $PWD 'data/intake/analyses.db'
python -m src.analysis_intake.worker
```

Interrompa com `Ctrl+C`. Use `--once` no worker para consumir no máximo um lote.
O Compose também inclui `quality-api` e `intake-worker` com volume compartilhado.

Exemplo de envio, preenchendo os identificadores reais e a data da captura:

```powershell
$secureToken = Read-Host 'Access token Supabase' -AsSecureString
$token = [System.Net.NetworkCredential]::new('', $secureToken).Password
$headers = @{
  Authorization = "Bearer $token"
  'X-Patient-Consent' = 'true'
  'Idempotency-Key' = [guid]::NewGuid().ToString()
}
$payload = @{
  resourceType = 'Media'
  id = [guid]::NewGuid().ToString()
  status = 'completed'
  subject = @{ reference = 'Patient/ID-DO-PACIENTE-CADASTRADO' }
  createdDateTime = '2026-09-21T10:15:00-03:00'
  content = @{
    contentType = 'image/jpeg'
    data = [Convert]::ToBase64String([IO.File]::ReadAllBytes('C:\imagens\foto.jpg'))
  }
} | ConvertTo-Json -Depth 10
$accepted = Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/analyses' `
  -Method Post -Headers $headers -ContentType 'application/fhir+json' -Body $payload
Invoke-RestMethod ("http://127.0.0.1:8000" + $accepted.statusUrl) -Headers $headers
Invoke-RestMethod ("http://127.0.0.1:8000" + $accepted.resultUrl) -Headers $headers
```

Reutilize `$headers` e `$payload` ao repetir um envio cuja resposta se perdeu.
Para várias imagens, envolva os recursos Media em `Bundle.type=collection`,
com uma entrada `{ resource: <Media> }` por imagem.

## Limites operacionais

Esta fila é local ao Heal+, em volume persistente compartilhado no mesmo host.
Não implementa o transporte do cluster, RNDS, broker distribuído ou webhook.
O cliente acompanha a conclusão por polling dos endpoints acima.
Proteja o diretório com ACLs da conta do serviço, criptografia de disco,
backup consistente do SQLite/WAL e política institucional de retenção.
SQLite não fornece criptografia em repouso por si só; não publique o volume
como diretório estático nem o compartilhe entre hosts via filesystem de rede.
As validações sintéticas não equivalem a homologação clínica ou de produção.

Referências: [Media R4](https://hl7.org/fhir/R4/media.html),
[Task R4](https://hl7.org/fhir/R4/task.html),
[Supabase getUser](https://supabase.com/docs/reference/python/auth-getuser).
