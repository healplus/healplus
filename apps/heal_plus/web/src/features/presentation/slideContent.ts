import {
  BrainCircuit,
  Briefcase,
  Camera,
  ClipboardCheck,
  ClipboardList,
  Code2,
  FileText,
  FileWarning,
  Handshake,
  Images,
  Layers,
  Lightbulb,
  MessagesSquare,
  MonitorSmartphone,
  Network,
  ScanEye,
  ScanLine,
  ScanSearch,
  Server,
  ShieldCheck,
  Sparkles,
  TestTubeDiagonal,
  UserCheck,
  Users,
  Wrench
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

/*
 * Conteúdo da apresentação pública (Conecta CPS · Polo Regional 4).
 * Os textos seguem o banner do projeto e evitam afirmar uso clínico validado:
 * qualquer menção à IA deve deixar claro que ela é apoio experimental.
 */

export interface SlideItem {
  icon: LucideIcon;
  title: string;
  text: string;
}

export interface TimelineItem extends SlideItem {
  current?: boolean;
}

export const institutionLogos = [
  { name: 'Fatec Ferraz de Vasconcelos', light: '/images/partners/fatec-ferraz.png', dark: '/images/partners/fatec-ferraz.png' },
  { name: 'Centro Paula Souza', light: '/images/partners/cps.svg', dark: '/images/partners/cps_modoDark.svg' }
] as const;

export const cover = {
  eyebrow: 'Conecta CPS · Polo Regional 4',
  title: 'Plataforma inteligente para avaliação e acompanhamento de feridas crônicas',
  course: 'Tecnologia em Análise e Desenvolvimento de Sistemas',
  institution: 'Fatec Ferraz de Vasconcelos'
};

export const challenge = {
  eyebrow: 'O desafio',
  title: 'Feridas crônicas exigem acompanhamento contínuo e comparável.',
  items: [
    {
      icon: ClipboardList,
      title: 'Avaliações periódicas',
      text: 'Localização, dimensões e condições do leito da ferida precisam ser registradas a cada consulta.'
    },
    {
      icon: FileWarning,
      title: 'Registros fragmentados',
      text: 'Anotações dispersas e fotos sem padronização dificultam perceber a evolução da lesão.'
    },
    {
      icon: MessagesSquare,
      title: 'Continuidade do cuidado',
      text: 'Sem um histórico organizado, a comunicação entre profissionais fica mais difícil.'
    }
  ] satisfies SlideItem[],
  source: 'Base: Sibbald et al. (2021); van Netten et al. (2017).'
};

export const idea = {
  eyebrow: 'A ideia inicial',
  title: 'Uma plataforma digital para apoiar quem cuida.',
  lead: 'Objetivo: auxiliar profissionais de saúde no acompanhamento da evolução de feridas crônicas.',
  items: [
    { icon: Users, title: 'Registrar', text: 'Pacientes e avaliações das feridas em campos estruturados.' },
    { icon: Images, title: 'Organizar', text: 'Imagens e históricos para comparar a evolução entre consultas.' },
    { icon: ScanSearch, title: 'Apoiar com IA', text: 'Delimitar áreas lesionadas nas imagens para auxiliar a análise.' }
  ] satisfies SlideItem[]
};

export const workflow = {
  eyebrow: 'Como funciona',
  title: 'Do cadastro ao relatório, sem perder o contexto.',
  items: [
    { icon: ClipboardCheck, title: 'Cadastrar', text: 'Dados essenciais do paciente e o contexto inicial do acompanhamento.' },
    { icon: Camera, title: 'Avaliar', text: 'Sinais, medidas, observações e fotografias em campos clínicos estruturados.' },
    { icon: ScanLine, title: 'Comparar', text: 'Imagens lado a lado e região de interesse para revisar mudanças ao longo do tempo.' },
    { icon: FileText, title: 'Documentar', text: 'Evolução consolidada em relatórios preparados para revisão profissional.' }
  ] satisfies SlideItem[],
  note: 'Demonstração ao vivo somente com dados fictícios.'
};

export const aiSupport = {
  eyebrow: 'Inteligência artificial e visão computacional',
  title: 'A IA ajuda a enxergar. A decisão continua com o profissional.',
  items: [
    { icon: Camera, title: 'Qualidade da imagem', text: 'Confere foco, iluminação e enquadramento antes da análise.' },
    { icon: ScanEye, title: 'Delimitação da lesão', text: 'Destaca a região da ferida na fotografia.' },
    { icon: Layers, title: 'Tecidos', text: 'Identificação visual dos tipos de tecido no leito da ferida.' },
    { icon: Sparkles, title: 'Comparação', text: 'Indicadores quantitativos entre avaliações, como antes e depois de um procedimento.' },
    { icon: UserCheck, title: 'Revisão humana', text: 'Toda saída é revisada por quem cuida do paciente.' }
  ] satisfies SlideItem[],
  caution:
    'Resultado experimental: na avaliação pré e pós-desbridamento, o protótipo mostrou potencial para apoiar o acompanhamento, mas ainda precisa de ajustes e validação clínica.'
};

export const journey = {
  eyebrow: 'Nossa trajetória',
  title: 'Da sala de aula à pesquisa aplicada em saúde digital.',
  items: [
    {
      icon: Lightbulb,
      title: 'A ideia',
      text: 'Estudantes de ADS da Fatec Ferraz de Vasconcelos, com orientação docente, propõem uma ferramenta para o acompanhamento de feridas.'
    },
    {
      icon: MonitorSmartphone,
      title: 'O protótipo',
      text: 'Plataforma web com pacientes, avaliações estruturadas, imagens, comparação da evolução e relatórios.'
    },
    {
      icon: Network,
      title: 'Chamada da RNP',
      text: 'Participação na chamada pública da RNP, no Programa Redes de Colaboração em Saúde Digital (cluster REDI-SUS).'
    },
    {
      icon: BrainCircuit,
      title: 'Hoje',
      text: 'Contribuímos com um módulo de análise de imagens por IA, integrado pelo padrão de interoperabilidade em saúde HL7 FHIR.',
      current: true
    }
  ] satisfies TimelineItem[]
};

export const skills = {
  eyebrow: 'Formação Etec + Fatec',
  title: 'Competências que o mercado procura, desenvolvidas em um problema real.',
  items: [
    { icon: Code2, title: 'Desenvolvimento web', text: 'React, TypeScript e interfaces acessíveis.' },
    { icon: Server, title: 'APIs e back-end', text: 'Python, serviços e integração entre sistemas.' },
    { icon: ScanEye, title: 'IA e visão computacional', text: 'Processamento de imagens com OpenCV e aprendizado de máquina.' },
    { icon: ShieldCheck, title: 'Dados e privacidade', text: 'Banco de dados, controle de acesso e LGPD.' },
    { icon: Network, title: 'Interoperabilidade', text: 'Padrão HL7 FHIR para troca de informações em saúde.' },
    { icon: TestTubeDiagonal, title: 'Qualidade de software', text: 'Testes automatizados, integração contínua e versionamento.' }
  ] satisfies SlideItem[],
  note: 'Trabalho multidisciplinar entre tecnologia e saúde, com orientação docente.'
};

export const partnership = {
  eyebrow: 'Parcerias',
  title: 'Projetos como o Heal+ crescem perto das empresas.',
  lead: 'O novo curso integrado Etec + Fatec do Centro Paula Souza aproxima a formação técnica e tecnológica dos desafios reais do mercado.',
  items: [
    { icon: Lightbulb, title: 'Desafios reais', text: 'Problemas do dia a dia da empresa viram projetos dos estudantes.' },
    { icon: Handshake, title: 'Mentoria', text: 'Profissionais compartilham experiência com alunos e professores.' },
    { icon: Briefcase, title: 'Estágios e visitas', text: 'Contato com o ambiente de trabalho desde a formação técnica.' },
    { icon: Wrench, title: 'Infraestrutura', text: 'Equipamentos, softwares e ambientes que ampliam o que se pode construir.' }
  ] satisfies SlideItem[]
};

export const team = {
  eyebrow: 'Equipe',
  title: 'Obrigado!',
  authors: [
    'Guilherme Alves de Campos',
    'Paulo Henrique Leal dos Santos',
    'Pedro Antonio Silvestre Tescaro',
    'Vitoria Amelia Silva'
  ],
  advisors: ['Marcia Aparecida Silva Bissaco', 'Daisy Eboli', 'Rogério Bezerra Costa']
};

export const disclaimer = 'Protótipo acadêmico em desenvolvimento. Não substitui a avaliação profissional.';
