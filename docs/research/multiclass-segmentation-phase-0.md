# 1. Entendimento do problema

O objetivo é evoluir o HEAL+ de uma segmentação binária da ferida para uma
segmentação semântica dos tecidos visíveis no leito, preservando revisão humana,
rastreabilidade e os dados originais. A saída pretendida é experimental e de
apoio: não constitui diagnóstico, prescrição ou autorização de uso clínico.

O programa deve manter duas tarefas separadas:

- segmentação binária: região externa versus ferida;
- segmentação tecidual dentro da ferida: fundo, granulação,
  esfacelo/fibrina, necrose/escara e pixels incertos ignorados.

O trabalho foi iniciado pela Fase 0. A inspeção local confirmou código
reutilizável, porém não encontrou no worktree atual o dataset clínico,
as máscaras exibidas nas capturas de tela ou metadados suficientes para
executar treino e avaliação reais. Nenhuma métrica experimental foi inventada.

## Decisão técnica 1

**DECISÃO:** manter o problema binário separado da classificação tecidual e
usar a máscara binária como possível restrição espacial, a ser avaliada por
ablação.

**EVIDÊNCIA OU MOTIVAÇÃO:** a literatura distingue segmentação da ferida,
mensuração e classificação de tecidos; a WSNet publicada é uma abordagem de
segmentação da ferida, não uma taxonomia tecidual pronta para reutilização.

**RISCO:** erros do primeiro estágio podem ser propagados para o segundo.

**ALTERNATIVA:** segmentação multiclasse direta na imagem inteira.

**COMO SERÁ VALIDADA:** comparar imagem inteira, ROI humana, ROI prevista e
pipeline em dois estágios usando os mesmos folds por paciente.

# 2. Síntese técnica das referências

- Zahia et al. estudaram granulação, esfacelo e necrose em imagens de lesão por
  pressão, incluindo tratamento de reflexo de flash e classificação baseada em
  patches. O desempenho relatado varia entre tecidos, com esfacelo sendo a
  classe mais difícil. A decisão aplicável ao HEAL+ é medir cada classe
  separadamente e criar uma categoria explícita de erro para brilho especular.
  Fonte primária: <https://pubmed.ncbi.nlm.nih.gov/29650318/>.
- A revisão sistemática de Scebba et al. separa segmentação, mensuração,
  classificação tecidual e acompanhamento. Ela também evidencia heterogeneidade
  de datasets, captura e validação, o que impede transportar números publicados
  diretamente para o HEAL+. Fonte:
  <https://doi.org/10.1016/j.artmed.2019.101742>.
- A WSNet combina contexto global e patches locais e usa adaptação ao domínio
  de feridas. No HEAL+, isso será tratado como hipótese experimental posterior
  aos baselines, não como reprodução do artigo. Fonte:
  <https://openaccess.thecvf.com/content/WACV2023/html/Oota_WSNet_Towards_an_Effective_Method_for_Wound_Image_Segmentation_WACV_2023_paper.html>.
- O estudo de registro fotográfico da UFMG organiza recomendações sobre
  consentimento, posicionamento, câmera, iluminação, fundo, foco, consistência
  de cor e armazenamento. A implicação é separar controle de captura de
  transformação da imagem e não corrigir silenciosamente a fotografia clínica.
  Fonte institucional:
  <https://repositorio.ufmg.br/handle/1843/51307?locale=en>.
- A revisão sobre IA baseada em imagens de feridas descreve segmentação,
  classificação, mensuração e sistemas móveis, mas destaca lacunas entre
  protótipos e sistemas clinicamente validados. Fonte:
  <https://arxiv.org/abs/2009.07141>.

## Decisão técnica 2

**DECISÃO:** começar com leitura RGB, orientação, letterbox e normalização
simples; correção cromática e remoção de reflexos serão apenas braços de ablação.

**EVIDÊNCIA OU MOTIVAÇÃO:** cor e textura distinguem tecidos, enquanto captura
por smartphone introduz variação de iluminação e dispositivo.

**RISCO:** normalização agressiva pode remover uma pista clínica ou criar uma
aparência artificial.

**ALTERNATIVA:** color constancy moderada, com o original sempre preservado.

**COMO SERÁ VALIDADA:** avaliação pareada por fold, por dispositivo e por
condição de captura, mais inspeção cega de amostras antes/depois.

