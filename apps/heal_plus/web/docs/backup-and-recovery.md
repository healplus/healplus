# Backup e recuperação

Este runbook define a proteção e a recuperação da camada Supabase usada pelo
frontend integrado do Heal+. Ele cobre o PostgreSQL do Supabase e os bytes dos
buckets do Storage; um backup só é completo quando os dois escopos e seus
manifestos foram preservados. O backend, Firebase, artefatos do Heal Analyzer e
integrações REDI-SUS/FHIR/RNDS continuam com seus próprios planos de recuperação.

O backup gerenciado do banco contém os metadados do Storage, mas não contém os
arquivos armazenados. O Storage também não oferece versionamento S3. Por isso,
exportar apenas o banco não recupera fotografias clínicas ou fotos de perfil
excluídas. Consulte a documentação oficial de
[backups do banco](https://supabase.com/docs/guides/platform/backups),
[download de objetos](https://supabase.com/docs/guides/storage/management/download-objects)
e [compatibilidade S3](https://supabase.com/docs/guides/storage/s3/compatibility).

## Objetivos aprovados

A aprovação do Pull Request que introduz este runbook registra a aprovação dos
valores abaixo. Uma alteração futura exige Issue, análise de impacto e nova
aprovação operacional.

| Escopo | RPO máximo | RTO máximo | Critério de recuperação |
| --- | --- | --- | --- |
| PostgreSQL, incluindo Auth e metadados do Storage | 24 horas | 4 horas | schema, usuários e registros íntegros, com RLS e relacionamentos verificados; |
| Bytes dos buckets `wound-images` e `profile-photos` | 24 horas | 8 horas | objetos restaurados nos caminhos originais e hashes conferidos; |
| Serviço completo | 24 horas | 8 horas | banco e Storage consistentes, smoke test aprovado e acesso cruzado negado; |

RPO é a perda máxima de dados tolerada entre o último backup recuperável e o
incidente. RTO é o tempo máximo entre a declaração do incidente e a recuperação
validada. Os tempos são contados após a pessoa responsável obter acesso ao
ambiente e aos repositórios de backup.

## Política de backup

- execute exportação diária do banco e do Storage, com o mesmo identificador de
  lote e horário em UTC;
- mantenha 35 cópias diárias e 12 cópias mensais;
- armazene as cópias criptografadas em conta ou provedor separado da produção,
  com versionamento ou imutabilidade e acesso mínimo;
- gere SHA-256 para cada dump e objeto e assine o manifesto do lote;
- monitore conclusão, tamanho anômalo, objeto ausente e atraso superior a 24
  horas;
- não registre senha, chave S3, `service_role`, dado clínico, URL assinada ou
  conteúdo de objeto em logs, Issues ou Pull Requests;
- preserve os backups gerenciados oferecidos pelo plano, mas não os trate como
  substitutos da cópia externa do Storage;
- revise acesso ao repositório de backup a cada trimestre e após troca de
  responsável.

O responsável operacional de produção executa e monitora a rotina. A pessoa
responsável por segurança controla credenciais e aprova acesso excepcional. Uma
segunda pessoa revisa o manifesto e a evidência de restauração. Nenhuma dessas
credenciais pertence ao frontend ou ao repositório.

## Criar um lote

Use uma estação operacional autorizada e variáveis fornecidas pelo cofre de
segredos. Os nomes abaixo são placeholders; não coloque valores no histórico do
shell.

1. Registre identificador do lote, projeto, horário UTC, versão do PostgreSQL e
   versão da Supabase CLI.
2. Exporte roles, schema e dados conforme o fluxo oficial de
   [backup e restauração entre projetos](https://supabase.com/docs/guides/platform/migrating-within-supabase/backup-restore):

   ```console
   supabase db dump --db-url "$SUPABASE_DB_URL" -f roles.sql --role-only
   supabase db dump --db-url "$SUPABASE_DB_URL" -f schema.sql
   supabase db dump --db-url "$SUPABASE_DB_URL" -f data.sql --use-copy --data-only
   ```

3. Baixe recursivamente os bytes de `wound-images` e `profile-photos` pela API,
   Supabase CLI ou endpoint S3. Chaves S3 são credenciais administrativas que
   [ignoram RLS](https://supabase.com/docs/guides/storage/s3/authentication) e
   devem existir apenas durante a operação autorizada.
4. Gere hashes SHA-256, contagens e tamanhos. Compare a lista de objetos com
   `storage.objects` no mesmo lote.
5. Criptografe, envie para o repositório separado e teste a leitura dos arquivos
   enviados.
6. Registre apenas a evidência sanitizada: lote, horários, contagens, tamanhos,
   hashes do manifesto, resultado e responsáveis.

Se banco ou Storage falhar, o lote inteiro é inválido e deve ser refeito. Nunca
apague a última cópia válida durante a rotação.

## Restaurar

Uma restauração destrutiva ou diretamente sobre produção exige autorização
explícita, backup imediatamente anterior, plano de retorno e comunicação do
incidente. O procedimento normal restaura primeiro em um projeto Supabase novo e
isolado; clonar ou restaurar apenas o banco não copia os bytes do Storage.

1. Declare o incidente, congele mudanças e selecione o último lote completo
   anterior ao evento.
2. Verifique a assinatura, os hashes e a compatibilidade de versões sem extrair
   dados para um ambiente inferior.
3. Crie um projeto de recuperação isolado, com acesso restrito e sem integrações,
   e registre o início do RTO.
4. Restaure roles, schema e dados na ordem documentada pelo Supabase. Durante a
   importação de dados, use transações curtas quando possível e interrompa no
   primeiro erro; não desabilite RLS como correção permanente.
5. Restaure cada objeto no bucket e caminho originais. Compare bytes, hashes,
   contagens e tamanhos com o manifesto.
6. Valide migrações, chaves estrangeiras, RLS, políticas do Storage, usuários,
   contagens por tabela e referências de imagens. Faça teste cruzado com dois
   usuários controlados e smoke test do aplicativo.
7. Registre RPO observado, RTO observado, divergências e aprovação das duas
   pessoas responsáveis.
8. Só então planeje o cutover. Mantenha o ambiente anterior preservado até a
   aceitação e tenha retorno documentado para o último estado estável.

Não envie e-mail, webhook ou outra integração durante o teste. Evidências com
dados reais permanecem em repositório privado com controle de acesso; apenas o
resumo sanitizado pode entrar no Pull Request.

## Ensaios e evidências

| Frequência | Ensaio | Evidência | Retenção |
| --- | --- | --- | --- |
| semanal e em mudanças deste fluxo | restauração local automatizada com dados sintéticos | artifact `backup-restore-evidence` do workflow e resultado da CI | 90 dias; |
| trimestral | restauração do último lote real em projeto novo, isolado e autorizado | checklist privado, lote, hashes, contagens, RPO/RTO e aprovações | 12 meses; |
| anual | exercício de mesa para indisponibilidade de banco e Storage | ata sanitizada, lacunas e Issues de correção | 24 meses; |

O workflow [`backup-restore-drill.yml`](../../../../.github/workflows/backup-restore-drill.yml)
executa o ensaio sintético e não acessa projeto remoto. Localmente, Docker e a
Supabase CLI `2.113.0` são obrigatórios:

```console
npm run test:backup-restore
```

O comando aceita a operação destrutiva somente para o `project_id` dedicado
`healplus-backup-restore-drill`, recria a stack local, exporta os dados clínicos
do PostgreSQL e os objetos sintéticos dos dois buckets, restaura tudo e grava evidência em
`test-results/backup-restore/evidence.json`. Esse arquivo é ignorado pelo Git.
O ensaio sintético semanal detecta regressões no procedimento, mas não substitui
o ensaio trimestral do último backup real, que também valida Auth e todos os
schemas incluídos no lote operacional.

Uma evidência é aprovada somente quando inclui commit, versões das ferramentas,
início e fim em UTC, RPO/RTO observados, contagens, hash do manifesto, resultado
das verificações e responsáveis. Falha, atraso ou divergência abre Issue P0,
preserva todos os artefatos e suspende mudanças destrutivas até correção e novo
ensaio aprovado.
