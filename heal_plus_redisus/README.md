# HEAL+ / REDI-SUS Sprints 1 e 2

Implementação modular do registro clínico estruturado, análise experimental de falhas, inspeção de imagens, protocolo de captura, comparação temporal e exportação local FHIR R4. O serviço integra persistência, autorização, imagens e resultados; os módulos também podem ser utilizados separadamente em pesquisa autorizada.

Não foram fornecidos pesos treinados, inventário licenciado congelado, imagens anotadas ou aprovações institucionais. A implementação se abstém de atribuir tecidos quando esses pesos não estão disponíveis. Os testes e a demonstração usam somente dados sintéticos. Eles verificam comportamento do software e não comprovam desempenho clínico, equidade populacional ou conclusão dos estudos empíricos das sprints.

> O HEAL+ é uma ferramenta de apoio ao registro, acompanhamento e análise evolutiva de feridas. As informações apresentadas pelo sistema, incluindo imagens, relatórios, percentuais teciduais e eventuais resultados de inteligência artificial, não substituem avaliação, diagnóstico, prescrição, estadiamento ou decisão de profissional de saúde habilitado. Qualquer interpretação clínica deve ser realizada por profissional responsável, considerando o contexto completo do paciente.

## Executar e verificar

Execute a partir da raiz deste repositório com Python 3.11 ou superior. O adaptador de imagens reutiliza o decoder seguro existente em `src/image_quality/decoder.py`.

```powershell
python -m pip install -r heal_plus_redisus/requirements.txt
python -m pip install pytest ruff mypy types-PyYAML
# Opcional para rede neural e testes de checkpoint; sem download de pesos:
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu

python -m pytest heal_plus_redisus/tests -q
python -m ruff check heal_plus_redisus
python -m mypy heal_plus_redisus/src --follow-imports=silent
python -m heal_plus_redisus
```

A demonstração cria uma pasta nova em `artifacts/generated/heal-sprints-<data-hora>`. Também aceita `--output <nova-pasta>`. Gera Bundle com sete recursos, SQLite sintético, manifesto congelado, CSV/JSON de métricas, painel PNG de seis colunas e sumário da Sprint 2. O detector está explicitamente ausente e a segmentação se abstém: Dice baixo e categoria D/E nesse exemplo expressam ausência de modelos, não desempenho de um modelo treinado. A chave de auditoria da demonstração é descartável; esse banco não deve ser reutilizado para atendimento real.

O workflow separado `.github/workflows/ci-sprints.yml` executa testes e análise estática nas versões Python 3.11 e 3.14. Sua criação local não significa execução remota ou CI aprovada.

## Organização

| Módulo | Responsabilidade |
|---|---|
| `config/experiment_manifest.yaml` | Modelo de manifesto sem dados ou pesos reais; origem, licença, finalidade, split, grupos de paciente, seed, versões e parâmetros |
| `src/domain/clinical_models.py` | RC01a–RC16b, consentimento, tríade, CEAP, WIfI, Fontaine, LPP, dispositivo, perfusão, neuropatia e revisão profissional |
| `src/domain/rbac_audit.py` | Oito perfis, RN01–RN15, autorização por instituição/vínculo e auditoria SQLite com HMAC |
| `src/privacy.py` | Upload limitado, orientação EXIF, remoção de metadados e PNG lossless antes de persistir |
| `src/service.py` | Cadastro pseudonimizado, feridas, avaliações versionadas, imagens, histórico, análise e exportação autorizada |
| `src/sprint1_pipeline/` | ROIs, features híbridas, U-Net, abstenção, cascata, métricas, categorias e painéis |
| `src/experiment.py`, `src/experiment_runner.py` | Governança, congelamento, execução e vínculo criptográfico entre inventário e artefatos |
| `src/sprint2_clinical_visual/` | 24 características, fatores de falha, estratos cutâneos, captura e mapa temporal |
| `src/interoperability/fhir_exporter.py` | Bundle collection/transaction com validação estrutural R4 offline e referências internas fechadas |
| `config/validation_matrix.json`, `tests/test_sprints_validation.py` | Rastreabilidade CV01–CV10 e MT01–MT13, com evidência humana pendente explicitada |