## Decisão técnica 3

**DECISÃO:** avaliar as classes individualmente e não selecionar modelo apenas
pela média global.

**EVIDÊNCIA OU MOTIVAÇÃO:** diferenças entre tecidos aparecem na referência de
Zahia et al.; uma média pode ocultar falha numa classe clinicamente importante.

**RISCO:** poucos pixels de uma classe produzem intervalos amplos e métricas
instáveis.

**ALTERNATIVA:** consolidar classes, somente se houver justificativa e aprovação
clínica.

**COMO SERÁ VALIDADA:** Dice, IoU, precisão, recall, especificidade e F1 por
classe, macro e ponderadas, matriz de confusão, bootstrap por paciente e
intervalos por fold.

# 3. O que já foi realizado no HEAL+

As capturas e o plano fornecidos indicam organização de imagens, seleção inicial
de 100 casos, ROI/GrabCut, revisão de máscaras binárias, U-Net básica, métricas
iniciais e planejamento de pseudo-rótulos, active learning e Residual U-Net.
Essas informações são histórico informado; os respectivos dados e resultados
não estão todos presentes no worktree auditado.

No repositório atual foram confirmados:

- pipeline binário executável em `ml/scripts/train_segmentation.py`;
- modelo `SmallUNet`, letterbox, treino, checkpoints, retomada, scheduler,
  early stopping e métricas binárias;
- descoberta de pares, crop por máscara, resize e split agrupado em
  `src/training/segmentation_dataset.py`;
- métricas binárias e multiclasse em
  `src/training/segmentation_metrics.py`;
- pipeline legado de DeepLabV3 para tecidos em
  `src/training/tissue_segmentation_training.py`;
- configurações, model cards e documentação de governança de modelos
  experimentais.

# 4. Lacunas do plano atual

- O dataset clínico e as primeiras 100 máscaras não estão versionados nem
  apontados por um manifesto local disponível.
- Não há IDs pseudonimizados de paciente e ferida para verificar separação.
- A codificação legada contém uma quinta classe treinável, pele perilesional,
  conflitante com o esquema tecidual provisório.
- Não há taxonomia tecidual formalmente aprovada.
- Não foram encontradas máscaras multiclasse, dupla anotação ou adjudicação.
- Origem, licença, consentimento, retenção e autorização de pesquisa do acervo
  das capturas não foram confirmados.
- Não há checkpoint tecidual treinado nem resultados reais de folds.
- O ambiente local é CPU; os experimentos maiores exigirão ambiente CUDA ou
  Colab controlado.
- Albumentations, MONAI, `segmentation_models_pytorch`, ONNX e MLflow não estão
  instalados. Eles não serão adicionados sem necessidade demonstrada.

# 5. Taxonomia clínica provisória

| Valor | Classe provisória | Uso |
| ---: | --- | --- |
| 0 | fundo/região externa à ferida | treinável |
| 1 | tecido de granulação | treinável |
| 2 | esfacelo/fibrina | treinável |
| 3 | necrose/escara | treinável |
| 255 | incerto/não rotulado | ignorado por loss e métricas |

Pele perilesional e epitelização ficam adiadas. O arquivo de taxonomia possui
estado `provisional_clinical_review_required`; o código rejeita uma taxonomia
marcada como aprovada sem `clinically_validated=true`.

## Decisão técnica 4

**DECISÃO:** não incluir epitelização ou pele perilesional como classe treinável
nesta versão.

**EVIDÊNCIA OU MOTIVAÇÃO:** o pedido exige definição clínica, exemplos e
concordância antes da inclusão; esses elementos ainda não existem no projeto.

**RISCO:** pixels clinicamente ambíguos podem aumentar o uso do valor 255.

**ALTERNATIVA:** uma versão posterior da taxonomia, sem reinterpretar máscaras
antigas e com migração versionada.

**COMO SERÁ VALIDADA:** aprovação formal, conjunto de exemplos, piloto de dupla
anotação e análise de confusão com pele periférica e granulação.

# 6. Arquitetura geral proposta

1. Camada de governança: consentimento, licença, pseudonimização e separação
   clínica/pesquisa.
2. Auditoria somente leitura: pareamento, qualidade, EXIF/GPS, classes,
   duplicatas e vazamentos.
3. Protocolo e dupla anotação: máscaras indexadas, `ignore=255`, revisão e
   adjudicação.
