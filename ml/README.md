# HEAL+ ML Workspace

Pipeline offline para treino e avaliacao de modelos de feridas cronicas. O frontend nao executa treino pesado e nao deve fingir IA clinica validada.

## Estrutura

- `datasets/`: manifestos e datasets locais nao versionados.
- `notebooks/`: exploracao e auditoria.
- `scripts/`: preparacao, treino, avaliacao, exportacao e inferencia.
- `models/`: pesos locais nao versionados.
- `configs/`: configuracoes de treino.
- `outputs/`: metricas, predicoes e relatorios.
- `benchmarks/`, `model_cards/`, `registry/`: governanca ja existente.

## Ordem recomendada

1. Preparar dataset licenciado com imagens e mascaras.
2. Validar mascaras.
3. Treinar segmentacao ferida vs fundo.
4. Avaliar Dice, IoU, Precision, Recall, F1, FPR e FNR.
5. Testar imagens fora do dataset.
6. Treinar validador de entrada/ROI.
7. Somente depois treinar classificacao tecidual.

## Segurança

Nao coloque imagens clinicas identificaveis no Git. Remova EXIF, nomes, documentos, rosto e metadados sensiveis. Exija consentimento e revisao profissional antes de exportar ROIs internas.

## CO2Wounds-V2

Uso permitido neste projeto: pesquisa, TCC, prova de conceito e treinamento experimental inicial de segmentacao ferida vs. fundo. Nao usar o modelo resultante como IA clinica validada nem em produto comercial sem autorizacao formal dos autores.

Fluxo esperado depois de baixar o dataset fora do Git:

```bash
python ml/scripts/prepare_co2wounds_v2.py --root data/external/co2wounds-v2 --accept-non-commercial-research-license
python ml/scripts/validate_masks.py --manifest ml/datasets/co2wounds_v2_train.jsonl
python ml/scripts/train_segmentation.py --accept-experimental-non-commercial-use --image-size 128 --epochs 8 --scheduler cosine
```

O preparador localiza automaticamente a pasta `split/` do ZIP oficial. Imagens
identicas com anotacoes separadas sao agrupadas, suas mascaras sao unidas e o
grupo inteiro permanece em um unico split. O treino e bloqueado se ainda houver
qualquer hash de imagem repetido entre treino e validacao.

## Auditoria do classificador

Antes de treinar classificacao etiologica, audite o acervo local:

```bash
python ml/scripts/audit_classification_dataset.py --root dataset/medetec_consolidated --fail-on-cross-label-conflict
```

Imagens identicas com rotulos diferentes bloqueiam o treino. Imagens do mesmo
paciente tambem devem permanecer no mesmo split quando um identificador
desidentificado de paciente estiver disponivel.

## Segmentacao multiclasse de tecidos

A taxonomia v0 e provisoria: fundo, granulacao, esfacelo/fibrina,
necrose/escara e `255` para pixels incertos. Antes de qualquer treino, revise
`docs/research/multiclass-annotation-protocol-v0.md` com a equipe clinica e
execute a auditoria somente leitura:

```bash
python ml/scripts/audit_segmentation_dataset.py --dataset-root CAMINHO_AUTORIZADO --manifest MANIFESTO.csv --fail-on-blockers
```

O comando bloqueia a liberacao diante de pares ausentes, arquivos corrompidos,
classes inesperadas, vazamento entre splits ou taxonomia sem validacao clinica.
Nao use `output/uploads` como fonte de treino: dados enviados ao produto nao
possuem consentimento implicito para pesquisa.

Revisao visual local, apos confirmar que o dispositivo e a pasta de saida sao
autorizados:

```bash
python ml/scripts/review_segmentation_masks.py --dataset-root CAMINHO_AUTORIZADO --manifest MANIFESTO.csv --max-samples 20 --allow-local-clinical-previews
```

Depois de tratar os bloqueios da auditoria, gere cinco folds agrupados por
paciente e balanceados pelo conteudo das mascaras:

```bash
python ml/scripts/create_multiclass_folds.py --dataset-root CAMINHO_AUTORIZADO --manifest MANIFESTO.csv --folds 5 --seed 42
```

O gerador exige identificadores pseudonimizados de paciente e ferida para todas
as amostras. A saida publica apenas `sample_id` derivado por hash e fold.

O primeiro baseline multiclasse fica bloqueado ate a taxonomia ser aprovada e a
auditoria nao ter bloqueios:

```bash
python ml/scripts/train_multiclass_unet.py --dataset-root CAMINHO_AUTORIZADO --manifest MANIFESTO.csv --fold-assignments ml/outputs/multiclass_folds/grouped_fold_assignments.csv --validation-fold 0 --accept-research-only
```

O baseline usa U-Net compacta com GroupNorm, letterbox, augmentations moderadas,
`ignore_index=255`, pesos calculados apenas no fold de treino, mixed precision
em CUDA, acumulacao e clipping de gradiente, scheduler, early stopping,
checkpoint `best`/`last` e retomada. O teste final nao participa da selecao.

Antes do treino, um profissional deve revisar pelo menos 20 variacoes locais:

```bash
python ml/scripts/preview_multiclass_augmentations.py --dataset-root CAMINHO_AUTORIZADO --manifest MANIFESTO.csv --count 20 --output CAMINHO_LOCAL_AUTORIZADO/augmentations.png --allow-local-clinical-previews
```

## Anotacao binaria guiada e treino semissupervisionado

Para contornar 100 feridas, aprovar e avancar automaticamente, treinar o
professor, revisar pseudo-rotulos e treinar o aluno:

```powershell
.\scripts\run_wound_annotation.ps1 -Images "C:\caminho\autorizado\imagens" -Workspace "C:\caminho\local\healplus-anotacoes"
```

O fluxo e retomavel e nao usa frontend web. Consulte
`docs/research/guided-semisupervised-wound-workflow.md`.

## Inferencia e exportacao

```bash
python ml/scripts/infer_single_image.py --image caminho/ferida.jpg --model ml/outputs/co2wounds_v2_unet_v2_final/best_small_unet.pt --allow-non-commercial-research
python ml/scripts/export_model.py --checkpoint ml/outputs/co2wounds_v2_unet_v2_final/best_small_unet.pt --format torchscript --output ml/models/wound_segmentation.ts --allow-non-commercial-research
```

Para usar o checkpoint de pesquisa no analisador headless, configure
`HEAL_ENABLE_EXPERIMENTAL_WOUND_SEGMENTER=1`, o caminho do checkpoint e
`HEAL_ALLOW_NONCOMMERCIAL_RESEARCH_MODEL=1`. O resultado inclui limiar,
incerteza, cobertura, versao e motivo de fallback. Nao habilite um checkpoint
nao comercial em produto ou atendimento real.
