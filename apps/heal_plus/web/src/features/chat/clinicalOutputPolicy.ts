export const CLINICAL_AI_REVIEW_NOTICE =
  'Apoio à decisão: esta resposta exige revisão profissional e não constitui diagnóstico ou prescrição.';

const SECRET_OR_PROMPT_PATTERNS = [
  /\bsk-[a-z0-9_-]{12,}\b/i,
  /\bAIza[a-z0-9_-]{20,}\b/i,
  /\bBearer\s+[a-z0-9._~-]{12,}\b/i,
  /\b(system prompt|prompt do sistema|instruções internas)\b/i
] as const;

const AUTONOMOUS_CLINICAL_PATTERNS = [
  /\bdiagnóstico (?:definitivo|confirmado|é)\b/i,
  /\b(?:eu )?prescrevo\b/i,
  /\btome\s+\d+(?:[.,]\d+)?\s*(?:mg|g|ml|comprimidos?)\b/i,
  /\bantibiótico obrigatório\b/i
] as const;

export interface ClinicalOutputValidation {
  blocked: boolean;
  flags: readonly ('autonomous_clinical_claim' | 'secret_or_prompt_disclosure')[];
  text: string;
}

export function validateClinicalAiOutput(rawText: string): ClinicalOutputValidation {
  const text = rawText.trim();
  if (!text) {
    return {
      blocked: true,
      flags: ['autonomous_clinical_claim'],
      text: `O provedor não retornou conteúdo clínico utilizável.\n\n${CLINICAL_AI_REVIEW_NOTICE}`
    };
  }

  if (SECRET_OR_PROMPT_PATTERNS.some(pattern => pattern.test(text))) {
    return {
      blocked: true,
      flags: ['secret_or_prompt_disclosure'],
      text:
        'A resposta foi bloqueada porque pode expor credenciais ou instruções internas. ' +
        `Reformule a solicitação sem pedir segredos ou configuração do sistema.\n\n${CLINICAL_AI_REVIEW_NOTICE}`
    };
  }

  if (AUTONOMOUS_CLINICAL_PATTERNS.some(pattern => pattern.test(text))) {
    return {
      blocked: true,
      flags: ['autonomous_clinical_claim'],
      text:
        'A resposta foi reformulada porque apresentava diagnóstico ou prescrição autônoma. ' +
        `Confirme os achados, riscos e próximos passos com avaliação profissional presencial.\n\n${CLINICAL_AI_REVIEW_NOTICE}`
    };
  }

  return {
    blocked: false,
    flags: [],
    text: `${text}\n\n${CLINICAL_AI_REVIEW_NOTICE}`
  };
}
