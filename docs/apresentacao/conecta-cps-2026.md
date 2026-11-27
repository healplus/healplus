# Apresentação Heal+ · Conecta CPS (Polo Regional 4)

Roteiro da equipe para a feira de 27/11/2026.

## Público e objetivo

- **Quem assiste:** empresas e instituições que podem apoiar o Centro Paula Souza no novo curso integrado Etec + Fatec.
- **O que essas pessoas querem saber:** que tipo de projeto os estudantes conseguem desenvolver. Ninguém ali está avaliando investimento no Heal+.
- **Mensagem central:** um problema real de saúde virou um projeto de software completo, que hoje contribui com pesquisa aplicada da RNP. É esse tipo de formação que o CPS oferece.

Não confundir com uma banca técnica: fale de impacto e de aprendizado, não de detalhes de implementação.

> Antes do evento, confirme com o prof. Rogério o nome oficial do novo curso e ajuste o slide "Parcerias" (`apps/heal_plus/web/src/features/presentation/slideContent.ts`) se for necessário.

## Como abrir

A apresentação fica dentro do próprio app, na rota pública `/apresentacao`. Não exige login nem internet depois de carregada, e não mostra dados de pacientes.

```powershell
cd apps/heal_plus/web
npm run dev:apresentacao
```

Abra `http://localhost:5173/apresentacao` (ou a porta que o Vite indicar).

| Tecla | Ação |
| --- | --- |
| `→`, `Espaço`, `Page Down` | Próximo slide |
| `←`, `Page Up` | Slide anterior |
| `Home` / `End` | Primeiro / último slide |
| `F` | Tela cheia |

Se preferir o PowerPoint, use [heal-plus-conecta-cps-2026.pptx](heal-plus-conecta-cps-2026.pptx). Ele tem os mesmos 9 slides, e a fala sugerida de cada um está nas anotações do apresentador.

Na versão web, também dá para usar os botões do rodapé, deslizar o dedo no tablet ou abrir um slide direto pela URL (`/apresentacao#ia`, `#trajetoria`, `#equipe`…).

`npm run dev:apresentacao` também liga o **modo de demonstração** (`VITE_PRESENTATION_MODE=true`): o menu da área clínica esconde a Agenda e o Assistente. O assistente exige a chave pessoal de um provedor de IA, e a agenda mostra nomes de pacientes.

## Roteiro (cerca de 4 minutos)

| # | Slide | Fala sugerida | Tempo |
| --- | --- | --- | --- |
| 1 | Capa | "Somos estudantes de ADS da Fatec Ferraz de Vasconcelos. Este é o Heal+, uma plataforma para apoiar o acompanhamento de feridas crônicas." | 15 s |
| 2 | O desafio | "Feridas crônicas precisam ser avaliadas a cada consulta. Na prática, as anotações ficam espalhadas e as fotos não seguem um padrão, então fica difícil saber se a ferida está melhorando." | 30 s |
| 3 | A ideia inicial | "A nossa ideia foi simples: um lugar único para registrar o paciente e as avaliações, organizar as imagens e comparar a evolução. E usar IA para ajudar a delimitar a lesão na foto." | 30 s |
| 4 | Como funciona | "O fluxo tem quatro passos: cadastrar, avaliar, comparar e documentar." Se houver tempo, faça a demonstração ao vivo (veja abaixo). | 30 s (+2 min de demo) |
| 5 | IA como apoio | "A IA confere a qualidade da foto, destaca a ferida e os tecidos e compara avaliações. A decisão é sempre do profissional. Os primeiros testes, antes e depois de um desbridamento, foram promissores, mas ainda faltam ajustes e validação clínica." | 40 s |
| 6 | Nossa trajetória | "Começou como um projeto de sala de aula, virou um protótipo, participamos da chamada pública da RNP para redes de saúde digital e hoje contribuímos com o módulo de análise de imagens por IA." | 40 s |
| 7 | Formação | "Num projeto só, a gente aprendeu desenvolvimento web, APIs, IA, segurança de dados, padrões de saúde e testes. É o que o mercado procura." | 30 s |
| 8 | Parcerias | "O novo curso Etec + Fatec quer aproximar ainda mais os estudantes das empresas: com desafios reais, mentoria, estágios e infraestrutura." | 30 s |
| 9 | Equipe | Agradeça, cite as orientadoras e o orientador e abra para perguntas. | 15 s |