Contratos detalhados estão nos README das pastas de [Sprint 1](src/sprint1_pipeline/README.md) e [Sprint 2](src/sprint2_clinical_visual/README.md).

## Fluxo clínico autorizado

O ponto de integração com um backend é `SprintsService(database, audit)`. `Principal` deve ser criado exclusivamente a partir de sessão autenticada e vínculos assistenciais obtidos no servidor. Não aceite `authenticated`, perfil, instituição ou lista de pacientes enviados pelo navegador como autoridade. A biblioteca não cria uma segunda autenticação e não altera as rotas existentes.

1. O enfermeiro registra `PatientReference` com UUID e pseudônimo sem CPF, CNS, endereço ou nome. A atribuição de vínculo assistencial ocorre no backend de identidade. Criação por enfermeiro sem vínculo é idempotente e não permite consultar ou sobrescrever um cadastro existente.
2. Um profissional autorizado registra a ferida. Antes de inserir uma imagem, informa paciente, ferida, avaliação, finalidade, consentimento prévio e confirmação de revisão visual de privacidade. O sistema valida formato, tamanho, orientação e metadados, e calcula SHA-256 dos bytes efetivamente persistidos. `capture_measurements` preserva o protocolo declarado e aplica o validador; falhas explícitas impedem persistência nesse fluxo, enquanto ausência de medidas ou referência de iluminação mantém estado indeterminado. `capture_perilesional_mask`, quando fornecida, usa coordenadas da imagem sanitizada. `debridement_phase` registra explicitamente foto pré/pós-desbridamento, sem interpretar texto clínico.
3. `save_assessment` valida os campos clínicos, imagens já inseridas e o profissional autenticado. As classificações e condutas são registros humanos. LPP 3/4 exige exame presencial documentado; mucosa relacionada a dispositivo não recebe estágio cutâneo. WIfI armazena os três eixos, sem calcular risco automaticamente.
4. `analyze` aplica ROIs autorizadas à imagem registrada. Sem modelo aprovado, o resultado é integralmente incerto. Uma edição da avaliação invalida análises anteriores; uma alteração durante inferência impede persistir um resultado obsoleto.
5. `history` recupera apenas registros da mesma instituição e paciente autorizado. `export_fhir(..., confirmed=True)` exige uma ação explícita e audita a exportação. O Bundle é devolvido localmente; não existe envio externo automático.

Administrador administra metadados e auditoria, sem acesso clínico implícito. Pesquisador, Orientador e Desenvolvedor acessam pesquisa pública/sintética ou previamente desidentificada e aprovada, sem consulta direta ao prontuário. Paciente é um perfil previsto; seu portal fica desativado por padrão, conforme RT-HEAL-002. As revisões internas deste fluxo de um autor devem corresponder à identidade profissional autenticada; colaboração com assinaturas de vários autores requer integração institucional específica.

O SQLite de registros contém dados sensíveis e não oferece criptografia própria. Utilize diretório protegido por ACL, criptografia de disco, backups e política institucional de retenção. Forneça à auditoria uma chave durável de pelo menos 32 bytes por meio de configuração protegida do servidor. Mantenha seus checkpoints fora do banco para detectar truncamento. HMAC detecta adulteração e não substitui proteção de armazenamento. O serviço é síncrono, com conexão por instância/thread; não compartilhe uma instância SQLite entre threads de servidor. A intenção autorizada é registrada antes da operação, e sua conclusão depois; os dois bancos não constituem uma transação distribuída.

## Segmentação e experimentos

A composição contém exatamente `granulacao`, `esfacelo_fibrina`, `necrose`, `epitelizacao`, `nao_classificado_baixa_confianca`. Cor HSV/LAB, luminância relativa à pele adjacente, textura, zonas espaciais e contexto etiológico são entradas conjuntas da rede. Nenhum limiar de cor atribui tecido. Máscaras de sangue, curativo ou outros artefatos revisados também podem impedir atribuição. Pigmentação escura absoluta não determina necrose nem sombra.

