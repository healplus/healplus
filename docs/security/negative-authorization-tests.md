# Negative authorization tests

This document records the authorization boundaries covered by issue #41. All
fixtures are synthetic and the tests never emit clinical payloads, credentials,
or tokens.

## Dependency on issue #40

Issue #41 verifies the isolation contract defined by issue #40. The current
branch predates the broader #40 implementation, so it makes only the small API
change required to prevent identifier enumeration: an existing resource owned
by another user is returned as the same `404` problem response as a missing
resource. Ownership storage, query scoping, and the Firebase rules architecture
remain responsibilities of #40.

## Audited boundaries

| Boundary | Ownership contract | Negative coverage |
| --- | --- | --- |
| Clinical API | Patient `owner_uid` is the root authorization decision; wounds, evaluations, images, jobs, and reports inherit the patient's scope | User A reads or mutates a known resource of user B; the result is compared with an unknown ID |
| Firestore web rules | Clinical documents are nested below `users/{uid}` and require `request.auth.uid == uid` | Reads and writes against user B's patients, wound evaluations, and analysis results; each write payload must also succeed below user A's namespace |
| Root Firestore rules | Direct client access to clinical collections is deny-all; only explicit administrative claims reach other documents | Audited as a secure backend-only boundary; the web rule suite covers the client data model |
| Firebase Storage | Objects are nested below `users/{uid}` and image writes require an image MIME type and a size below 10 MiB | Reads, overwrites, creates, and deletes against user B's image namespace |

The frontend currently models a wound inside an evaluation rather than as an
independent Firestore document. Reports and asynchronous jobs are persisted by
the API, so their identifier tests live in the API matrix.

## Uniform denial contract

- The API returns `404 application/problem+json` with the same problem type,
  title, detail, code, error, and normalized complete payload for a known
  cross-user ID and a missing ID of the same resource type.
- Patient-linked and standalone wound analyses are both covered.
- Structurally incomplete repository records fail closed as `404` without an
  internal error. A repository failure raises a distinct internal exception and
  returns a generic `503 repository_unavailable`, so infrastructure failures
  are not mistaken for absent resources.
- Firestore returns `permission-denied` for both existing and missing documents
  below another user's namespace.
- Storage returns `storage/unauthorized` for both existing and missing objects
  below another user's namespace.
- Denial responses and application logs are checked for a synthetic sensitive
  marker to prevent accidental payload disclosure.

## CI execution

- `tests/test_negative_authorization.py` is part of the Python smoke job.
- `npm run test:rules` runs the Firestore and Storage matrices under the Firebase
  emulators in the web CI job with Java 21.