4. Pipeline de dados: orientação, letterbox, normalização e augmentations
   moderadas sincronizadas.
5. Split por paciente; se não houver paciente, por ferida; nunca divisão simples
   por imagem.
6. Baseline binário já existente e baseline U-Net multiclasse.
7. Somente após baselines: Residual Attention SE U-Net e ramo global–local.
8. Somente após modelo humano confiável: pré-treino sem teste, pseudo-rótulos
   controlados e active learning.
9. Avaliação por classe, paciente, dispositivo, captura e grupos autorizados.
10. Inferência com incerteza, versão, qualidade de captura e revisão profissional
    obrigatória.

# 7. Plano de execução por fases

| Fase | Entrega e porta de saída | Estado após esta auditoria |
| --- | --- | --- |
| 0 | referências, inventário, ambiente e riscos | concluída |
| 1 | relatório real de imagens/máscaras e vazamentos | ferramenta concluída; execução clínica bloqueada por ausência de dados |
| 2 | taxonomia e manual, piloto com dupla anotação | artefatos provisórios; aguarda aprovação e dados |
| 3 | revisão das primeiras 100 e splits por grupo | gerador de folds preparado; revisão real bloqueada |
| 4 | baseline binário nos splits aprovados | código legado disponível; novo treino bloqueado |
| 5 | baseline U-Net multiclasse | código e smoke test sintético prontos; treino clínico bloqueado |
| 6 | Residual Attention SE U-Net e ablações | não iniciar antes da Fase 5 |
| 7 | global–local inspirado na WSNet | não iniciar antes da Fase 5 |
| 8 | adaptação ao domínio sem usar teste final | depende de imagens não rotuladas autorizadas |
| 9 | pseudo-rotulagem com 255 em baixa confiança | depende de baseline confiável |
| 10 | active learning com incerteza e diversidade | depende de baseline e pool autorizado |
| 11 | teste externo, erros e equidade | depende de coorte/metadados autorizados |
| 12 | exportação, equivalência numérica e integração | depende de modelo selecionado |

Não é cientificamente válido “executar” as fases 3–12 sem dados, taxonomia
aprovada e splits. Os artefatos preparatórios não serão apresentados como
resultados de treinamento.

# 8. Estrutura dos arquivos

```text
ml/
  configs/
    multiclass_unet_v0.json
    tissue_taxonomy_v0.json
  scripts/
    audit_segmentation_dataset.py
    evaluate_annotation_agreement.py
    create_multiclass_folds.py
    review_segmentation_masks.py
    train_multiclass_unet.py
  outputs/
    segmentation_audit/        # gerado localmente, sem imagens clínicas
src/training/
  segmentation_audit.py
  annotation_agreement.py
  segmentation_review.py
  segmentation_splits.py
  multiclass_baseline.py
  segmentation_dataset.py
  segmentation_metrics.py
  tissue_segmentation_training.py
  tissue_taxonomy.py
data/
  manifests/
    README.md
  protocols/
    multiclass_annotation_schema_v0.json
docs/
  data/dataset-card.md
  research/
    multiclass-segmentation-phase-0.md
    multiclass-annotation-protocol-v0.md
    multiclass-annotation-quick-reference-v0.md
tests/
  test_segmentation_audit.py
  test_segmentation_dataset.py
  test_tissue_segmentation_training.py
  test_tissue_taxonomy.py
```

# 9. Informações encontradas no projeto

- Branch de trabalho: `codex/multiclass-wound-segmentation`.
- Ambiente inspecionado: Windows, Python 3.14.3, PyTorch 2.11 em CPU,
  torchvision 0.26, OpenCV 4.13, NumPy 2.4 e Pillow 12.2.
- CUDA e `nvidia-smi` não estão disponíveis localmente.
- Não há imagens ou máscaras em `data/` ou `ml/datasets/`.
- Há 55 imagens em `output/uploads`, mas elas foram excluídas: não há evidência
  de consentimento para pesquisa, manifesto ou máscara, e o diretório pode
  conter dados sensíveis do produto.
- Não foi encontrado o visualizador ROI/GrabCut mostrado na captura.
- Checkpoints presentes são de componentes gerais; não foi encontrado um
  checkpoint tecidual validável.
