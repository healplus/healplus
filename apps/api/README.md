# Compatibilidade da API

O backend canônico vive em `apps/heal_plus/api/`.

Este diretório mantém somente o import legado `apps.api.app` durante a
transição. Código novo deve usar:

```python
from apps.heal_plus.api.app import create_app
```

Este pacote continua exportando `app`, `create_app` e a operação FHIR R4 `POST /api/v1/fhir/$validate-image` para qualidade técnica de imagens.

Contrato, métricas, autenticação e roteiro de validação RUTE:
[`docs/api/image-quality-fhir.md`](../../docs/api/image-quality-fhir.md).

## Como iniciar

```powershell
python -m apps.api.app
```
