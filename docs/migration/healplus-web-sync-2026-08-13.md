# Migração seletiva do `healplus-web`

Data da auditoria: 2026-08-13

Origem: `pedrotescaro/healplus-web@12b3cfc` (`main`)

Destino: `healplus/healplus@0c57a74` (`develop`)

Branch de trabalho: `feature/sincronizar-healplus-web`

## Objetivo e limites

Esta migração incorpora as melhorias de experiência, segurança, persistência,
testes e operação desenvolvidas no repositório `healplus-web` sem transformar o
HEAL+/REDI-SUS em um produto independente e sem substituir módulos exclusivos
do monorepo.

Permanecem como fontes de verdade do destino:

- o conteúdo institucional REDI-SUS da landing page, incluindo instituições,
  parceiros, traduções, FAQ e rodapé;
- HEAL Analyzer, seus modos autenticado e independente e seus serviços de
  análise;
- chat/IA em modelo BYOK, relatórios avançados, Firebase, FHIR e integrações
  REDI-SUS/RNDS;
- o histórico Git do monorepo e o fluxo `branch curta -> PR -> develop`.

Os repositórios não compartilham ancestrais Git. A origem nasceu de uma cópia
do frontend, enquanto o destino continuou recebendo funcionalidades próprias.
Por isso, nenhum commit é aplicado por `cherry-pick` ou por cópia integral da
árvore: cada mudança é portada por hunk e validada contra o código atual.

## Legenda

- **Portado**: comportamento incorporado de forma equivalente.
- **Adaptado**: intenção incorporada respeitando a arquitetura REDI-SUS atual.
- **Já existente**: o destino já possui comportamento equivalente ou superior.
- **Não aplicável**: mudança conflitante com um limite explícito, mantida apenas
  como registro de auditoria.

O estado abaixo registra a decisão de migração. As evidências finais e eventuais
limitações são atualizadas nesta mesma branch após os testes.

## Inventário por commit da origem

