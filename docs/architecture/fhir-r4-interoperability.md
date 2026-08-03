# FHIR R4 Interoperability Architecture

## Placement decision

The repository already had an interoperability package at `src/interoperability`.
Instead of introducing a parallel package elsewhere, the new FHIR layer was added
as `src/interoperability/fhir_r4`.

This keeps the structure clean for three reasons:

1. Existing code already groups interoperability concerns under `src/interoperability`.
2. Legacy entry points such as `src.interoperability.fhir_client` can stay stable.
3. New FHIR-specific logic remains isolated from dashboard, ML, and care-plan code.

## Folder structure

```text
src/interoperability/fhir_r4/
  models/
  mappers/
  validators/
  client/
  adapters/google_cloud/
  examples/
```

## Data flow

The implementation follows this flow:

1. REDISUS payloads arrive from:
   - wound evaluations
   - normalized inference results from `packages/clinical_domain/workflow.py`
   - care plan payloads
   - image metadata
2. `RedisusFHIRMapper` normalizes those payloads.
3. Resource models build the FHIR JSON structure.
4. Validators perform minimum structural checks.
5. A generic client or cloud adapter sends the payload.

## Backend integration

The first backend integration point is now available in the clinical API:

- `GET /api/v1/lesions/<case_id>/fhir`

This route assembles the FHIR export from the real persisted clinical case:

- patient record
- selected evaluation, defaulting to the latest one in the lesion timeline
- stored clinical images
- latest inference result linked to the evaluation
- active or matching care plan

Supported query parameters:

- `bundleType=collection|transaction`
- `evaluationId=<evaluation_id>`
- `download=1`

## Resource mapping

### Patient

Source inputs:

- internal patient id
- CPF / CNS
- demographics
- contact and address data

### Practitioner

Mapped REDISUS concepts:

- `professional_name` from the stored evaluation
- local professional identifier when available
- professional role represented in `PractitionerRole`

### Encounter

Mapped REDISUS concepts:

- evaluation as an ambulatory encounter
- patient subject and practitioner participant
- service provider link to the mapped unit organization when available
- condition link through encounter diagnosis
- local case/evaluation identifiers for traceability
- period, reason text, wound location, and service type coding

### Observation

Mapped REDISUS concepts:

- tissue percentages
- wound area
- wound depth
- pain score
- PUSH score
- BWAT score
- REDISUS health score
- AI confidence
- risk level

### Condition

Mapped REDISUS concepts:

- wound etiology classification
- local REDISUS coding only while a standard etiology mapping has not been clinically validated
- body site
- risk-derived severity
- AI confidence as extension
- optional links to `Encounter` and recorder `Practitioner`

### DiagnosticReport

Mapped REDISUS concepts:

- assessment summary
- observation reference
- condition coding summary
- recommendations
- wound image linkage through `Media`
- attachment fallback through `presentedForm`
- encounter and performer linkage when available

### CarePlan

Mapped REDISUS concepts:

- task list
- schedule/frequency text
- goals and alert notes
- condition relationship
- author and encounter linkage when available

### Organization

Mapped REDISUS concepts:

- `unit_id` and `unit_name` as the primary service organization
- `team_id` and `team_name` as the care-team organization
- hierarchical relation between team and unit through `partOf`

### PractitionerRole

Mapped REDISUS concepts:

- clinical role derived from practitioner/evaluation context
- organization allocation derived from team or unit scope
- wound-care specialty placeholder prepared for future target value sets

### Media

Mapped REDISUS concepts:

- stored wound images as reusable clinical resources
- patient, encounter, operator, reason, and body-site linkage
- attachment preservation for URL, inline data, or local image path

### Provenance

Mapped REDISUS concepts:

- human authorship from the evaluating professional
- derived AI generation with model/contract version traceability
- professional verification using the FHIR `verifier` participation type
- explicit linkage between exported resources and the originating evaluation/images

## Canonical wound contract decision

Contract version: `2026-08-03`.

The mapper uses a standard code only when the source concept and unit have an
unambiguous, reviewed destination. Other clinical concepts remain in an explicit
Heal+ namespace instead of being presented as LOINC, SNOMED CT, or ICD-10.

