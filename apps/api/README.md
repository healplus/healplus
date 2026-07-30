# Compatibilidade da API

O backend canônico vive em `apps/heal_plus/api/`.

Este diretório mantém somente o import legado `apps.api.app` durante a
transição. Código novo deve usar:

```python
from apps.heal_plus.api.app import create_app
```