| Commit | Autor | Decisão | Aplicação no monorepo |
| --- | --- | --- | --- |
| `dc205a1` | Pedro Tescaro | Já existente | Snapshot inicial usado apenas como base de comparação; não substitui a árvore do destino. |
| `1b27508` | Pedro Tescaro | Portado | Fundo interativo `DotField` no showcase de autenticação, preservando a mensagem REDI-SUS. |
| `a1dd4a5` | Pedro Tescaro | Portado | Showcase e partículas compatíveis com os temas claro e escuro. |
| `fff2f11` | Pedro Antonio Silvestre Tescaro | Adaptado | Somente melhorias técnicas compatíveis; copy independente e remoções de tipos/Analyzer são rejeitadas. |
| `ebff3f3` | Pedro Antonio Silvestre Tescaro | Adaptado | RLS, vínculos por usuário e Storage entram como migrações novas, não destrutivas e adequadas ao schema atual. |
| `509bb92` | Pedro Antonio Silvestre Tescaro | Adaptado | O frontend do monorepo mantém `envDir` na raiz, necessário ao layout `apps/heal_plus/web`; a correção é documentada e testada nesse contexto. |
| `67d1c39` | Pedro Antonio Silvestre Tescaro | Adaptado | Entregáveis úteis são integrados às fontes canônicas existentes, sem duplicar documentação acadêmica. |
| `69bdfa4` | Pedro Antonio Silvestre Tescaro | Adaptado | Governança compatível é incorporada às políticas existentes do monorepo. |
| `8f9fb2a` | Pedro Antonio Silvestre Tescaro | Adaptado | Upgrade de runtime é avaliado isoladamente para não quebrar Analyzer/chat nem colidir silenciosamente com PRs de dependências. |
| `46da638` | Pedro Antonio Silvestre Tescaro | Adaptado | Jornadas E2E permanecem sintéticas e são ajustadas ao diretório e às rotas do monorepo. |
| `0aa3fc1` | Pedro Antonio Silvestre Tescaro | Já existente | O README raiz do monorepo continua sendo a entrada do GitHub. |
| `fad7230` | Pedro Antonio Silvestre Tescaro | Adaptado | Referências úteis são ligadas à documentação REDI-SUS existente. |
| `7912f4a` | GRUPO HEAL+ | Adaptado | Diagnóstico de ambiente é migrado com caminhos e variáveis do monorepo. |
| `926d7bb` | GRUPO HEAL+ | Adaptado | Integridade documental é integrada aos checks existentes. |
| `2578e1a` | GRUPO HEAL+ | Não aplicável | A copy de produto independente conflita diretamente com o escopo REDI-SUS solicitado; nenhuma frase institucional é importada. |
| `e7f855f` | GRUPO HEAL+ | Portado | Callback de autenticação usa carregamento simples, estável e acessível. |
| `fed8db7` | GRUPO HEAL+ | Adaptado | Reparo de RLS é refeito sobre tabelas/políticas atuais, com isolamento entre usuários. |
| `023df2b` | GRUPO HEAL+ | Adaptado | Perfil é provisionado antes de atualizações parciais, sem alterar o contrato de autenticação do backend. |
| `1d80091` | PaulinhoLeal | Adaptado | Dicionário de dados persistidos é incorporado ao catálogo de dados do monorepo. |
| `65908c5` | GRUPO HEAL+ | Adaptado | Tokens, contraste, responsividade e acabamento visual são portados sem trocar a copy ou as instituições da landing. |
| `5192942` | GRUPO HEAL+ | Portado | Superfície azul suave do carregamento de autenticação. |
| `db050e4` | GRUPO HEAL+ | Adaptado | Dashboard, preferências, navegação e contraste são refinados preservando módulos exclusivos. |
| `df3a667` | GRUPO HEAL+ | Adaptado | Drawer móvel simplificado mantém Chat e HEAL Analyzer. |
| `7d0baa9` | GRUPO HEAL+ | Adaptado | Topbar e navegação inferior fixas respeitam safe areas e o composer do chat. |
| `0ac6ae1` | GRUPO HEAL+ | Adaptado | Padrões responsivos são aplicados ao chat BYOK real; o assistente simulado da origem não é criado. |
| `046135e` | GRUPO HEAL+ | Adaptado | Estratégia de ambientes é documentada para o monorepo e suas integrações. |
| `d80d677` | CampsGui | Adaptado | Preparação, compressão e upload clínico são portados preservando Analyzer e persistência atual. |
| `0313846` | CampsGui | Adaptado | Procedimentos de backup e restauração entram como exercício operacional seguro, sem execução automática em ambiente compartilhado. |
| `12b3cfc` | CampsGui | Adaptado | Correção de upload/Storage é aplicada sobre o bucket e as políticas atuais. |

## Atribuição

Os commits temáticos desta branch registram os hashes de origem no corpo. Quando
há reutilização substancial de código, também usam `Co-authored-by` com a
identidade do autor original:

- Pedro Tescaro / Pedro Antonio Silvestre Tescaro
  `<133606054+pedrotescaro@users.noreply.github.com>`;
- GRUPO HEAL+ `<308188988+grupohealplus@users.noreply.github.com>`;
- PaulinhoLeal `<paulonagasumileal@gmail.com>`;
- CampsGui `<CampsGui@users.noreply.github.com>`.

Commits de merge da origem não são listados separadamente porque não adicionam
mudança além dos commits individuais acima. Branches paralelas do monorepo,
incluindo conectores RNDS e trabalhos do Analyzer, não fazem parte desta
migração e não são incorporadas nem removidas.

## Plano de validação

As verificações são executadas serialmente para evitar interferência entre
servidor de desenvolvimento e testes:

1. `npm ci`, `npm run lint`, `npm test` e `npm run build` em
   `apps/heal_plus/web`;
2. `npm run test:e2e` com dados e credenciais sintéticos;
3. testes de isolamento RLS/Storage em projeto Supabase de desenvolvimento,
   quando houver credenciais explicitamente destinadas a teste;
4. smoke tests de Python e os checks de artefatos/segredos do monorepo;
5. inspeção manual em 390 x 844, 768 px e 1440 px, nos temas claro/escuro e com
   `prefers-reduced-motion`, cobrindo landing, autenticação, dashboard, chat,
   relatórios e Analyzer.

Migrações de banco permanecem apenas versionadas até revisão de segurança e
autorização para aplicá-las. A fronteira de token entre Supabase e o backend que
usa Firebase deve ser validada antes de qualquer alegação de revogação de sessão
no servidor.
