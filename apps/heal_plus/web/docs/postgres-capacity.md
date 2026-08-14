# Capacidade do PostgreSQL e dimensionamento do HEAL+

## Resposta executiva

Ainda não existe evidência de um ensaio de capacidade do HEAL+ com carga
representativa. O PostgreSQL suporta volumes muito superiores ao estágio atual
do produto, mas isso não comprova que o plano Supabase, os índices, as conexões e
os tempos de resposta escolhidos suportem a carga esperada.

A documentação oficial do PostgreSQL informa que o tamanho total de um banco
não possui limite fixo próprio e que uma relação pode chegar a 32 TB com o bloco
padrão de 8 KiB. A mesma documentação ressalta que disco e desempenho impõem
limites práticos antes dos limites absolutos. No Supabase, capacidade recomendada,
conexões, IOPS e throughput dependem do compute e do disco provisionados.

Portanto, a resposta correta é: **o limite teórico foi verificado, mas o volume
operacional do HEAL+ ainda precisa ser dimensionado e validado por teste de carga**.

Fontes oficiais:

- [Limites do PostgreSQL](https://www.postgresql.org/docs/current/limits.html)
- [Compute e disco no Supabase](https://supabase.com/docs/guides/platform/compute-and-disk)
- [Tamanho do banco e do disco no Supabase](https://supabase.com/docs/guides/platform/database-size)

## O que ocupa cada camada

O PostgreSQL persiste contas, pacientes, avaliações, agenda, textos clínicos,
metadados de imagens e coordenadas de ROI. Fotografias não ficam dentro das
tabelas: o banco guarda o caminho privado e os metadados, enquanto os bytes
reencodados ficam no Supabase Storage.

Isso exige duas projeções separadas:

```text
Banco por período ~= dados das linhas + índices + TOAST + folga de manutenção
Storage por período = avaliações x imagens por avaliação x tamanho médio reencodado
Backup total = banco + WAL necessário + bytes dos buckets + manifestos
```

O limite de upload de 10 MB é uma barreira por arquivo, não uma previsão de
tamanho médio. O preparo no navegador limita a maior dimensão a 2.560 pixels e
reencoda os pixels em WebP ou JPEG, mas o tamanho médio real precisa ser medido
com imagens sintéticas ou datasets públicos representativos.

## Exemplo de ordem de grandeza

O cenário abaixo serve apenas para orçamento inicial; não é resultado de carga
nem previsão aprovada:

| Hipótese | Valor ilustrativo |
| --- | ---: |
| Profissionais | 1.000 |
| Pacientes por profissional | 50 |
| Avaliações por paciente por ano | 12 |
| Avaliações por ano | 600.000 |
| Imagens por avaliação | 2 |
| Tamanho médio reencodado | 1,2 MB |

Nesse cenário, somente os bytes das imagens consumiriam aproximadamente 1,44 TB
por ano. Se cada arquivo atingisse o teto de 10 MB, o limite de entrada seria
aproximadamente 12 TB por ano. O banco relacional seria muito menor, mas não deve
ser estimado somente pela soma dos campos: JSONB/TOAST, índices, versões mortas,
WAL e folga operacional também consomem disco.

## Como produzir uma resposta validada

1. Definir cenários de 12, 36 e 60 meses, concorrência de pico e metas de p95
   para login, listagens, histórico, agenda e criação de avaliação.
2. Gerar somente dados sintéticos com a distribuição esperada de pacientes,
   avaliações, imagens e ROIs.
3. Medir o tamanho reencodado das imagens e as relações com
   `pg_total_relation_size`, incluindo índices e TOAST.
4. Executar carga em projeto Supabase de homologação com o mesmo compute, disco,
   pooling e configuração planejados para produção.
5. Acompanhar conexões, CPU, memória, IOPS, throughput, WAL, autovacuum e as
   consultas mais caras por `pg_stat_statements`.
6. Repetir após 1x, 3x e 5x o volume anual esperado e registrar o primeiro ponto
   em que uma meta deixa de ser atendida.
7. Dimensionar backup/restauração com o banco e os buckets no mesmo lote; o RTO
   não pode ser inferido somente do tamanho do dump SQL.

Consultas de diagnóstico, executadas apenas por pessoa autorizada no ambiente:

```sql
select pg_size_pretty(pg_database_size(current_database()));

select
  relname,
  pg_size_pretty(pg_total_relation_size(relid)) as total,
  n_live_tup,
  n_dead_tup
from pg_stat_user_tables
order by pg_total_relation_size(relid) desc;

select count(*) as connections, state
from pg_stat_activity
group by state;
```

## Preparação incorporada nesta migração

- filtros de proprietário e listagens principais possuem índices compostos;
- as chaves `patient_id` de avaliações e compromissos possuem índices próprios,
  necessários também para `ON DELETE CASCADE`;
- políticas RLS usam `(select auth.uid())` e colunas indexadas;
- imagens clínicas ficam fora das tabelas e usam Storage privado;
- o runbook de backup trata banco e Storage como um único lote recuperável.

Particionamento não é necessário no estágio atual. Ele deve ser reavaliado
quando uma tabela se aproximar de centenas de milhões de linhas ou quando as
medições demonstrarem benefício; antecipá-lo sem carga observada aumentaria a
complexidade de migração, RLS e manutenção.