- Os 13 testes de segmentação já existentes passaram antes das alterações.
- O split existente foi ajustado para priorizar paciente antes de ferida.
- O decoder legado convertia `255` em fundo; isso foi corrigido e o valor passou
  a ser ignorado por loss e métricas.
- A U-Net multiclasse compacta passou em smoke test sintético de duas épocas em
  CPU. Esse teste valida execução e checkpoints; não produz evidência de
  desempenho em feridas reais.

# 10. Informações ainda ausentes

- caminho autorizado do dataset;
- manifesto com `image_path`, `mask_path`, `patient_id`, `lesion_id`,
  dispositivo, sequência temporal e origem;
- comprovação de licença/consentimento e política de retenção;
- confirmação se as 100 imagens pertencem a pacientes/feridas distintos;
- máscaras binárias e multiclasse originais;
- esquema atual real das máscaras e paleta, se não forem indexadas;
- parecer clínico sobre os limites das quatro classes;
- anotadores, amostra de dupla anotação e processo de adjudicação;
- metadados autorizados para equidade e generalização;
- coorte externa bloqueada;
- hardware e orçamento de treino.

# 11. Riscos técnicos e clínicos

- vazamento por fotografias repetidas, mesma ferida ou mesmo paciente;
- confusão entre esfacelo e brilho, necrose e sombra, granulação e sangue;
- viés de dispositivo, iluminação, localização e tom de pele;
- rótulos inconsistentes e fronteiras subjetivas;
- classe rara ausente em um fold;
- propagação de erro entre máscara binária e tecido;
- transformação cromática que altera informação clínica;
- pseudo-rótulo promovido incorretamente a ground truth;
- checkpoint privado ou não comercial distribuído sem autorização;
- uso do protótipo como diagnóstico por interpretação indevida.

As barreiras são: bloqueio automático de treino diante de vazamentos ou
taxonomia não aprovada, `ignore=255`, avaliação por pior classe e revisão
profissional obrigatória.

# 12. Primeiro conjunto de arquivos que serão criados ou alterados

O primeiro conjunto efetivamente implementado contém:

- taxonomia JSON versionada e carregador validado;
- auditoria reproduzível com relatório JSON/CSV/Markdown e gráfico agregado;
- testes sintéticos de privacidade, classes e vazamento;
- correção do agrupamento por paciente;
- correção do tratamento do índice 255;
- protocolo textual completo e referência rápida;
- atualização do Data Sheet para remover alegações que não correspondem ao
  conteúdo atual do worktree.

Nenhum arquivo clínico foi copiado, renomeado, alterado ou incluído no Git.

# 13. Critério para considerar a primeira fase concluída

A Fase 0 está concluída quando o inventário, o ambiente, as referências, as
decisões, as lacunas e os riscos estão registrados e os testes existentes foram
executados. A Fase 1 somente estará materialmente concluída quando:

1. o dataset autorizado for indicado por manifesto;
2. a auditoria produzir ao menos um par imagem/máscara decodificável;
3. não houver arquivos corrompidos, valores inesperados ou desalinhamento;
4. paciente e ferida tiverem cobertura suficiente para um split sem vazamento;
5. duplicatas entre splits forem eliminadas;
6. a fila de revisão humana for tratada;
7. a taxonomia for aprovada por responsável clínico;
8. o relatório final for arquivado sem identificadores ou previews sensíveis.

Comando preparado:

```powershell
python ml/scripts/audit_segmentation_dataset.py `
  --dataset-root C:\caminho\autorizado `
  --manifest C:\caminho\autorizado\manifest.csv `
  --output-dir ml/outputs/segmentation_audit `
  --fail-on-blockers
```

O código retorna status diferente de zero quando há bloqueios. A ausência de
bloqueios automáticos não equivale a aprovação ética, clínica ou regulatória.

Depois da aprovação da taxonomia, da auditoria sem bloqueios e da geração dos
folds, o baseline de um fold poderá ser executado com:

```powershell
python ml/scripts/train_multiclass_unet.py `
  --dataset-root C:\caminho\autorizado `
  --manifest C:\caminho\autorizado\manifest.csv `
  --fold-assignments ml/outputs/multiclass_folds/grouped_fold_assignments.csv `
  --validation-fold 0 `
  --accept-research-only
```

O comando calcula pesos somente nas amostras de treino, não acessa um conjunto
de teste e grava melhor/último checkpoint e histórico por época.
