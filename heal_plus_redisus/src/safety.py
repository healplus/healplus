"""Single source of the mandatory clinical limitation notice (RN07/RF17)."""

from typing import Final

ASSISTIVE_DISCLAIMER: Final[str] = (
    "O HEAL+ é uma ferramenta de apoio ao registro, acompanhamento e análise evolutiva de feridas. "
    "As informações apresentadas pelo sistema, incluindo imagens, relatórios, percentuais teciduais "
    "e eventuais resultados de inteligência artificial, não substituem avaliação, diagnóstico, "
    "prescrição, estadiamento ou decisão de profissional de saúde habilitado. Qualquer interpretação "
    "clínica deve ser realizada por profissional responsável, considerando o contexto completo do paciente."
)

TISSUE_CLASSES: Final[tuple[str, ...]] = (
    "granulacao",
    "esfacelo_fibrina",
    "necrose",
    "epitelizacao",
    "nao_classificado_baixa_confianca",
)