### Versão de 1 minuto (para quem passa rápido no estande)

> "O Heal+ é uma plataforma criada por estudantes de ADS da Fatec Ferraz de Vasconcelos para ajudar profissionais de saúde a acompanhar feridas crônicas. Ela organiza o histórico do paciente, as fotos e a evolução da ferida, e usa inteligência artificial como apoio para destacar a lesão na imagem. O projeto começou em sala de aula, participou da chamada pública da RNP para saúde digital e hoje contribui com um módulo de análise por IA. É um exemplo do que os estudantes do Centro Paula Souza conseguem construir quando trabalham com problemas reais."

## Demonstração ao vivo (opcional)

Faça somente se a internet do local estiver estável. Sem internet, siga só com os slides.

1. Antes do evento, entre com uma **conta de demonstração** que tenha apenas **pacientes fictícios**. Não use contas com dados reais.
2. No slide 4, clique em **Abrir a plataforma** (ou acesse `/login`).
3. Mostre, nesta ordem: **Dashboard → Pacientes → Detalhe de um paciente → Comparar evolução → Relatórios**.
4. Se a API Python estiver rodando, mostre o **HEAL Analyzer** com uma imagem de exemplo já testada.
5. Volte para `/apresentacao#ia` para retomar a fala.

### O que não mostrar

- Dados, fotos ou prontuários de pacientes reais.
- O Assistente de IA e as configurações de chave de API.
- Terminal, arquivos `.env`, painel do Supabase ou qualquer credencial.
- Não diga que a IA "diagnostica" ou que o sistema já está em uso clínico.

## Perguntas prováveis

- **"Já está sendo usado em hospitais?"** Não. É um protótipo de pesquisa aplicada. Para uso assistencial ainda faltam validação clínica e aprovações.
- **"A IA dá o diagnóstico?"** Não. Ela destaca a região da ferida e gera indicadores para o profissional revisar. A decisão é sempre humana.
- **"E a privacidade dos pacientes?"** O projeto segue princípios da LGPD: acesso autenticado, dados isolados por usuário e só as informações necessárias. Em demonstrações usamos apenas dados fictícios.
- **"Que tecnologias vocês usaram?"** React e TypeScript no front-end, Python nas APIs e na análise de imagens (OpenCV), Supabase para dados e autenticação, e o padrão HL7 FHIR para interoperabilidade em saúde.
- **"O que é a RNP?"** A Rede Nacional de Ensino e Pesquisa. O Heal+ participou da chamada pública do Programa Redes de Colaboração em Saúde Digital, no contexto do cluster REDI-SUS.
- **"Como uma empresa pode ajudar?"** Encaminhe para os professores e para a coordenação do CPS. Não assuma compromissos em nome da instituição.

## Checklist

### Na véspera

- [ ] `npm ci` e `npm run build:apresentacao` sem erros em `apps/heal_plus/web`.
- [ ] Abrir `/apresentacao` e passar os 9 slides no computador que será usado.
- [ ] Testar a tela cheia (`F`) na resolução do monitor ou projetor.
- [ ] Se for fazer a demo: conta de demonstração com pacientes fictícios funcionando.
- [ ] Levar o banner impresso e o PDF do banner em um pendrive.

### No local

- [ ] Carregar `/apresentacao` assim que chegar (depois disso funciona sem internet).
- [ ] Desativar notificações do sistema e fechar abas e programas que não serão usados.
- [ ] Deixar a apresentação aberta na capa, em tela cheia.

### Plano B

1. Sem internet: rode `npm run build:apresentacao` e depois `npm run preview` antes de sair de casa e mantenha o servidor aberto. Os slides não dependem de serviços externos (as fontes caem para as do sistema).
2. Se o computador falhar: apresente usando o banner impresso, seguindo o mesmo roteiro.
