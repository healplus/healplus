# Sprint 1: contratos e limites técnicos

Todas as coordenadas usam a imagem RGB `uint8` original. `ROI.bbox` é
`(x1, y1, x2, y2)` com limites superiores exclusivos. A expansão contextual
preserva 25% de cada dimensão **por lado**, limitada aos limites da imagem.
Identificadores de imagens/ROIs devem ser pseudônimos.

O pipeline limita imagens a 12 megapixels, a soma `pixels_da_imagem × ROIs`
a 16 megapixels de mapas por lote e cada recorte contextual a 2 megapixels
antes da criação do tensor de features. Esses limites protegem a memória;
não provocam redimensionamento silencioso. Ao reduzir a resolução, preserve
a escala e registre a transformação no manifesto reprodutível.

```python
from heal_plus_redisus.src.sprint1_pipeline import ROI, HybridSegmenter

result = HybridSegmenter().segment(
    image_rgb,
    ROI("lesao-1", (20, 20, 80, 80)),
    context={"etiology": "unknown"},
    # bed_mask=mascara_profissional_bool,  # opcional; nunca derivada de cor
)
assert result.status == "abstained_no_validated_model"
```

`context.etiology` aceita `pressure`, `venous`, `arterial`, `diabetic`,
`other`, `unknown`. Os indicadores opcionais `suspected_blood`,
`residual_dressing` e `recent_debridement` são booleanos ou desconhecidos.
São registros profissionais, não diagnósticos inferidos por imagem.

## Segmentação e incerteza

O tensor versionado de 27 canais combina RGB, HSV, LAB, LAB relativo ao
anel perilesional, textura local (desvio padrão, gradiente e Laplaciano),
zonas morfológicas e contexto clínico. O anel é um **proxy geométrico**;
não estabelece pele saudável nem fronteiras anatômicas verdadeiras.
Nenhum descritor clássico produz uma classe tecidual.

`TissueProposalUNet` possui cabeças separadas de contorno binário do leito e
cinco propostas teciduais. Um modelo recém-inicializado serve apenas para
treinamento e testes de forma. `TorchUNetBackend.from_checkpoint` verifica
SHA-256, carrega `weights_only=True`, exige o esquema de features e a versão
esperados e depende de `CheckpointApproval.approved`. A referência de revisão
e o digest do split devem remeter a evidência real de governança. Esses campos
não demonstram eficácia clínica por si mesmos.

Sem checkpoint aprovado, todo o suporte analisado se torna
`nao_classificado_baixa_confianca`; nenhum contorno é inventado. Uma máscara
profissional pode definir o leito, independentemente da classificação tecidual.
`class_map=255` significa fora do suporte, enquanto `4` significa tecido não
classificado. As probabilidades do backend devem voltar ao tamanho do recorte
original; o serviço retorna mapas na dimensão da imagem original.

Abstenção usa confiança `<0.65`, entropia normalizada `>=0.65`, a classe
neural desconhecida e artefatos. Sombra é uma diferença local relativa;
luminância absoluta baixa não implica necrose nem rejeição. Reflexo e baixa
nitidez apenas elevam incerteza. Sangue/curativo dependem de contexto ou máscara
revisada, não de inferência baseada em cor. Heurísticas são experimentais e
exigem calibração por câmera/dataset e auditoria de equidade.

`tissue_percentages` soma 100% no leito quando conhecido. Se o contorno estiver
indisponível, o escopo é explicitamente `unlocalized_roi` e 100% desconhecido.
`tia_percent` usa ROI como denominador; `bed_uncertainty_percent` informa
separadamente a incerteza no suporte tecidual. Não devem ser confundidos.

## Experimentos e relatórios

`CascadeEvaluator.evaluate` recebe `reference_bed_masks` como **rótulos de
avaliação**, sem enviá-los ao segmentador. Uma anotação disponível ao operador
deve ser passada separadamente em `professional_bed_masks`. Não use o mesmo
contorno como entrada e verdade de avaliação para alegar eficácia do contorno.

Matching de múltiplas lesões usa atribuição húngara de IoU; a média divide pela
maior contagem de caixas, penalizando ausências e duplicações. Máscaras da
cascata são avaliadas como união, preservando penalização de lesões perdidas.
`detection_map` calcula AP de classe única com 101 pontos de recall e limiares
IoU de 0.50 a 0.95, limitado a 100 detecções por imagem. Não implementa estratos
de área/crowd de COCO e não equivale a uma validação oficial pycocotools.
Sensibilidade sem positivos e especificidade sem negativos são `null`.

`YoloDetectorAdapter` aceita `checkpoint_sha256` e `model_version` opcionais,
sempre juntos. São metadados fornecidos por quem já carregou e revisou o
modelo; o adaptador não verifica o arquivo nem baixa pesos. A camada que
carrega o detector deve verificar o digest e a aprovação antes de habilitar
experimentos reais. O runner pode verificar essas duas propriedades públicas.

A/B/C/D seguem os limiares técnicos da Sprint. Combinações intermediárias,
não cobertas nas definições originais, recebem `INTERMEDIATE`. E é um indicador
independente: um caso pode continuar D e também receber E. Não se atribui A
quando a definição de A não é satisfeita.

`export_experiment(evaluations, images, output_dir)` salva tabelas JSON/CSV,
macro médias por imagem, mAP, lista C/D/E para Sprint 2 e painéis de seis colunas
para B/C/D/E. A coluna CV mostra textura/zonas explicativas, sem mapa de tecido
derivado de cor. Imagens devem passar antes pelo controle de upload,
anonimização e autorização da camada de aplicação. A comparação final requer
datasets licenciados, anotados e congelados e checkpoints revisados; os testes
automatizados sintéticos não demonstram desempenho clínico.

O HEAL+ é uma ferramenta de apoio ao registro, acompanhamento e análise evolutiva de feridas. As informações apresentadas pelo sistema, incluindo imagens, relatórios, percentuais teciduais e eventuais resultados de inteligência artificial, não substituem avaliação, diagnóstico, prescrição, estadiamento ou decisão de profissional de saúde habilitado. Qualquer interpretação clínica deve ser realizada por profissional responsável, considerando o contexto completo do paciente.
