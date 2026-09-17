# Contrato provisório de acesso: conta pessoal e instituição

## Status e finalidade

**Status:** decisão provisória para o piloto, versão `1.0.0`.

Este documento define o mínimo necessário para implementar e testar autorização
sem ampliar acesso implicitamente. O contrato normativo e legível por máquina está
em [`access-control-contract.v1.json`](access-control-contract.v1.json).

“Ownership” neste documento significa **vínculo técnico usado para autorização e
custódia no produto**. Não afirma propriedade jurídica de dados nem define, por si
só, os papéis de controlador, operador ou titular previstos na LGPD. Essas
responsabilidades dependem de decisão institucional.

O contrato complementa o [modelo de ameaças](threat-model.md), as
[diretrizes de backend seguro](secure-backend-guidelines.md) e a orientação de
governança da fundação sobre
[gestão de acesso](https://github.com/healplus/healplus-foundation/blob/main/docs/05-governance/access-management.md).

## Decisão

1. Toda conta representa uma pessoa. Não há conta institucional compartilhada.
2. A conta pessoal existe independentemente dos vínculos institucionais.
3. Um vínculo institucional é explícito, tem escopo em uma instituição e pode ser
   revogado sem excluir a conta pessoal.
4. Papel administrativo não concede acesso a conteúdo clínico.
5. Acesso clínico institucional exige, ao mesmo tempo, vínculo ativo, capacidade
   clínica apropriada e atribuição explícita ao recurso.
6. O servidor é a fonte de verdade para papéis, vínculos, atribuições e ownership.
   Campos ou papéis enviados pelo cliente nunca autorizam uma operação.
7. Tudo que não estiver permitido neste contrato é negado.

Papéis clínicos profissionais, como enfermagem ou medicina, são atributos separados
dos papéis de acesso abaixo. Um título profissional não substitui atribuição ao
caso; um papel administrativo não substitui capacidade clínica.

## Papéis mínimos

| Papel | Pode | Não pode por padrão |
|---|---|---|
| `personal_owner` | Criar e usar recursos do próprio espaço pessoal | Acessar recursos institucionais ou de outra conta |
| `invited_account` | Aceitar ou recusar o convite destinado à própria identidade | Ler dados da instituição antes da ativação |
| `institution_member` | Atuar em recurso clínico atribuído, se também possuir a capacidade necessária | Administrar membros; acessar toda a instituição |
| `institution_access_admin` | Convidar e remover membros comuns dentro da própria instituição | Ler conteúdo clínico ou auditoria; promover administradores; alterar owner |
| `institution_owner` | Administrar configuração, administradores e continuidade do vínculo institucional | Ler conteúdo clínico sem também ser membro clínico atribuído |

Uma pessoa pode acumular papéis, mas cada autorização avalia todos os requisitos da
ação. Acumular `institution_owner` e `institution_member`, por exemplo, não elimina
a necessidade de atribuição explícita ao recurso clínico.

## Matriz de ações críticas

“Todos” significa que todas as partes listadas precisam confirmar. Operações
desabilitadas continuam negadas mesmo quando a tabela identifica os futuros
participantes.

| Ação crítica | Papéis autorizados | Restrições obrigatórias |
|---|---|---|
| Criar recurso pessoal | `personal_owner` | Identidade autenticada; owner definido pelo servidor |
| Ler, editar ou exportar recurso pessoal | `personal_owner` | Owner técnico igual à identidade atual |
| Criar recurso clínico institucional | `institution_member` | Vínculo ativo, capacidade de escrita, atribuição explícita e owner institucional definido pelo servidor |
| Ler recurso clínico institucional | `institution_member` | Vínculo ativo, capacidade de leitura e atribuição explícita |
| Atualizar recurso clínico institucional | `institution_member` | Mesmas condições de leitura, capacidade de escrita e owner inalterado |
| Enviar mídia clínica | `institution_member` | Vínculo e atribuição ativos, owner do recurso pai no mesmo escopo, caminho gerado no servidor e validação do tipo declarado, conteúdo/formato real e tamanho |
| Exportar recurso clínico institucional | `institution_member` | Atribuição, capacidade específica de exportação e auditoria |
| Solicitar IA com contexto clínico | `institution_member` | Atribuição, ação e consentimento aplicáveis explícitos, minimização e revisão humana |
| Convidar membro comum | `institution_access_admin` ou `institution_owner` | Convite nominal, expirável, de uso único e auditado |
| Convidar administrador | `institution_owner` | Mesmas condições do convite; não permite convidar owner diretamente |
| Aceitar convite | `invited_account` | Identidade corresponde ao destinatário e confirma explicitamente |
| Revogar convite | `institution_access_admin` ou `institution_owner` | Somente convite dentro do próprio limite de concessão; operação auditada |
| Alterar papel de membro comum | `institution_access_admin` ou `institution_owner` | Não pode conceder `institution_access_admin` nem `institution_owner` |
| Promover ou remover administrador | `institution_owner` | Alvo não é owner; operação auditada |
| Remover membro comum | `institution_access_admin` ou `institution_owner` | Revogar primeiro; reatribuir trabalho depois; não alterar owner nem autoria histórica |
| Sair da instituição | `institution_member` ou `institution_access_admin` | Somente o próprio vínculo; revogar antes de reatribuir trabalho; owner usa transferência explícita |
| Alterar configurações institucionais | `institution_owner` | Vínculo ativo e operação auditada |
| Ler auditoria de acesso | Nenhum | **Desabilitado** até definir campos, finalidade, retenção e revisores autorizados |
| Transferir responsabilidade de owner institucional | `institution_owner` atual **e** outro `institution_access_admin` de destino | Identidades distintas, confirmação das duas pessoas, vínculo ativo do destino, instituição nunca fica sem responsável e auditoria |
| Alterar owner como campo comum | Nenhum | Rejeitar a requisição |
| Transferir recurso pessoal para instituição | `personal_owner` **e** `institution_owner` de destino | **Desabilitado** até decisão institucional; quando habilitado exige confirmação bilateral e conjunto de recursos enumerado |
| Transferir recurso institucional para conta pessoal | Nenhum | **Desabilitado** até decisão institucional |
| Transferir entre instituições | Nenhum | Fora do escopo e negado |
| Excluir definitivamente recurso clínico | Nenhum | **Desabilitado** até definição de retenção e descarte |

## Ownership e atribuição

Cada recurso clínico deve receber no servidor, durante a criação:

- `owner_type`: `personal` ou `institution`;
- `owner_id`: identificador interno do owner técnico;
- `created_by`: identidade individual que realizou a criação;
- timestamp gerado no servidor.

`owner_type`, `owner_id` e `created_by` são imutáveis em atualizações comuns. A
atribuição de profissional, equipe ou fila é mutável e **não transfere ownership**.
Remover alguém da instituição preserva os registros e a autoria histórica.

Uma transferência de responsabilidade administrativa da instituição troca a pessoa
que exerce `institution_owner`, mas mantém `owner_id` dos recursos apontando para a
mesma instituição. Isso não é transferência dos recursos.

A eventual transferência de recurso pessoal para instituição fica bloqueada no
piloto. Antes de habilitá-la, a instituição deve resolver as pendências listadas
abaixo. A implementação futura não poderá reutilizar uma atualização comum: deverá
ser uma operação dedicada, transacional, bilateral, auditada e com efeitos
apresentados antes da confirmação.

## Convite, saída e revogação

O convite identifica uma conta destinatária, instituição, papel proposto, emissor,
expiração e nonce de uso único. O papel proposto é validado no servidor por
allowlist: administradores de acesso só podem convidar `institution_member`, e
owners podem convidar `institution_member` ou `institution_access_admin`. Convites
nunca concedem `institution_owner`; esse papel só muda pelo fluxo bilateral entre
duas identidades distintas. O convite não cria vínculo nem concede acesso até a
aceitação pela identidade destinatária. Convite expirado, reutilizado, revogado ou
aberto por outra identidade é negado sem revelar dados institucionais.

Na remoção:

1. o servidor inativa o vínculo;
2. novas requisições falham fechadas, inclusive com IDs de recursos conhecidos;
3. sessões são invalidadas quando o provedor permitir; em qualquer caso, operações
   sensíveis revalidam o vínculo ativo e não confiam apenas em claims em cache;
4. atribuições e filas de trabalho são tratadas separadamente, sem manter acesso
   temporário e sem mudar owner ou autoria;
5. o evento registra apenas metadados mínimos de auditoria, nunca conteúdo clínico.

Um `institution_access_admin` só remove membros comuns. Apenas
`institution_owner` remove ou rebaixa administradores. A última pessoa responsável
não pode sair nem ser removida sem transferência explícita e aceita.

## Limites administrativos

- Administração de acesso não é papel clínico e não contorna ownership.
- Não existe papel “superadmin institucional” capaz de ler todo conteúdo.
- Nenhum administrador promove a si próprio para `institution_owner`.
- Convites e alterações de papel só concedem o subconjunto permitido ao ator.
- Logs de administração usam identificadores mínimos e não incluem imagens, notas,
  prontuários, tokens, prompts ou payloads clínicos.
- A interface pode ocultar ações, mas toda decisão é repetida no servidor.
- Claims de token ajudam na autenticação, mas vínculo ativo e atribuição ao recurso
  precisam vir de fonte autoritativa atual.

## Cenários de teste obrigatórios

### Convites

- convite pendente não concede leitura;
- convite expirado, reutilizado ou aberto por outra identidade é negado;
- administrador de acesso convida membro, mas não administrador ou owner;
- owner convida administrador, mas não outro owner;
- após aceitar, o membro continua sem acesso clínico até receber atribuição.

### Menor privilégio

- administrador ou owner sem papel clínico e sem atribuição não lê conteúdo;
- membro atribuído lê apenas os recursos atribuídos;
- possuir um ID válido de outro recurso não altera a decisão;
- upload com vínculo revogado, recurso de outro escopo, tipo ou tamanho inválido é negado;
- exportação exige capacidade adicional e gera auditoria;
- troca de conta limpa estado sensível no cliente.

### Remoção

- vínculo revogado é negado na requisição seguinte, mesmo com token ainda válido;
- usuário removido não lê, altera, exporta, envia mídia nem solicita IA;
- remoção preserva owner, `created_by` e histórico;
- reatribuir trabalho não reativa acesso nem muda owner.

### Ownership

- update comum com `owner_id`, `owner_type` ou `created_by` é rejeitado;
- transferência pessoal-instituição permanece desabilitada;
- owner institucional não sai deixando a instituição órfã;
- tentativa cross-institution é negada.

Os cenários usam apenas identificadores e dados sintéticos. Respostas de negação não
devem confirmar a existência de recurso fora do escopo.

## Estado atual e lacunas de implementação

Este contrato é uma decisão de destino, não evidência de que todos os controles já
estão implementados.

A camada Supabase acessada diretamente pelo frontend possui RLS pessoal por
`auth.uid()` e Storage por pasta do usuário, documentados em
[`apps/heal_plus/web/docs/security-and-privacy.md`](../../apps/heal_plus/web/docs/security-and-privacy.md).
Essas políticas não implementam vínculos, atribuições ou papéis institucionais e
não devem ser interpretadas como cumprimento deste contrato futuro.

- `packages/shared/security.py` usa papéis planos e hoje permite bypass de
  ownership para papéis administrativos.
- As políticas RLS em `supabase/migrations` restringem registros e imagens ao titular e exigem sessão ativa.
- ainda não existe fonte autoritativa versionada para vínculo, atribuição e
  capacidade clínica institucional.

Até a implementação e os testes negativos correspondentes, contas institucionais
não devem ser habilitadas com dados reais.

## Pendências para decisão institucional

Estas perguntas não são resolvidas por este contrato e devem permanecer explícitas:

- quem exerce as responsabilidades institucionais de controlador e operador em
  cada piloto;
- quais evidências validam vínculo profissional e capacidade clínica;
- prazo e responsável por revisão periódica de membros;
- prazo operacional de desligamento e política de expiração de sessão;
- quantidade permitida de owners e recuperação quando não houver pessoa disponível;
- retenção, arquivamento, exclusão e exportação de dados clínicos;
- conteúdo, retenção, acesso e revisão da trilha de auditoria;
- base legal, consentimento aplicável e comunicação para transferência
  pessoal-instituição;
- processo excepcional de emergência (“break glass”), que permanece negado;
- autoridade para aprovar a entrada de cada instituição e sua configuração inicial.

SCIM, RBAC regulatório definitivo e compartilhamento entre instituições continuam
fora do escopo.

## Critério para substituir o caráter provisório

Uma versão definitiva exige decisão institucional sobre as pendências, modelagem
versionada da fonte autoritativa, políticas server-side para cada ação, testes
negativos com duas identidades e revisão de privacidade e segurança. Mudanças no
JSON normativo exigem nova versão e revisão de segurança.
