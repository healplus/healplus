/*
 * Modo de demonstração para eventos públicos (feiras, bancas, visitas).
 * Quando VITE_PRESENTATION_MODE=true, a navegação mostra apenas o fluxo
 * principal: cadastro, avaliação, comparação, relatórios e análise de imagem.
 * As rotas continuam protegidas por autenticação; o modo só simplifica o menu.
 */

/** Rotas que ficam fora do menu durante uma demonstração pública. */
export const routesHiddenInPresentation: ReadonlySet<string> = new Set([
  // Exige a chave pessoal do provedor de IA (BYOK); não deve ser exposta em público.
  '/chat',
  '/agenda'
]);

export function isPresentationMode() {
  return import.meta.env.VITE_PRESENTATION_MODE === 'true';
}

export function filterForPresentation<T extends { to: string }>(items: readonly T[], presentation = isPresentationMode()): T[] {
  return presentation ? items.filter(item => !routesHiddenInPresentation.has(item.to)) : [...items];
}
