# Official API

Esta é a camada oficial de backend do repositório a partir da reorganização.

## O que faz

- carrega o ambiente do projeto;
- inicializa o banco local clínico;
- registra a API clínica de `src/dashboard/clinical_api.py`;
- registra os endpoints de integração que antes viviam isolados em `backend/app.py`.
- registra a operação FHIR R4 `POST /api/v1/fhir/$validate-image` para qualidade técnica de imagens.

Contrato, métricas, autenticação e roteiro de validação RUTE:
[`docs/api/image-quality-fhir.md`](../../docs/api/image-quality-fhir.md).

## Como iniciar

```powershell
python -m apps.api.app
```

## Compatibilidade

`backend/app.py` continua existindo como shim e importa esta aplicação para evitar quebra de comandos antigos.
