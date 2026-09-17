# Estrutura do repositório

## Estrutura canônica

```text
healplus/
├── apps/
│   ├── heal_plus/
│   │   ├── api/                 # backend Flask e rotas
│   │   └── web/                 # frontend React/Vite
│   ├── api/                     # shim temporário do import antigo
│   └── desktop/                 # legado, fora deste recorte
├── contracts/
│   └── heal_plus/               # contratos lógicos com o cluster
├── packages/
│   ├── clinical_domain/         # domínio e persistência
│   ├── ml_inference/            # fronteira de inferência
│   └── shared/                  # segurança, runtime e auditoria
├── src/                         # implementação em migração gradual
├── ml/                          # pesquisa e treinamento, não runtime web
├── tests/
└── docs/
```

## Decisões

- `apps/heal_plus/` é a única raiz de aplicação ativa do produto Heal+.
- `apps/api/` é um shim temporário; não recebe novas funcionalidades.
- `backend/` e entrypoints Python da raiz permanecem apenas por compatibilidade.
- O código de Dermasus, Rede Viva, Twin, Takere, Integration Service e RNDS
  Dispatcher não pertence a este repositório.
- A integração com esses componentes acontece por contratos versionados, nunca
  por imports diretos.
- A migração de implementações restantes em `src/` ocorrerá em mudanças menores
  e testáveis, sem duplicar o domínio clínico.

## Mapeamento da migração

| Caminho anterior | Caminho canônico |
|---|---|
| `apps/api/` | `apps/heal_plus/api/` |
| `web/redisus-frontend/` | `apps/heal_plus/web/` |
| integração conceitual espalhada em documentos | `contracts/heal_plus/` e `docs/architecture/healplus-cluster-boundary.md` |
