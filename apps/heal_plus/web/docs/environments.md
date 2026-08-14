# Estratégia de ambientes

Esta é a fonte canônica para separar desenvolvimento, homologação (staging) e
produção no HEAL+. O objetivo é impedir que dados, chaves, redirects e processos
de release sejam compartilhados por conveniência.

Esta pasta entrega o frontend estático, enquanto o repositório integrado também
mantém backend, Firebase e integrações REDI-SUS/FHIR/RNDS. Cada ambiente precisa
ser preparado como uma combinação coerente e independente de:

- projeto Supabase;
- variáveis públicas `VITE_*` usadas no build;
- domínio ou URL de preview;
- URLs autorizadas no Supabase Auth;
- `VITE_CLINICAL_API_URL` apontando ao backend compatível do mesmo ambiente;
- configurações separadas das integrações preservadas;
- dados, usuários de teste e evidências de validação.

## Registro de ambientes

| Ambiente | Proprietário operacional | Finalidade | Dados permitidos | Supabase e credenciais | Redirects autorizados |
| --- | --- | --- | --- | --- | --- |
| Desenvolvimento | Pessoa responsável pela mudança, com revisão de `@grupohealplus` | Execução local, experimentação e validação inicial antes do Pull Request | Somente dados sintéticos criados para teste | Projeto Supabase de desenvolvimento; `.env` local não versionado; chaves públicas exclusivas desse projeto | `http://localhost:<porta>/auth/callback` para a porta Vite em uso |
| Homologação | Responsável pelo release em `@grupohealplus` | Aceite funcional, smoke test, RLS, Storage, migrações e revisão visual antes de produção | Dados sintéticos representativos; nenhum dado real de paciente ou profissional externo | Projeto Supabase de homologação; variáveis do host configuradas separadamente; OAuth app separado quando aplicável | Domínio de homologação e previews aprovados explicitamente |
| Produção | Responsável operacional e de segurança em `@grupohealplus` | Uso real autorizado, com backup, retenção, monitoramento e plano de incidente | Dados reais apenas quando houver autorização, base legal e controles operacionais | Projeto Supabase de produção; variáveis do host de produção; rotação e acesso restritos | Domínios públicos de produção, sem curingas amplos |

Nenhum ambiente inferior pode apontar para o projeto Supabase, bucket, chave,
OAuth app ou domínio de callback de produção.
Os ambientes não compartilham projeto Supabase, credenciais, buckets ou dados.

## Regras obrigatórias de isolamento

1. **Projetos separados:** desenvolvimento, homologação e produção usam projetos
   Supabase diferentes. Migrações são promovidas pelo repositório, não copiando
   bancos entre ambientes.
2. **Dados separados:** desenvolvimento e homologação usam somente dados
   sintéticos. Não exporte produção para ambientes inferiores, mesmo parcialmente,
   sem uma tarefa aprovada de anonimização irreversível.
3. **Credenciais separadas:** cada ambiente define `VITE_SUPABASE_URL`,
   `VITE_SUPABASE_ANON_KEY` e `VITE_CLINICAL_API_URL` próprios. Nunca versionar `.env`, chave
   `service_role`, senha de banco ou token privado.
4. **Build separado:** variáveis `VITE_*` entram no bundle. Gere um build novo
   para cada ambiente; não reaproveite um artefato compilado com outra URL do
   Supabase.
5. **Redirects exatos:** configure Site URL e Redirect URLs no Supabase Auth por
   ambiente. Produção não deve aceitar `localhost`, domínios de preview genéricos
   ou curingas amplos.
6. **Storage separado:** buckets como `wound-images` e `profile-photos` pertencem
   ao projeto Supabase do ambiente. Caminhos de objetos não devem ser tratados
   como portáveis entre ambientes.
7. **Evidência sanitizada:** logs, screenshots, Issues, Pull Requests e relatórios
   de validação usam somente dados sintéticos e não exibem tokens ou URLs
   assinadas.

## Promoção entre ambientes

Promova uma alteração pelo commit ou tag aprovado, nunca por cópia manual de
dados, `.env` ou arquivos compilados de outro ambiente.

1. Abra uma branch curta conforme a
   [política integrada de branches](../../../../docs/operations/branch-policy.md).
2. Implemente a mudança com documentação, testes e rollback proporcional ao risco.
3. Abra Pull Request para `develop`, vincule a Issue e descreva:
   - ambientes afetados;
   - migrações ou variáveis novas;
   - validações executadas;
   - plano de rollback;
   - confirmação de uso exclusivo de dados sintéticos.
4. Execute CI e verificações locais obrigatórias.
5. Após merge em `develop`, publique primeiro em homologação:
   - gere build com variáveis de homologação;
   - aplique migrações pendentes no Supabase de homologação;
   - execute smoke test, teste RLS com dois usuários sintéticos e checklist visual.
6. Promova para produção somente depois do aceite de homologação:
   - confirme o lote completo, o ensaio de restauração, redirects e variáveis de produção;
   - gere build com variáveis de produção;
   - aplique migrações compatíveis;
   - publique e execute a verificação pós-implantação.
7. Se houver falha de frontend, reverta republicando o último artefato aprovado
   para aquele ambiente. Se houver falha de banco, prefira correção aditiva e siga
   o rollback documentado na migração.

## Checklist por ambiente

Antes de usar um ambiente, registre internamente:

- finalidade e proprietário operacional;
- URL pública ou local esperada;
- projeto Supabase correspondente;
- lista de Redirect URLs autorizadas;
- origem dos dados sintéticos;
- status das migrações;
- último teste cruzado de RLS;
- responsável por backup e incidentes, último lote válido e último ensaio de
  restauração, quando aplicável.

Produção segue os RPO/RTO, a retenção e as responsabilidades definidos em
[backup-and-recovery.md](backup-and-recovery.md). O projeto isolado usado no
ensaio trimestral é temporário e não se torna um ambiente inferior nem recebe
integrações externas.

## Mudanças que exigem revisão desta estratégia

Atualize este documento no mesmo Pull Request quando:

- criar nova variável de ambiente;
- alterar domínio, callback ou provedor OAuth;
- adicionar bucket, tabela clínica, integração externa ou monitoramento;
- mudar o fluxo de build, deploy, rollback ou promoção;
- permitir qualquer dado real fora de produção.