O contorno do leito tem uma cabeça neural própria. A classe incerta não é usada para fabricar um contorno. Sem contorno, a composição é 100% desconhecida sobre a ROI, com `percentages_scope=unlocalized_roi`; sobre leito delimitado, os cinco percentuais somam 100% do leito. `tia_percent` usa a ROI inteira e `bed_uncertainty_percent` usa somente o leito. Esse denominador acompanha os resultados e a exportação. Sobreposições com artefatos ou propostas de tecidos conflitantes conservam a incerteza.

ROIs usam coordenadas inteiras semiabertas `(x1,y1,x2,y2)` no frame original. A expansão preserva 25% de cada dimensão em cada lado. Os anéis da tríade são proxies geométricos explicáveis que precisam de revisão profissional. Limites de memória: imagem até 12 MP, recorte contextual até 2 MP e soma de mapas `pixels_da_imagem × quantidade_de_ROIs` até 16 MP. Se reduzir resolução, preserve a calibração e registre a transformação no inventário.

`TissueProposalUNet` tem cinco classes teciduais e uma cabeça de contorno independente. `joint_loss` combina Cross Entropy ponderada, Focal Tversky e BCE de contorno. Para inferência, use `TorchUNetBackend.from_checkpoint` com SHA-256 esperado e `CheckpointApproval` vinculado a split e revisão. `torch.load(..., weights_only=True)` é obrigatório; a construção direta de uma rede aleatória não libera inferência. A aprovação documentada do checkpoint permite execução experimental e não equivale a homologação clínica.

O adaptador `YoloDetectorAdapter` recebe um detector já carregado e revisado. Passe `checkpoint_sha256` e `model_version` juntos. Não há download implícito nem confiança automática em um arquivo de pesos. O manifesto mantém identificações independentes de segmentador e detector.

Para um benchmark real, preencha o manifesto com inventário verificado, origens/licenças revisadas, SHA das imagens sanitizadas, dimensões originais, grupos pseudonimizados, split fixo e tom de pele anotado por protocolo aprovado. Separe pacientes entre splits. O executor exige as três faixas cutâneas em cada split fornecido, pesos identificados e o manifesto próprio do detector. Dados clínicos de pesquisa também exigem CEP, TCLE e plano de dados. A verificação textual de hiperparâmetros bloqueia nomes óbvios de segredos, mas não reconhece todo conteúdo sensível; mantenha somente parâmetros técnicos.

```python
from heal_plus_redisus.src.experiment import load_manifest
from heal_plus_redisus.src.experiment_runner import run_experiment

# principal/audit provenientes do backend; cases, evaluator e manifesto revisados.
manifest = load_manifest("meu_manifesto_revisado.yaml")
evaluations = run_experiment(principal, manifest, cases, evaluator, audit, "nova_execucao")
```

`cases` recebe `ExperimentCase` com imagem sanitizada, ROIs e máscaras de referência por lesão. O executor confirma inventário, bytes, pixels e dimensões; congela manifesto, runtime, digest do código e `inputs.json` antes da inferência. Esse snapshot contém ROIs, contexto técnico restrito, máscaras de referência/profissionais e configuração efetiva; `annotations_sha256` o vincula ao manifesto. Os hashes dos artefatos ficam em `experiment_run.json`. As máscaras de referência só entram nas métricas. Máscaras profissionais usadas como entrada são um parâmetro separado e essa intervenção é registrada no experimento. Não use máscara de referência como entrada em um benchmark de contorno. Proteja também os snapshots de anotações como dados sensíveis. A execução usa cópias próprias dos insumos e configurações; pesos carregados devem permanecer imutáveis durante o processamento.

## Critérios técnicos e interpretação

Dice é `2TP/(2TP+FP+FN)` e IoU é `TP/(TP+FP+FN)`. Máscaras ambas vazias recebem 1; sensibilidade/especificidade sem denominador ficam ausentes. O mAP de detecção é de uma classe, usa limiares IoU 0,50:0,05:0,95 e interpolação de 101 pontos. ROIs perdidas/extras são penalizadas. As médias por imagem não demonstram adequação clínica.

