# Política de artefatos, dados e modelos

O repositório deve ser leve, auditável e seguro. Artefatos gerados não devem ser versionados no Git.

## Permitido no Git

- Código-fonte.
- Testes e fixtures sintéticas pequenas.
- Documentação.
- Model cards.
- Dataset cards.
- Manifests e checksums.
- Schemas e contratos.
- Imagens pequenas de UI ou exemplo sintético explicitamente justificadas.

## Proibido no Git

- Dados clínicos reais.
- Dumps de banco.
- Arquivos `.db`, `.sqlite` ou `.sqlite3`.
- Checkpoints e pesos: `.pt`, `.pth`, `.keras`, `.h5`, `.ckpt`, `.onnx`, `.tflite`, `.task`, `.pb`.
- Diretórios `dataset/`, `models/`, `runs/` e `tmp_images/`.
- Logs de treinamento e TensorBoard events.
- DOCX/PDF gerados automaticamente quando houver fonte em Markdown, LaTeX ou script.

## Registro de modelos

Cada modelo publicado deve ter entrada em `ml/registry/models.yaml` com:

- `id`
- `version`
- `status`
- `task`
- `artifact_uri`
- `local_cache_path`
- `sha256`
- `license`
- `intended_use`
- `limitations`
- `metrics`

Enquanto o storage externo não for definido, use `artifact_uri: pending://...` e mantenha o arquivo local ignorado pelo Git.

O inventário dos blobs históricos e o plano reversível de migração estão em
[`artifact-history-inventory.md`](artifact-history-inventory.md).

Downloads devem usar `scripts/fetch_verified_artifact.py`, que aceita apenas
`https://` ou `file://`, limita tamanho, verifica SHA-256 e só então promove o
arquivo temporário ao cache. URI com credencial embutida é rejeitada.

## Registro de datasets

Cada dataset deve ter dataset card em `docs/data/` ou manifest em `data/manifests/`, incluindo origem, licença, termos de uso, data de coleta, splits, transformações, riscos e limitações.

## Exceções

Exceções precisam ser pequenas, justificadas e revisadas em PR. Exemplos atuais aceitáveis: `examples/synthetic_wound.jpg`, logos e assets estáticos essenciais do frontend.
