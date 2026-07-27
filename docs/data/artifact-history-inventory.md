# Inventário de artefatos no histórico Git

Data da auditoria: 2026-07-27.

## Estado atual

- Nenhum arquivo rastreado no `HEAD` excede 5 MB.
- `Artifact Guard` bloqueia novos pesos, checkpoints, datasets, bancos e artefatos gerados.
- O histórico ainda contém blobs antigos grandes, embora seus caminhos estejam removidos do `HEAD`.

Maiores famílias encontradas:

| Família histórica | Maior blob observado | Classificação |
| --- | ---: | --- |
| `models/wound_classifier_v2/*.pth` | ~94 MB | peso de modelo |
| `models/wound_classifier/saved_model/**` | ~33 MB | peso de modelo |
| `models/wound_classifier_v2/*.pt` | ~20 MB | peso de modelo |
| `runs/**/weights/*.pt` | ~18 MB | saída de treinamento |
| `web/redisus-frontend/public/videos/dashboard-heal.mp4` | ~64 MB | mídia histórica |

O inventário usa tamanho de blob, não conteúdo, e não expõe dados clínicos.

## Decisão de armazenamento

- Código, cards, manifests e checksums ficam no Git.
- Modelos e datasets ficam em storage externo versionado com acesso por menor privilégio.
- Git LFS não é o destino padrão de modelos/datasets; pode ser usado somente para mídia de produto pequena, não clínica e explicitamente aprovada.
- `artifact_uri` não pode carregar token, assinatura duradoura ou credencial.
- O download só é promovido ao cache após SHA-256 válido por `scripts/fetch_verified_artifact.py`.

## Plano reversível de migração do histórico

1. Criar mirror de backup imutável e tag de preservação fora do repositório operacional.
2. Publicar cada artefato necessário no storage aprovado e registrar URI, licença, versão e SHA-256.
3. Validar restauração em clone descartável com o downloader verificado.
4. Gerar mapa `blob SHA -> artifact_uri -> sha256`.
5. Simular a reescrita em clone descartável com `git filter-repo`.
6. Comparar árvore do `HEAD`, tags de release, manifests e testes.
7. Agendar janela, congelar pushes e comunicar novos SHAs a todos os clones.
8. Executar force-push somente após aprovação explícita de manutenção, segurança e responsáveis por reprodutibilidade.
9. Manter o mirror de backup por prazo aprovado e documentar como recuperar uma versão histórica.

A reescrita não faz parte deste issue porque invalida clones e SHAs existentes. Executá-la sem backup e coordenação seria irreversível para colaboradores.

## Reprodução da auditoria

```powershell
git rev-list --objects --all |
  git cat-file --batch-check='%(objectname) %(objecttype) %(objectsize) %(rest)'
```

Ordene apenas linhas `blob` por tamanho e não abra conteúdo potencialmente sensível.

## Teste sintético do checksum

```powershell
python -m pytest tests/test_fetch_verified_artifact.py -q
```
