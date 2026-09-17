# Referência rápida — anotação tecidual v0

**Uso experimental. Taxonomia ainda não aprovada.**

| Valor | Marcar quando | Não confundir com |
| ---: | --- | --- |
| 0 | seguramente fora do leito | pele periférica não é tecido da ferida nesta versão |
| 1 | granulação visualmente defensável | sangue sobreposto |
| 2 | esfacelo/fibrina visualmente defensável | brilho/flash |
| 3 | necrose/escara visualmente defensável | sombra |
| 255 | dúvida, transição, desfoque, saturação ou oclusão | uma classe “mista” |

Checklist:

1. Confirme imagem autorizada e pseudonimizada.
2. Preserve a imagem original.
3. Use máscara monocanal, mesma resolução e apenas `0,1,2,3,255`.
4. Não marque tecido fora da máscara binária aprovada.
5. Objeto ou sangue que cobre o leito: `255`.
6. Epitelização: `255` até aprovação clínica.
7. Salve como nova versão; não sobrescreva máscara aprovada.
8. Envie dúvidas para adjudicação, sem dados identificáveis.
