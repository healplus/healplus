# Apps

Esta pasta concentra os entrypoints canônicos do projeto.

## Estrutura

- `heal_plus/`: backend e frontend canônicos do produto Heal+.
- `api/`: compatibilidade temporária com o import Python anterior.
- `desktop/`: referência para a camada desktop legada.

Serviços externos do cluster não devem ser implementados nesta raiz. O contrato de integração do Heal+ fica em `contracts/heal_plus/`.
