# ADR-0003 — Preparo e envio de imagens clínicas no navegador

- Status: Aceita
- Data: 2026-08-10

## Contexto

Fotografias clínicas podem chegar com dimensões maiores que as necessárias, nomes identificáveis e metadados EXIF, inclusive modelo do dispositivo e coordenadas. Enviar o arquivo original aumenta uso de memória, tempo e exposição de dados sem melhorar a visualização usada pelo HEAL+.

## Decisão

- aceitar como entrada somente JPEG, PNG e WebP, com limite padrão de 10 MB por arquivo, configurável por `VITE_MAX_IMAGE_UPLOAD_MB` e igual ao limite do bucket;
- decodificar e reencodar cada imagem sequencialmente no navegador, limitando o maior lado a 2560 px e preservando a proporção;
- gerar WebP com qualidade 0,84; usar JPEG com qualidade 0,88 quando o navegador não conseguir codificar WebP;
- substituir o nome original por um identificador aleatório e usar somente os pixels no novo arquivo. A reencodificação remove EXIF, GPS, miniaturas e demais blocos de metadados que não fazem parte dos pixels;
- enviar os arquivos sequencialmente ao bucket privado e mostrar progresso por arquivo e por bytes;
- permitir cancelamento por `AbortSignal`. Uma tentativa cancelada não grava a avaliação e solicita a remoção dos objetos que ela já enviou;
- manter ROI normalizada, pois o redimensionamento preserva a proporção e as coordenadas relativas.

## Consequências

O tamanho e o pico de memória ficam limitados de forma previsível, e metadados desnecessários não chegam ao Storage. Há uma pequena perda controlada de compressão, aceitável para documentação e comparação visual; este preparo não classifica, diagnostica nem altera a imagem clinicamente. O navegador precisa oferecer Canvas 2D e uma das rotas de decodificação suportadas.

O cancelamento depende de conectividade suficiente para a limpeza no bucket. Políticas de retenção e uma rotina futura de reconciliação continuam recomendadas como defesa para interrupções abruptas do navegador.

## Alternativas consideradas

- Manter o arquivo original: rejeitado por preservar metadados e transferir bytes desnecessários.
- Processar neste fluxo pelo backend integrado: adiado; a redução local evita enviar metadados e bytes desnecessários antes do bucket privado sem mudar o contrato do backend.
- Usar upload resumível: adiado; o limite de 10 MB e a redução local tornam o upload padrão suficiente neste marco.

## Verificação

Testes unitários cobrem reencodificação, redimensionamento, nome gerado, progresso, cancelamento e limpeza. Testes de componente cobrem anúncio acessível e preservação do formulário após cancelamento. A validação manual usa exclusivamente imagens sintéticas.
