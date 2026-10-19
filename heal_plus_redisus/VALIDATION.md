# Evidências técnicas das Sprints 1 e 2

Verificação local em 19 de outubro de 2026, no Windows, com Python 3.14.3, OpenCV 4.13.0, Pydantic 2.12.5 e PyTorch 2.11.0 CPU. Somente dados sintéticos foram usados nos testes novos e na demonstração.

| Verificação | Resultado observado |
|---|---|
| Testes novos de domínio, privacidade, pesquisa, CV, persistência, FHIR e integração | 231 passaram |
| Regressões existentes de qualidade de imagens, FHIR e métricas | 72 passaram |
| Rodada combinada | **303 passaram em 57,15 s** |
| Ruff check e format check | Passaram |
| Mypy | Passou nos 23 arquivos de `src/` |
| Compileall | Passou |
| Demonstração ponta a ponta | Executou e gerou Bundle com sete recursos, banco sintético, métricas, snapshots e painel |
| Painel de seis colunas | Inspecionado visualmente, incluindo o aviso oficial integral |

Comando da rodada combinada:

```powershell
python -m pytest heal_plus_redisus/tests tests/test_image_quality.py tests/test_fhir_r4_layer.py tests/test_segmentation_metrics.py -q
```

As regressões verificam o decoder compartilhado, a camada FHIR existente e as métricas. Os testes novos incluem EXIF/orientação, MIME e limites, ausência de consentimento, troca de usuário/instituição, revisores profissionais, vínculos de imagem, alterações concorrentes, checkpoint e SHA, ROIs múltiplas, abstenção e sobreposição, limiares de incerteza, captura, estratos cutâneos, denominadores desconhecidos, alinhamento temporal e integridade das anotações congeladas. A rastreabilidade e os critérios que exigem evidência humana estão em `config/validation_matrix.json`.

A demonstração final foi executada com:

```powershell
python -m heal_plus_redisus --output artifacts/generated/heal-sprints-evidence-20261019
```

Saídas locais, intencionalmente ignoradas pelo Git:

- `artifacts/generated/heal-sprints-evidence-20261019/synthetic-bundle.json`
- `artifacts/generated/heal-sprints-evidence-20261019/sprint2-summary.json`
- `artifacts/generated/heal-sprints-evidence-20261019/experiment/manifest.json`
- `artifacts/generated/heal-sprints-evidence-20261019/experiment/inputs.json`
- `artifacts/generated/heal-sprints-evidence-20261019/experiment/experiment_run.json`
- `artifacts/generated/heal-sprints-evidence-20261019/experiment/panels/20000000-0000-4000-8000-000000000001.png`

O manifesto registra runtime e digest do código; o snapshot de insumos e configuração é vinculado por `annotations_sha256`. A demonstração não possui pesos: D/E, Dice zero e 100% de incerteza são o comportamento esperado de abstenção segura, e não uma medida de eficácia de um modelo treinado. Os recursos FHIR foram validados estruturalmente pelo schema offline R4 4.0.1 e pelas verificações de referência do exportador.

Não foram executados estudos com pacientes, avaliação clínica, benchmark com bases reais, homologação RNDS, testes de câmera/dispositivo, teste de usabilidade com profissionais ou CI remoto. O workflow foi acrescentado, mas não publicado/executado remotamente nesta tarefa. O frontend existente não foi alterado. As alterações locais anteriores à tarefa foram preservadas.

> O HEAL+ é uma ferramenta de apoio ao registro, acompanhamento e análise evolutiva de feridas. As informações apresentadas pelo sistema, incluindo imagens, relatórios, percentuais teciduais e eventuais resultados de inteligência artificial, não substituem avaliação, diagnóstico, prescrição, estadiamento ou decisão de profissional de saúde habilitado. Qualquer interpretação clínica deve ser realizada por profissional responsável, considerando o contexto completo do paciente.
