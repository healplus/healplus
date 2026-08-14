# Supabase da camada web

Este diretório versiona somente o schema e as políticas usados diretamente pelo
frontend. Não substitui o backend integrado, Firebase, Heal Analyzer nem os
contratos REDI-SUS/FHIR/RNDS.

## Aplicação segura

As migrações são aditivas ou reparadoras e devem ser promovidas na ordem do nome.
Não execute `db reset` em ambiente compartilhado. Antes de homologação ou
produção:

1. faça backup verificável do PostgreSQL e dos bytes do Storage;
2. inspecione os tipos implantados, pois ambientes legados podem ter IDs `text`;
3. aplique primeiro em um projeto de desenvolvimento isolado;
4. valide dois usuários sintéticos, incluindo tentativas cruzadas;
5. confirme que `wound-images` é privado e que não existe política clínica para
   `anon`;
6. registre resultado, rollback e responsável no Pull Request.

`202608030001_initial_schema.sql` prepara instalações novas.
`202608040002_repair_clinical_rls_policies.sql` repara RLS sem modificar dados e
usa comparação textual para tolerar IDs legados. As duas migrações de
`20260811` reafirmam buckets e políticas de proprietário.

As tabelas clínicas revogam privilégios de `anon` e concedem explicitamente
`SELECT`, `INSERT`, `UPDATE` e `DELETE` a `authenticated`; RLS continua sendo a
barreira por linha. A camada atual implementa ownership pessoal por `uid`, não o
modelo institucional futuro descrito no contrato integrado de acesso.

## Desenvolvimento e ensaio

O `project_id` local `healplus-backup-restore-drill` é intencional: o script de
restauração recusa qualquer outro identificador. Com Docker e a Supabase CLI
fixada pelo workflow:

```console
npm run test:backup-restore
```

O comando recria apenas a stack local dedicada e usa dados sintéticos. Nenhuma
migração deste trabalho é aplicada remotamente de forma automática.

## Rollback

Políticas podem ser reparadas por nova migração aditiva. Remover tabelas,
colunas, objetos ou buckets não faz parte deste conjunto. Uma reversão que afete
dados exige restauração validada conforme
[`../docs/backup-and-recovery.md`](../docs/backup-and-recovery.md).