| Canonical source | FHIR destination | Coding and unit decision |
| --- | --- | --- |
| patient, professional, unit, team, case, evaluation and media ids | resource `identifier` | local NamingSystem under `https://heal.redisus.org.br/fhir/NamingSystem/*`; CPF/CNS keep their declared national identifier systems |
| evaluation time and care setting | `Encounter.period`, `Encounter.class`, `Encounter.serviceType` | ambulatory class; service/reason values remain local |
| wound assessment | `Observation.code` | LOINC `39135-9` (Wound assessment panel) |
| wound area | `Observation.component` | LOINC `89260-4`; UCUM `cm2` |
| wound depth | `Observation.component` | LOINC `39127-6`; UCUM `mm` |
| pain severity | `Observation.component` | LOINC `72514-3`; numeric score without a fabricated UCUM unit |
| tissue percentages | `Observation.component` | local codes `granulation`, `epithelialization`, `slough`, and `necrosis`; UCUM `%` |
| PUSH, BWAT, Heal+ health score and model confidence | `Observation.component` | local code system; numeric value without a fabricated `score` unit |
| risk level | `Observation.interpretation`, `Condition.severity` | local value set because it is a Heal+ workflow classification |
| wound etiology and body site | `Condition.code`, `Condition.bodySite` | local code when the input is local or unknown; no silent promotion to SNOMED CT or ICD-10 |
| assessment summary and recommendations | `DiagnosticReport.conclusion`, `DiagnosticReport.note` | free clinical text, preserved only in the explicitly requested export |
| wound image | `Media.content`, `DiagnosticReport.media` | one deduplicated `Media` per image; no image bytes duplicated in another clinical resource |
| automated generation | `Provenance.agent` | local software agent and model/contract identifiers |
| professional review | `DiagnosticReport.resultsInterpreter`, `Provenance.agent` | practitioner reference plus standard provenance participant type `verifier` |
| fields not represented above | omitted | no canonical destination has been approved; omission is safer than an invented standard mapping |

All contained references use absolute canonical `fullUrl` values under
`https://heal.redisus.org.br/fhir/{ResourceType}/{id}`. Relative references must
resolve to an entry in the same bundle. A transaction bundle additionally requires
each `request.url` to match its resource type and id.

Review state controls clinical status consistently: pending automated output is
`preliminary`/`provisional`; approved or professionally corrected output is
`final`/`confirmed`; rejected output is `entered-in-error`/`refuted`. Care plans
are exported only after a professional review has materialized them.

## Validation approach

The built-in contract validator checks:

- required fields per resource type
- unique resource identities and canonical `fullUrl` values
- resolvable internal references, including URN and relative references
- transaction request method and URL integrity
- approved wound LOINC codes and applicable UCUM units
- explicit namespace for local codes
- non-empty bundle entries and required clinical links

Optional validation through `fhir.resources` remains available but is not the
default execution path because local environments may carry different package
versions or target-profile expectations.

## Google Cloud Healthcare API boundary

The Google adapter targets a FHIR store endpoint with the following shape:

`https://healthcare.googleapis.com/v1/projects/{project}/locations/{location}/datasets/{dataset}/fhirStores/{store}/fhir`

Auth is intentionally externalized:

- direct bearer token via environment variable
- ADC via `GOOGLE_APPLICATION_CREDENTIALS` when `google-auth` is installed

This keeps transport concerns out of the mapper and makes it easier to add other
destinations later.

## Publication flow

The package now includes `FHIRPublicationService` as the controlled write path.
It is intentionally separate from the mapper and the API route.

The consent, destination, idempotency, retry and rollback boundary is defined in
[`fhir-publication-boundary.md`](fhir-publication-boundary.md). Export remains
local; external publication requires an explicit `FHIRPublicationAuthorization`.

Current responsibilities:

- validate bundle structure before send
- compute a stable hash ignoring volatile export timestamps
- skip duplicate publication of the same logical bundle
- retry transient failures with bounded attempts
- persist a local audit log and publication index

What is intentionally not hard-wired yet:

- asynchronous job orchestration
- persistent DB-backed publication ledger
- distributed locking
- target-specific retry policies
- operator-facing dashboards for publication status

## RNDS and other external dependencies

A server-side RNDS transport adapter now exists in
`src/interoperability/fhir_r4/adapters/rnds/`. It implements the official
Auth/EHR host split, certificate-based token request, RNDS headers, document
submission and safe capture of the returned `Location`.

It remains isolated from the Heal+ frontend and clinical API. The adapter is not
an assertion of homologation and cannot make the current generic Heal+ export
RNDS-conformant by itself.

Still required before real clinical use:

- institutional accreditation and homologation evidence;
- an approved RAC/document mapper for the wound-care scenario;
- full validation against the exact national profile and terminology package;
- secure certificate provisioning in the Integration Service/RNDS Dispatcher;
- DB-backed reconciliation and operator workflow for ambiguous submissions.

Operational details are in
[`../integrations/rnds-connector.md`](../integrations/rnds-connector.md).

## Known limitations

- The mapper covers the main wound case flow only.
- Scores, tissue classes, risk, service and reason codings remain local until an external target profile and value set are approved.
- Validation is structural-first, not full conformance against a Brazilian production IG package.
- Publication audit is currently file-based, not yet persisted in the application database.
- No automatic publication route is wired into the existing clinical API yet.
