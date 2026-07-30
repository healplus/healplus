# Arquitetura Atual do Repositório

## Objetivo

Descrever o estado real do HEAL+ / REDISUS hoje, sem confundir visão futura com o que já está operacional no repositório.

## Componentes Atuais

### 1. Núcleo Python em `src/`

É a parte mais importante do repositório do ponto de vista técnico. Concentra:

- domínio clínico;
- processamento por OpenCV;
- módulos de inferência e classificação;
- banco SQLite local;
- API clínica Flask;
- interoperabilidade e utilitários.

Principais módulos:

- `src/data/database.py`
- `src/dashboard/clinical_api.py`
- `src/diagnosis/`
- `src/processing/`
- `src/treatment/`

### 2. Backend oficial em `apps/heal_plus/api/`

Esta é a nova composição canônica do backend.

Responsabilidades:

- inicializar a aplicação Flask oficial;
- registrar a API clínica;
- registrar endpoints de integração legados;
- expor um ponto único para saúde, análise, relatórios e rotas de dashboard.

### 3. Frontend em `apps/heal_plus/web/`

Aplicação React/Vite com foco em:

- login;
- dashboard de pacientes;
- avaliações;
- relatórios;
- integração com Firebase;
- proxy para API clínica.

### 4. Compatibilidade temporária

- `apps/api/` mantém o import público anterior e encaminha para `apps/heal_plus/api/`.
- `apps/web/` aponta para a nova localização do frontend.
- `backend/app.py` mantém o entrypoint Flask legado.

### 5. Backend de compatibilidade em `backend/`

`backend/app.py` agora aponta para `apps/heal_plus/api/app.py` para manter compatibilidade com comandos antigos.

### 6. Experimentos e treinamento

- `scripts/` concentra rotinas de preparação e treino.
- `models/` guarda pesos e metadados versionados.
- `dataset/` contém principalmente o acervo `medetec`.
- `runs/` contém saídas de treino do detector.

## Leitura Correta da Arquitetura

### Fluxo clínico oficial

```text
Frontend React/Vite
    -> proxy /api/clinical
        -> apps/heal_plus/api/app.py
            -> src/dashboard/clinical_api.py
            -> integração Firebase / Gemini / analyzer legado
            -> SQLite local em data/redisus.db
```

### Fluxo clínico anteriormente mais coerente

```text
Frontend React/Vite
    -> proxy /api/clinical
        -> API clínica Flask em src/dashboard/clinical_api.py
            -> SQLite local em data/redisus.db
            -> pipeline de análise e relatórios
```

## Decisão Arquitetural de Curto Prazo

Para organizar o projeto sem quebrar o código existente:

- `apps/heal_plus/api` passa a ser o backend oficial;
- `packages/` passa a ser a camada canônica de importação;
- `src/dashboard/clinical_api.py` permanece como contrato clínico principal;
- `backend/app.py` vira shim de compatibilidade;
- `heal_analyzer.py`, `main.py`, `realtime_app.py` e `heal_platform.py` seguem como entrypoints legados ou experimentais.

## Dores Reais

- dois backends convivendo com responsabilidades sobrepostas;
- múltiplos entrypoints Python na raiz;
- taxonomia clínica não totalmente alinhada entre heurística, DL, frontend e docs;
- pesos e datasets misturados com fonte do produto;
- ausência de packaging e separação de ambientes.

## Direção Recomendada

### Agora

- consolidar documentação e contrato de dados;
- manter o runtime atual funcional;
- eliminar ruído da raiz;
- publicar benchmark honesto e model cards.

### Depois

- unificar backend clínico e backend de integração;
- extrair módulos reutilizáveis para packages dedicados;
- separar artefatos grandes do repositório principal;
- adicionar observabilidade, CI robusto e interoperabilidade clínica formal.

## Fronteira com o ecossistema

O papel do Heal+ no diagrama do cluster, os componentes externos e os contratos permitidos estão definidos em [`healplus-cluster-boundary.md`](healplus-cluster-boundary.md). A estrutura de pastas canônica está em [`repository-layout.md`](repository-layout.md).
