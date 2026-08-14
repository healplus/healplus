# Setup local de desenvolvimento

Este guia define os caminhos oficiais de instalação e execução do Heal+/REDISUS.
Escolha somente o perfil necessário para a tarefa. Não misture os perfis `api` e
`desktop` no mesmo ambiente, pois eles usam variantes diferentes do OpenCV.

O contrato legível por máquina está em
[`runtime-profiles.toml`](../../runtime-profiles.toml) e pode ser verificado com:

```powershell
python scripts/check_runtime_profiles.py
```

## Requisitos comuns

- Python 3.11;
- Git;
- ambiente virtual Python local;
- Node.js 22.22 ou superior e npm 10 apenas para o perfil web.

Modelos, datasets, checkpoints e credenciais não fazem parte de nenhum setup.
Artefatos necessários devem vir de storage externo, por URI e checksum, conforme
[`docs/data/artifact-policy.md`](../data/artifact-policy.md).

## Perfis oficiais

| Perfil | Dependências | Entrada oficial | Uso |
| --- | --- | --- | --- |
| API mínima | `requirements-api.txt` | `python -m apps.heal_plus.api.app` | backend, contratos e análise headless |
| Web | `apps/heal_plus/web/package-lock.json` via `npm ci` | `npm run dev` | frontend Vite/React |
| Desktop opcional | `requirements-desktop.txt` | `python heal_analyzer.py` | interface PyQt e OpenCV com GUI |
| ML opcional | `requirements-ml.txt` | scripts versionados em `scripts/` | treino, benchmark e inferência local pesada |

`requirements-ci.txt` adiciona somente ferramentas de teste e qualidade sobre a
API mínima. `requirements.txt` é um agregador legado e não é o caminho recomendado
para um ambiente novo.

## API mínima

Windows PowerShell:

```powershell
python -m venv .venv-api
.\.venv-api\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-api.txt
python scripts/check_runtime_profiles.py --profile api
$env:CLINICAL_API_REQUIRE_AUTH = "0"
$env:REDISUS_DB_PATH = "data/dev-api.db"
python -m apps.heal_plus.api.app
```

Linux ou macOS:

```bash
python3.11 -m venv .venv-api
source .venv-api/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-api.txt
python scripts/check_runtime_profiles.py --profile api
CLINICAL_API_REQUIRE_AUTH=0 REDISUS_DB_PATH=data/dev-api.db python -m apps.heal_plus.api.app
```

Verificação:

```powershell
python -m pytest tests/test_official_api_factory.py tests/test_runtime_profiles.py -q
```

O healthcheck oficial é `GET /api/v1/health`.

## Web

```powershell
Copy-Item apps/heal_plus/web/.env.example .env.local
Set-Location apps/heal_plus/web
npm ci
npm run lint
npm test
npm run build
npm run dev
```

Use `npm ci`, não `npm install`, para reproduzir o `package-lock.json`.

## Desktop opcional

Crie um ambiente separado do perfil API:

```powershell
python -m venv .venv-desktop
.\.venv-desktop\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-desktop.txt
python scripts/check_runtime_profiles.py --profile desktop
python heal_analyzer.py
```

Falhas relacionadas a `PyQt6`, câmera ou `cv2.imshow` indicam que o perfil
desktop não foi instalado ou que o sistema não oferece uma sessão gráfica. Elas
não devem ser tratadas instalando GUI no servidor da API.

## ML opcional

Crie outro ambiente:

```powershell
python -m venv .venv-ml
.\.venv-ml\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-ml.txt
python scripts/check_runtime_profiles.py --profile ml
python scripts/train_pressure_injury_classifier.py --help
```

O perfil oficial é compatível com CPU. CUDA, `onnxruntime-gpu`, TensorFlow,
MedSAM e checkpoints são extensões específicas de tarefa e não têm fallback
silencioso. Quando ausentes, o componente deve declarar estado degradado ou
indisponível e manter revisão humana obrigatória.

## Desenvolvimento e CI

```powershell
python -m venv .venv-dev
.\.venv-dev\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python scripts/check_runtime_profiles.py
python -m pytest tests/test_runtime_profiles.py -q
```

Com `make` disponível, os atalhos oficiais são:

```powershell
make install-api
make install-ci
make install-dev
make install-desktop
make install-ml
make check-runtime
make api-smoke
make web-install
make web-lint
make web-typecheck
make web-build
```

## Configuração e dados locais

Use `.env.example`, `.env.backend.example` e
`apps/heal_plus/web/.env.example` como contratos. Nunca versione `.env`,
service accounts, tokens ou conteúdo clínico.

Datasets, checkpoints, bancos locais, runs e imagens temporárias devem ficar
ignorados no disco local ou em storage externo. Os testes usam somente fixtures
sintéticas.
