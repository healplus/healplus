# Protocolo provisório de anotação multiclasse de tecidos

**Versão:** 0.1.0  
**Estado:** revisão clínica obrigatória  
**Finalidade:** pesquisa e desenvolvimento; não usar como decisão clínica.

## 1. Pré-condições

Anotar somente imagens autorizadas para pesquisa, pseudonimizadas e sem nome,
CPF, prontuário, endereço, rosto, tatuagem identificável, etiqueta hospitalar ou
localização EXIF. Não copiar imagens clínicas para tickets, documentos ou Git.

Antes do lote piloto, profissionais designados devem aprovar por escrito as
definições, os exemplos positivos e negativos e o processo de adjudicação. A
imagem original permanece imutável; a máscara é um arquivo novo, indexado,
monocanal e com a mesma largura e altura.

## 2. Valores da máscara

| Valor | Nome | Regra operacional provisória |
| ---: | --- | --- |
| 0 | fundo/região externa | todo pixel seguramente fora do leito da ferida |
| 1 | granulação | região do leito julgada compatível com granulação |
| 2 | esfacelo/fibrina | região do leito julgada compatível com esfacelo ou fibrina |
| 3 | necrose/escara | região do leito julgada compatível com necrose ou escara |
| 255 | ignorar/incerto | não há evidência visual suficiente ou existe artefato/oclusão |

As descrições são operacionais e provisórias. Aparência isolada de cor não é
suficiente para criar um rótulo. Anotadores não devem inferir etiologia,
infecção, prognóstico, profundidade ou diagnóstico a partir da fotografia.

## 3. Ordem de anotação

1. Verificar autorização, identidade pseudônima e integridade do arquivo.
2. Marcar a região total da ferida na máscara binária, sem alterar a imagem.
3. Dentro dessa região, marcar somente tecidos visualmente defensáveis.
4. Usar 255 em transições ambíguas, oclusões ou artefatos.
5. Executar o validador; corrigir valores, resolução e regiões fora da ferida.
6. Registrar versão do protocolo, anotador pseudônimo e estado de revisão em
   manifesto separado, nunca no nome do arquivo.

## 4. Regras para limites e áreas mistas

- Usar zoom uniforme e evitar borda artificialmente serrilhada.
- Delimitar pela evidência visível; não completar tecido escondido.
- Em mosaicos de tecidos, marcar cada região apenas se houver área observável
  suficiente. Misturas abaixo da resolução confiável recebem 255.
- Pixels de transição sem decisão reproduzível recebem 255; não criar uma
  “classe mista”.
- A máscara tecidual não pode ultrapassar a máscara binária aprovada da ferida,
  salvo o valor 255 usado para sinalizar desacordo de limite.

## 5. Artefatos e situações especiais

- **Brilho especular:** 255 quando encobre a textura; não classificar
  automaticamente como esfacelo.
- **Sangue:** classificar tecido somente se ele continuar visível; sangue que
  cobre a região recebe 255, não granulação automática.
- **Curativo, gaze, régua, luva ou objeto:** 0 se fora da ferida; 255 se ocluir o
  leito.
- **Pele periférica:** 0 nesta taxonomia; não é uma classe tecidual.
- **Região desfocada:** 255 quando o tecido não puder ser distinguido.
- **Sombra:** 255 se impedir avaliação; não classificar automaticamente como
  necrose.
- **Superexposição:** 255 nas áreas saturadas sem detalhe.
- **Subexposição:** 255 nas áreas sem detalhe recuperável.
- **Reflexo de flash:** manter a imagem original e usar 255 onde houver perda de
  informação. Uma versão experimental corrigida nunca substitui o rótulo da
  original.
- **Borda parcialmente fora do quadro:** marcar o que está visível e usar 255 na
  transição truncada; sinalizar a captura para revisão.
- **Epitelização:** 255 até existir definição, exemplos e aprovação específicos.

## 6. Quando usar 255

Usar 255 quando dois anotadores treinados possam, de forma razoável, escolher
classes diferentes devido à fotografia; quando um artefato encobre o tecido; ou
quando o protocolo não cobre o caso. Não usar 255 apenas para economizar tempo.
Uma taxa elevada de 255 deve gerar revisão da imagem, do treinamento do anotador
ou da taxonomia.

## 7. Dupla anotação e concordância

Selecionar o piloto antes de iniciar o lote, buscando diversidade de classe,
dispositivo, tamanho, qualidade de captura e, quando autorizado, tons de pele.
O tamanho será definido após conhecer pacientes e prevalências; a seleção deve
ser por paciente, não por fotografias correlacionadas.

Dois anotadores trabalham independentemente e sem visualizar a máscara do
outro. A comparação exclui pixels 255 de qualquer anotador e relata:

- Dice e IoU por classe;
- matriz de confusão por pixel;
- Cohen’s Kappa, acompanhada das prevalências;
- proporção de pixels ignorados;
- frequência e mapa de desacordos por classe e por caso.

Não definir um corte clínico arbitrário antes do piloto. Os resultados orientam
treinamento e revisão do manual. Casos discordantes são adjudicados por
profissional designado, com motivo codificado, sem apagar as máscaras originais.

Manifesto mínimo da dupla anotação:

```csv
sample_id,mask_a,mask_b
sample-pseudonimo,masks/a/sample.png,masks/b/sample.png
```

Execução:

```powershell
python ml/scripts/evaluate_annotation_agreement.py `
  --dataset-root C:\caminho\autorizado `
  --manifest C:\caminho\autorizado\dupla_anotacao.csv `
  --output-dir ml/outputs/annotation_agreement `
  --fail-on-invalid-pairs
```

Os relatórios contêm apenas IDs derivados por hash, resultados agregados e
códigos de erro; não contêm caminhos originais nem imagens.

## 8. Controle de versão e rastreabilidade

Cada registro de máscara deve conter no manifesto:

- `sample_id` pseudônimo;
- caminho relativo da imagem e da máscara;
- hash SHA-256 do arquivo original;
- versão da taxonomia e do protocolo;
- token do anotador;
- data UTC;
- estado `draft`, `double_annotated`, `adjudicated` ou `approved`;
- token do revisor e códigos de desacordo, quando aplicável.

Alterações após aprovação geram nova versão de máscara. Nunca sobrescrever a
versão anterior e nunca usar pseudo-rótulo como máscara humana.

Para revisar localmente uma amostra sem registrar caminhos ou nomes no CSV:

```powershell
python ml/scripts/review_segmentation_masks.py `
  --dataset-root C:\caminho\autorizado `
  --manifest C:\caminho\autorizado\manifest.csv `
  --max-samples 20 `
  --allow-local-clinical-previews
```

As teclas são: setas para navegar, `A` para aprovar, `R` para solicitar revisão,
`I` para invalidar e `Q` para sair. Um mosaico local pode ser criado acrescentando
`--contact-sheet C:\pasta\autorizada\mosaico.png`; esse arquivo contém dados
clínicos e não deve ser anexado ao Git.

## 9. Critério de conclusão do piloto

O piloto termina quando as definições foram aprovadas, os casos incertos foram
catalogados, a concordância foi calculada por classe, o processo de adjudicação
funcionou e o responsável clínico decidiu manter, unir, dividir ou adiar cada
classe. Só então a taxonomia pode mudar para `approved`.
