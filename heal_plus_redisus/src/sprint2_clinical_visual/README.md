# Sprint 2: contratos e limites técnicos

Os módulos operam sobre dados fornecidos pela aplicação autenticada. Não publicam
imagens, não acessam serviços externos e não inferem diagnóstico, etiologia ou
estadiamento. Os relatórios incluem `ASSISTIVE_DISCLAIMER` integralmente.

## Inspeção profissional

`VisualInspection` é um modelo Pydantic com identificadores pseudonimizados,
categoria da Sprint 1, dataset, tom de pele anotado, métricas em `[0, 1]` e fatores
`F01–F07`, `C01–C08`, `E01–E03`, `X01–X06`.
`features={"C01": "presente"}` registra uma observação humana; não executa uma
classificação automática. Os estados são `presente`, `ausente`, `desconhecido` e
`nao_avaliado`. Campo omitido permanece `desconhecido`.

`ClinicalVisualInspector().inspect(inspection)` retorna as 24 observações,
pendências de revisão e campos clínicos necessários ao contexto etiológico
informado. `reviewer_id` e `reviewed_at` com fuso horário representam a origem da
revisão. Cabe à camada de domínio verificar a identidade e o perfil do revisor;
o módulo não aceita texto clínico como instrução nem atribui credenciais.

## Análise estatística

`StatisticalAnalyzer().analyze(rows)` compara categoria D com A e exclui anotações
sem revisão. Para a análise ampliada da referência, use
`failure_categories=("C", "D", "E")`. Uma imagem só pode aparecer uma vez no mesmo
dataset. Pares, splits por paciente e comparabilidade precisam ser planejados
antes de formar os grupos; a função não inventa pareamento.

Para cada fator, a frequência é `presente / (presente + ausente)`, acompanhada de
contagens de desconhecidos e total. O denominador observado evita transformar
falta de avaliação em ausência. A RP divide as frequências entre os grupos. Sem
observações ou com frequência zero no controle, RP é `None` e o motivo é
explícito. Não são adicionados pseudocontadores nem resultados infinitos.

Dice, IoU e TIA são médias das métricas fornecidas, com contagem independente de
valores disponíveis, nos grupos com e sem o fator. As combinações de dois fatores
com presença observada são listadas. Os mesmos resultados são estratificados por
dataset e tom de pele. As taxas de falso positivo de necrose e falso negativo de
eritema exigem numeradores e denominadores de referência humana via
`EquityCounts`; amostra ausente e denominador zero permanecem indeterminados.

Essa análise é descritiva. RP em amostras preselecionadas de falha e controle não
equivale a risco populacional, causalidade ou validação clínica. Não há números
de desempenho ou resultados clínicos fabricados.

## Captura guiada

`GuidedCaptureValidator().validate(rgb, measurements, perilesional_mask=mask)`
recebe RGB `uint8` e máscara booleana da referência perilesional. A checagem de
nitidez usa variância do Laplaciano no recorte central, reduzido a no máximo
512 pixels no maior eixo. Iluminação compara quantis **dentro da referência da
própria pessoa**, com revisão explícita quando há variação intensa. Luminância
baixa isolada não estabelece sombra. Reflexo utiliza saturação branca técnica.

Os limiares em `CaptureThresholds` são parâmetros de pesquisa e precisam de
calibração/validação com dispositivos e tons de pele representativos. Pouca
textura também pode diminuir a métrica de nitidez; o resultado não certifica
adequação clínica.

Distância de 20–30 cm e ângulo frontal de 90° (tolerância técnica configurável)
exigem medida e fonte em `CaptureMeasurements`. Pixels não produzem centímetros;
orientação do aparelho sem referência ao plano da ferida não produz ângulo
clínico. Escala, enquadramento, fundo, privacidade, consentimento e remoção EXIF
são confirmações explícitas. O módulo não substitui a remoção real de metadados
feita pelo serviço de ingestão.

O resultado é `rejeitado` se alguma checagem falhar, `indeterminado` se faltarem
dados e nenhuma tiver falhado, ou `aceito` quando todas as checagens técnicas
forem satisfeitas. Não há afirmação de validade clínica.

## Comparação longitudinal

`TemporalHeatmap().compare(previous, current, alignment)` exige a mesma pessoa e
ferida e ordem cronológica. Cada `TemporalFrame` contém classes inteiras 0–4,
máscaras booleanas ROI/incerteza e `ScaleCalibration` independente. A escala deve
ser confirmada no mesmo plano, em mm ou cm; não é estimada de objetos na imagem.
Classes: 0 granulação, 1 esfacelo/fibrina, 2 necrose, 3 epitelização, 4 baixa
confiança. Frações teciduais usam somente pixels confiáveis e a fração excluída
é apresentada separadamente.

`AlignmentEvidence` contém pelo menos seis pares de correspondências anatômicas
revisadas e confirmação de comparabilidade aproximadamente planar. A homografia
RANSAC verifica distribuição dos pontos, inliers, reprojeção, orientação e
compatibilidade com as escalas métricas. Não substitui avaliação 3D de cavidades
ou de deformação anatômica. Sem evidência suficiente, não há mapa de calor.

O mapa compara somente a interseção alinhada confiável das duas visitas, exclui
classe 4 e pixels de incerteza, e apresenta alterações categóricas sem hierarquia
de melhora/piora. Áreas em mm² derivam da ROI geométrica anotada e escala de cada
visita; a área confiável é informada separadamente. A diferença de área aparente
não demonstra cicatrização. O contexto pré/pós-desbridamento acompanha o resultado.

Os testes de `tests/test_visual.py` utilizam apenas imagens e anotações sintéticas
e constituem evidência técnica, sem validação clínica ou aprovação ética implícita.
