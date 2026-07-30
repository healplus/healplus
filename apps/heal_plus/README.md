# Aplicação Heal+

Esta é a raiz canônica do produto Heal+ neste repositório.

```text
apps/heal_plus/
├── api/    # composição e rotas do backend Flask
└── web/    # aplicação React/Vite
```

O domínio clínico, a inferência e utilitários reutilizáveis continuam em
`packages/` e `src/`. Essa separação permite organizar o produto sem duplicar
regras clínicas ou misturar o Heal+ com serviços do cluster que pertencem a
outros repositórios.

## Execução local

Backend:

```powershell
python -m apps.heal_plus.api.app
```

Frontend:

```powershell
Set-Location apps/heal_plus/web
npm ci
npm run dev
```

## Fronteira com o cluster

- O Heal+ não se conecta diretamente à RNDS.
- A troca clínica futura deve usar FHIR R4 através do Integration Service e dos
  tópicos administrados pelo cluster.
- A integração de imagens com o Takere usa referências mínimas; credenciais,
  imagens e conteúdo clínico não entram em URLs, logs ou eventos.
- Os contratos lógicos estão em `contracts/heal_plus/`.
- Não há cliente real de RNDS, broker ou Takere habilitado por esta
  reorganização.

Consulte `docs/architecture/healplus-cluster-boundary.md` para o mapeamento do
diagrama e as limitações atuais.