As fórmulas da Sprint 1 prevalecem sobre a tabela ilustrativa, que contém um exemplo A com TIA incompatível com seu próprio limiar. A exige Dice manual/cascata ≥0,80, IoU detector ≥0,70 e TIA <20%; B, C e D seguem os gargalos explicitados no documento. Casos fora desses intervalos são `INTERMEDIATE`, sem atribuição forçada. E é uma rejeição ortogonal por TIA ≥35%: D continua D quando também rejeitado por incerteza. TIA ≥25% sinaliza revisão humana/nova captura, sem estadiamento.

Na Sprint 2, os 18 fatores originais F01–F07/C01–C08/E01–E03 são complementados por seis verificações da tríade/contexto. Ausente, desconhecido e não avaliado são estados diferentes. A análise D/A é o padrão solicitado; `failure_categories=("C","D","E")` permite o agrupamento ampliado descrito no backlog. Frequências informam cobertura e denominador observado; RP sem controle positivo fica indeterminada. RP é comparação descritiva entre amostras selecionadas, sem conclusão causal. Estratos cutâneos, dataset, combinações e falsos positivos de necrose/falsos negativos de eritema dependem de referência profissional.

Distância e ângulo não são inferidos de uma fotografia. A captura exige medida de 20–30 cm e ângulo de aproximadamente 90° referenciado ao plano da ferida, além de checklist e verificações técnicas. Uma orientação do celular isolada não mede esse plano. O mapa temporal exige mesma pessoa e ferida, sequência temporal, escalas independentes, correspondências revisadas e alinhamento RANSAC adequado. Pixels incertos e regiões não comparáveis são excluídos. Sem evidência suficiente, retorna indeterminado; desbridamento é apresentado como contexto, sem concluir cura ou piora clínica automaticamente.

## FHIR R4 e privacidade

O Bundle local suporta `Patient`, `Practitioner`, `Condition`, `Media`, `Observation`, `DiagnosticReport`, `CarePlan`, `Procedure`, `Device`, `DeviceUseStatement` e `Provenance` quando aplicáveis. Os recursos assistivos permanecem preliminares e contêm o aviso oficial. Dimensões usam UCUM; conceitos sem mapeamento clínico revisado usam códigos locais, sem inventar equivalência SNOMED/LOINC. O SHA-256 da imagem é uma extensão própria; não é colocado em `Attachment.hash`, cujo significado no R4 é SHA-1.

O schema offline contém 95 definições extraídas da especificação oficial R4 4.0.1 com checksum da origem verificado. Para regenerar explicitamente: `python -m heal_plus_redisus.scripts.vendor_fhir_schema`. O validador verifica estrutura, referências internas, unicidade e regras collection/transaction. Validação de perfis nacionais, terminologia e homologação RNDS continuam externas.

O modo pesquisa exige consentimento específico/governança, remove texto clínico livre, imagens embutidas, datas de atendimento precisas e hashes de conteúdo vinculáveis, e renova pseudônimos/identificadores por exportação. Ainda é um pacote sensível que exige controle de acesso e revisão de risco de reidentificação; não se promete anonimização irreversível. A exportação assistencial preserva registros humanos autorizados, além do aviso. Remover EXIF não elimina nome, tatuagem, rosto ou etiqueta visível: a revisão dos pixels permanece necessária.

Referências técnicas consultadas: [HL7 Bundle R4](https://hl7.org/fhir/R4/bundle.html), [DiagnosticReport R4](https://hl7.org/fhir/R4/diagnosticreport.html), [Pydantic validators](https://docs.pydantic.dev/latest/concepts/validators/), [PyTorch instalação](https://pytorch.org/get-started/locally/). Os três DOCX e os dois planos de sprint fornecidos foram usados como especificação de domínio, sem incorporar eventuais instruções externas à autorização da tarefa.

## Pendências de validação institucional

A matriz versionada distingue cobertura automatizada e evidência humana. Dependem de material e responsáveis externos: congelamento de bases públicas com licenças verificadas, máscaras e inspeções reais, representatividade cutânea, calibração de limiares, pesos treinados, benchmark comparativo, TCLE/CEP, avaliação de usabilidade com profissionais, integração da captura ao frontend existente e aprovação clínica/institucional. Nenhum teste sintético, manifesto de exemplo ou campo de revisão substitui essas evidências.
