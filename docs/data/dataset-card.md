# Data Sheet — imagens de feridas do HEAL+

## Estado verificado

No worktree auditado em 27 de julho de 2026 não há dataset clínico versionado em
`data/`, `dataset/`, `datasets/` ou `ml/datasets/`. Portanto, não é possível
confirmar quantidade, pacientes, feridas, classes, licença ou qualidade das
máscaras.

Uma versão anterior deste documento afirmava haver mais de 1.200 arquivos
Medetec em `dataset/medetec/`. Essa pasta não existe no estado atual e a
afirmação histórica não deve ser usada como evidência.

## Arquivos deliberadamente excluídos

Foram localizadas 55 imagens em `output/uploads`. Elas não foram abertas como
dataset de pesquisa nem incorporadas à auditoria porque:

- podem ser dados clínicos sensíveis enviados ao produto;
- não há manifesto de consentimento, origem ou licença;
- não há máscaras pareadas ou grupos pseudonimizados;
- dados operacionais não devem ser reutilizados para treino silenciosamente.

## Finalidade pretendida

Pesquisa e desenvolvimento de:

- segmentação binária de ferida;
- segmentação experimental de granulação, esfacelo/fibrina e necrose/escara;
- controle de qualidade de captura;
- avaliação de incerteza e revisão profissional.

Nenhum modelo produzido deve ser considerado diagnóstico ou validado para uso
clínico apenas por desempenho retrospectivo.

## Pré-requisitos para registrar uma versão

- base legal, consentimento e aprovação ética/institucional aplicáveis;
- licença e origem por fonte;
- política de acesso, retenção e exclusão;
- imagens pseudonimizadas e EXIF sensível removido;
- IDs pseudônimos de paciente e ferida;
- hashes, versões e cadeia de curadoria;
- máscaras binárias e/ou multiclasse sem sobrescrever originais;
- taxonomia aprovada e versão do protocolo;
- dispositivo, instituição e sequência temporal quando autorizados;
- atributos de equidade somente com autorização e quantidade suficiente.

## Manifesto mínimo

O manifesto deve ser armazenado fora de áreas públicas quando contiver
informações sensíveis. Campos mínimos:

```text
sample_id,image_path,mask_path,image_sha256,patient_id,lesion_id,split,
source,license_or_consent_ref,device_id,captured_at_utc,taxonomy_version,
annotation_state
```

Não usar nome, CPF, prontuário ou outro identificador direto.

## Auditoria reproduzível

```powershell
python ml/scripts/audit_segmentation_dataset.py `
  --dataset-root C:\caminho\autorizado `
  --manifest C:\caminho\autorizado\manifest.csv `
  --output-dir ml/outputs/segmentation_audit `
  --fail-on-blockers
```

A auditoria não altera as fontes e não gera previews clínicos. O relatório usa
tokens derivados por hash, detecta arquivos ausentes/corrompidos, valores de
máscara, qualidade básica, duplicatas e vazamento de paciente/ferida.

## Divisão e avaliação

A prioridade de agrupamento é paciente, depois ferida. Fotografias da mesma
pessoa ou ferida não podem cruzar treino, validação e teste. Com dados
suficientes, usar cinco folds estratificados por grupos e uma coorte externa
bloqueada.

Resultados devem declarar origem, versão, exclusões, prevalência, pior classe,
variação entre folds e limitações. Comparações entre versões exigem os mesmos
splits.

## Limitações atuais

- zero pares de imagem/máscara disponíveis no worktree;
- taxonomia multiclasse ainda provisória;
- nenhuma dupla anotação;
- nenhum split verificável;
- nenhum resultado de treino multiclasse;
- nenhuma avaliação externa ou prospectiva.

Até que esses itens sejam resolvidos, o nível máximo é **Nível 0 — protótipo
técnico**.
