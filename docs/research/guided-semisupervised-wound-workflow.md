# Anotação guiada e treino semissupervisionado de feridas

Este fluxo é uma aplicação Python local, sem frontend web. Ele foi criado para
anotar pelo menos 100 máscaras binárias com supervisão humana e depois treinar
um modelo professor-aluno com augmentation.

O resultado é experimental e requer revisão profissional. Ele não diagnostica
feridas nem está validado para uso clínico.

## Execução rápida no Windows

Abra o PowerShell na raiz do projeto:

```powershell
.\scripts\run_wound_annotation.ps1
```

Um seletor pedirá a pasta exata das imagens. Não selecione `Downloads` inteiro
ou outra pasta com fotografias pessoais misturadas.

Também é possível indicar a pasta diretamente:

```powershell
.\scripts\run_wound_annotation.ps1 `
  -Images "C:\caminho\autorizado\imagens" `
  -Workspace "C:\caminho\local\healplus-anotacoes"
```

O `Workspace` não deve estar dentro de OneDrive, Google Drive, Git ou outra
pasta publicada. Se ele for omitido, será usado
`ml/outputs/guided_wound_workflow`, que já é ignorado pelo Git.

Execução direta e configurável:

```powershell
python ml/scripts/run_guided_semisupervised_wound.py `
  --images "C:\caminho\autorizado\imagens" `
  --workspace "C:\caminho\local\healplus-anotacoes" `
  --target-human 100 `
  --pseudo-review-count 20 `
  --teacher-epochs 15 `
  --student-epochs 15 `
  --device auto `
  --confirm-authorized-data
```

Fechar a janela antes da meta não perde o progresso. Execute o mesmo comando
novamente para continuar.

## Como usar a janela

1. Mantenha o modo **Adicionar**.
2. Pressione o botão esquerdo e contorne a ferida; solte para preencher.
3. Faça outros contornos para acrescentar regiões separadas.
4. Use **Apagar** e contorne uma área incluída por engano.
5. Confira a máscara e o overlay.
6. Clique **Aprovar e próxima**.

Controles:

- `A`: aprovar e avançar;
- `E`: modo apagar;
- `+`: modo adicionar;
- `Ctrl+Z` ou Backspace: desfazer;
- seta direita ou `N`: deixar pendente e avançar;
- seta esquerda: imagem anterior;
- `Q` ou Esc: salvar o que já foi aprovado e sair.

Uma máscara vazia ou ocupando mais de 95% da fotografia não pode ser aprovada.

## Automação executada

### 1. Preparação segura

- busca imagens recursivamente;
- ordena nomes numericamente;
- remove duplicatas exatas por SHA-256;
- corrige orientação EXIF;
- cria PNGs RGB sem EXIF e com nomes pseudônimos;
- não modifica as imagens originais;
- grava progresso sem caminhos ou nomes originais.

### 2. Primeira rodada humana

As primeiras 100 máscaras são sempre humanas. A ferramenta não promove
pseudo-rótulo a ground truth.

### 3. Data augmentation

O treino aplica, de forma sincronizada à imagem e à máscara:

- flip horizontal;
- rotação de até 15 graus;
- pequenas alterações de brilho, contraste e saturação.

As transformações são geradas em memória a cada época; não são duplicadas como
novos pacientes. Uma grade local com 20 exemplos é salva como
`augmentation_preview_20.png`.

### 4. Modelo professor

Uma U-Net compacta é treinada somente nas máscaras aprovadas por humanos.
Não há conjunto de teste ou validação por imagem neste fluxo, porque não foram
fornecidos IDs de paciente/ferida. A loss de treino não deve ser interpretada
como evidência de desempenho.

### 5. Pseudo-rótulos

O professor processa as imagens restantes:

- probabilidade maior ou igual a 0,90: ferida;
- probabilidade menor ou igual a 0,10: fundo;
- região intermediária: `255`, ignorada pela loss;
- máscaras com pouca confiança ou área implausível são rejeitadas;
- pseudo-rótulos ficam separados das máscaras humanas;
- cada pseudo-rótulo registra modelo, confiança e estado de revisão.

### 6. Segunda rodada humana

Por padrão, 20 sugestões são apresentadas primeiro. É possível aprovar,
corrigir ou deixar pendente. Ao serem aprovadas, elas passam a ser máscaras
humanamente revisadas, mantendo a proveniência `human_reviewed_pseudo`.

### 7. Modelo aluno

O aluno começa nos pesos do professor e usa:

- peso `1.0` para máscaras aprovadas;
- peso `0.30` para pseudo-rótulos ainda não revisados;
- `255` ignorado na BCE e na Dice;
- mixed precision em CUDA;
- clipping de gradiente e scheduler cossenoidal.

## Saídas

```text
workspace/
  normalized_images/              # cópias sem EXIF
  human_masks/                    # máscaras aprovadas/pedentes
  pseudo_masks/                   # 0=fundo, 1=ferida, 255=incerto
  checkpoints/
    teacher_last.pt
    student_last.pt
  annotation_progress.json
  augmentation_preview_20.png
  pseudo_label_review_queue.csv
  pseudo_label_summary.json
  semi_supervised_pipeline_report.json
```

## Limitações

- O fluxo cria uma segmentação binária da região da ferida, não dos tecidos.
- Avaliação honesta ainda exige IDs pseudonimizados de paciente e ferida.
- O modelo não deve ser escolhido ou aprovado pela loss de treino.
- Imagens da mesma pessoa não podem ser separadas entre treino e teste futuro.
- Checkpoints treinados em dados privados devem permanecer sob controle de
  acesso.
- Data augmentation melhora diversidade aparente, mas não substitui novos
  pacientes, dispositivos ou tons de pele.
