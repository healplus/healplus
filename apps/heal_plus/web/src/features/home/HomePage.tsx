import {
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  Camera,
  Check,
  ChevronDown,
  ClipboardCheck,
  FileText,
  Image as ImageIcon,
  Globe2,
  LockKeyhole,
  Menu,
  Moon,
  ScanLine,
  ShieldCheck,
  Stethoscope,
  Sun,
  X
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { useTheme } from '../../app/providers/ThemeProvider';
import DotField from '../../components/ui/DotField';
import { Marquee } from '../../components/ui/magic-surface';

type Language = 'pt' | 'en';

const content = {
  pt: {
    navPlatform: 'Plataforma',
    navFlow: 'Fluxo clínico',
    navSafety: 'Segurança',
    navPartners: 'Instituições',
    access: 'Acessar',
    signIn: 'Entrar',
    project: 'O projeto',
    technology: 'Tecnologia',
    heroBadge: 'Plataforma de apoio ao diagnóstico de feridas',
    heroLine1: 'Cuidado inteligente.',
    heroLine2: 'Evolução visível.',
    heroDescription: 'O Heal+ transforma o acompanhamento de feridas em um fluxo claro: cadastro, avaliação, imagem, ROI, comparativo e relatório em uma base preparada para integrar o ecossistema REDI-SUS.',
    heroSecondary: 'Conhecer plataforma',
    stat1: 'Fluxo clínico centralizado',
    stat2: 'Imagens e evidências visuais',
    stat3: 'Base preparada para análise assistida',
    stat4: 'Relatórios e histórico longitudinal',
    primaryCta: 'Acessar área clínica',
    flowEyebrow: 'Um fluxo, todo o contexto',
    flowTitle: 'Da primeira avaliação ao relatório, sem perder a continuidade.',
    flowText:
      'Cada etapa mantém o contexto anterior visível, reduz retrabalho e ajuda a equipe a documentar decisões com consistência.',
    platformEyebrow: 'Experiência clínica',
    platformTitle: 'Informação certa, no momento em que a equipe precisa.',
    platformText:
      'Uma interface criada para leitura rápida, registro responsável e comparação longitudinal — sem transformar apoio computacional em diagnóstico definitivo.',
    cardTimeline: 'Linha do tempo clara',
    cardTimelineText: 'Avaliações, imagens e condutas organizadas em sequência para facilitar a revisão do caso.',
    cardImages: 'Evidência visual comparável',
    cardImagesText: 'Demarcação de região de interesse e imagens lado a lado para acompanhar mudanças ao longo do tempo.',
    cardReports: 'Documentação consistente',
    cardReportsText: 'Relatórios estruturados para revisão profissional, pesquisa e continuidade do cuidado.',
    safetyEyebrow: 'Segurança clínica e privacidade',
    safetyTitle: 'Tecnologia para apoiar o cuidado — com limites claros.',
    safetyText:
      'O Heal+ organiza evidências e oferece suporte à análise. A avaliação, a interpretação e a conduta permanecem sob responsabilidade profissional.',
    safetyItem1: 'Minimização de dados e acesso autenticado',
    safetyItem2: 'Histórico rastreável e isolamento por usuário',
    safetyItem3: 'IA apresentada como apoio, nunca como diagnóstico definitivo',
    references: 'Ver referências técnicas',
    partnersEyebrow: 'Apoio institucional',
    partnersTitle: 'Pesquisa aplicada conectada ao ecossistema de saúde digital.',
    faqEyebrow: 'FAQ',
    faqTitle: 'Perguntas frequentes.',
    faqDescription: 'Respostas rápidas sobre o Heal+, acesso ao módulo e uso na rotina clínica.',
    faq1: 'O Heal+ é gratuito?',
    faqA1: 'O Heal+ é um módulo integrado ao ambiente REDI-SUS e seu acesso é regulado pelas diretrizes do cluster parceiro.',
    faq2: 'Preciso de equipamento especial?',
    faqA2: 'Não. O registro de imagens pode ser realizado utilizando a câmera nativa de dispositivos móveis como tablets e smartphones da instituição.',
    faq3: 'Os dados dos pacientes ficam seguros?',
    faqA3: 'Sim. A aplicação foi desenhada considerando LGPD, anonimização e RBAC (Role-Based Access Control) robustos.',
    faq4: 'O módulo já faz diagnósticos por IA?',
    faqA4: 'No momento, preparamos a base da inteligência. Os modelos e segmentações estão em desenvolvimento, e a documentação serve de alicerce para tal.',
    finalEyebrow: 'Pronto para começar?',
    finalTitle: 'Transforme registros dispersos em uma evolução clínica compreensível.',
    finalCta: 'Entrar no Heal+',
    footerText: 'Módulo de saúde digital do cluster REDI-SUS para apoio à avaliação, acompanhamento e documentação de feridas crônicas.',
    copyright: 'Pesquisa aplicada em saúde digital.'
  },
  en: {
    navPlatform: 'Platform',
    navFlow: 'Clinical flow',
    navSafety: 'Safety',
    navPartners: 'Institutions',
    access: 'Access',
    signIn: 'Sign in',
    project: 'The project',
    technology: 'Technology',
    heroBadge: 'Wound diagnostics support platform',
    heroLine1: 'Smart care.',
    heroLine2: 'Visible evolution.',
    heroDescription: 'Heal+ transforms wound monitoring into a clear workflow: registration, evaluation, imaging, ROI, comparison, and reporting in a platform prepared to integrate with the REDI-SUS ecosystem.',
    heroSecondary: 'Discover platform',
    stat1: 'Centralized clinical flow',
    stat2: 'Images and visual evidence',
    stat3: 'Analysis-ready foundation',
    stat4: 'Reports and longitudinal history',
    primaryCta: 'Access clinical area',
    flowEyebrow: 'One flow, full context',
    flowTitle: 'From the first assessment to the report, without losing continuity.',
    flowText:
      'Each step keeps previous context visible, reduces rework and helps teams document decisions consistently.',
    platformEyebrow: 'Clinical experience',
    platformTitle: 'The right information when the team needs it.',
    platformText:
      'An interface designed for quick reading, responsible records and longitudinal comparison — without presenting computational support as a final diagnosis.',
    cardTimeline: 'A clear timeline',
    cardTimelineText: 'Assessments, images and decisions arranged in sequence to make case review easier.',
    cardImages: 'Comparable visual evidence',
    cardImagesText: 'Region-of-interest marking and side-by-side images to follow changes over time.',
    cardReports: 'Consistent documentation',
    cardReportsText: 'Structured reports for professional review, research and continuity of care.',
    safetyEyebrow: 'Clinical safety and privacy',
    safetyTitle: 'Technology that supports care — with clear boundaries.',
    safetyText:
      'Heal+ organizes evidence and supports analysis. Assessment, interpretation and care decisions remain with healthcare professionals.',
    safetyItem1: 'Data minimization and authenticated access',
    safetyItem2: 'Traceable history and per-user isolation',
    safetyItem3: 'AI presented as support, never as a final diagnosis',
    references: 'View technical references',
    partnersEyebrow: 'Institutional support',
    partnersTitle: 'Applied research connected to the digital health ecosystem.',
    faqEyebrow: 'FAQ',
    faqTitle: 'Frequently asked questions.',
    faqDescription: 'Quick answers about Heal+, clinical module access and daily use.',
    faq1: 'Is Heal+ free?',
    faqA1: 'Heal+ is a module integrated into the REDI-SUS environment and access is governed by the partner cluster guidelines.',
    faq2: 'Do I need special equipment?',
    faqA2: 'No. Images can be captured using the native camera on compatible institutional mobile devices such as tablets and smartphones.',
    faq3: 'Is patient data protected?',
    faqA3: 'Yes. The application was designed with privacy, anonymization and robust role-based access control in mind.',
    faq4: 'Does the module already provide AI diagnoses?',
    faqA4: 'Not at this time. The analytical foundation is being prepared and computational models remain under development.',
    finalEyebrow: 'Ready to begin?',
    finalTitle: 'Turn scattered records into understandable clinical progress.',
    finalCta: 'Sign in to Heal+',
    footerText: 'REDI-SUS digital health module supporting wound assessment, longitudinal monitoring and clinical documentation.',
    copyright: 'Applied research in digital health.'
  }
} as const;

const flowIcons = [ClipboardCheck, Camera, ScanLine, FileText];

const partners = [
  { name: 'RNP', light: '/images/partners/rnp.png', dark: '/images/partners/rnp_modoDark.png' },
  { name: 'Fatec Ferraz de Vasconcelos', light: '/images/partners/fatec-ferraz.png', dark: '/images/partners/fatec-ferraz.png' },
  { name: 'Centro Paula Souza', light: '/images/partners/cps.svg', dark: '/images/partners/cps_modoDark.svg' }
];

export default function HomePage() {
  const { theme, toggleTheme } = useTheme();
  const [language, setLanguage] = useState<Language>('pt');
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [isScrolled, setIsScrolled] = useState(false);
  const [openFaq, setOpenFaq] = useState<number | null>(null);
  const t = content[language];

  useEffect(() => {
    const updateScrollState = () => setIsScrolled(window.scrollY > 56);
    updateScrollState();
    window.addEventListener('scroll', updateScrollState, { passive: true });
    return () => window.removeEventListener('scroll', updateScrollState);
  }, []);

  const flow = [
    { title: language === 'pt' ? 'Cadastrar' : 'Register', text: language === 'pt' ? 'Organize dados essenciais do paciente e o contexto inicial do acompanhamento.' : 'Organize essential patient data and the initial monitoring context.' },
    { title: language === 'pt' ? 'Avaliar' : 'Assess', text: language === 'pt' ? 'Registre sinais, medidas e observações em campos clínicos estruturados.' : 'Record signs, measurements and notes in structured clinical fields.' },
    { title: language === 'pt' ? 'Comparar' : 'Compare', text: language === 'pt' ? 'Use imagens e ROI para revisar mudanças entre diferentes momentos.' : 'Use images and ROI to review changes between different moments.' },
    { title: language === 'pt' ? 'Documentar' : 'Document', text: language === 'pt' ? 'Consolide a evolução em relatórios preparados para revisão profissional.' : 'Consolidate progress in reports prepared for professional review.' }
  ];

  const marqueeItems = [
    language === 'pt' ? 'Cadastro estruturado' : 'Structured registration',
    language === 'pt' ? 'Avaliação TIMERS' : 'TIMERS assessment',
    language === 'pt' ? 'Registro fotográfico' : 'Photographic record',
    language === 'pt' ? 'Demarcação de ROI' : 'ROI marking',
    language === 'pt' ? 'Comparação longitudinal' : 'Longitudinal comparison',
    language === 'pt' ? 'Relatórios clínicos' : 'Clinical reports'
  ].map(item => (
    <span key={item} className="flex items-center gap-3 text-sm font-bold text-slate-600 dark:text-slate-300">
      <Check className="h-4 w-4 text-heal-teal" aria-hidden="true" />
      {item}
    </span>
  ));

  const navItems = [
    { href: '#plataforma', label: t.navPlatform },
    { href: '#fluxo', label: t.navFlow },
    { href: '#seguranca', label: t.navSafety },
    { href: '#instituicoes', label: t.navPartners }
  ];

  const closeMenu = () => setMobileMenuOpen(false);
  const handleScroll = (event: React.MouseEvent<HTMLAnchorElement>, id: string) => {
    event.preventDefault();
    closeMenu();
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const heroStats = [
    { value: '01', label: t.stat1 },
    { value: 'ROI', label: t.stat2 },
    { value: 'IA', label: t.stat3 },
    { value: 'PDF', label: t.stat4 }
  ];

  return (
    <div className="min-h-screen overflow-x-hidden bg-white text-slate-950 transition-colors dark:bg-[#111111] dark:text-white">
      <nav
        aria-label="Navegação principal"
        className={`fixed inset-x-0 z-50 mx-auto border transition-[top,width,max-width,background-color,border-color,border-radius,box-shadow,backdrop-filter] duration-500 ease-out ${
          isScrolled
            ? theme === 'dark'
              ? 'top-4 w-[calc(100%_-_3rem)] max-w-6xl rounded-[18px] border-white/10 bg-[#111111]/90 text-white shadow-2xl backdrop-blur-2xl'
              : 'top-4 w-[calc(100%_-_3rem)] max-w-6xl rounded-[18px] border-slate-200 bg-white/90 text-slate-900 shadow-2xl backdrop-blur-2xl'
            : theme === 'dark'
              ? 'top-3 w-[calc(100%_-_1.5rem)] max-w-[1536px] rounded-none border-transparent bg-transparent text-white shadow-none backdrop-blur-none'
              : 'top-3 w-[calc(100%_-_1.5rem)] max-w-[1536px] rounded-none border-transparent bg-transparent text-slate-900 shadow-none backdrop-blur-none'
        }`}
      >
        <div className={`flex w-full items-center justify-between transition-[padding] duration-500 ease-out ${isScrolled ? 'px-4 py-3 sm:px-6' : 'px-4 py-5 sm:px-10'}`}>
          <Link to="/" className="group flex items-center gap-3" aria-label="Heal+ — início">
            <img src="/images/Logo_final_modobranco.png" alt="Heal+" className="h-8 w-auto shrink-0 object-contain transition-transform duration-300 group-hover:scale-[1.03] sm:h-9" />
            <span className={`hidden items-center gap-2 border-l pl-3 font-mono text-[10px] uppercase tracking-widest xl:inline-flex ${theme === 'dark' ? 'border-white/15 text-slate-400' : 'border-slate-300 font-semibold text-slate-600'}`}>
              REDI-SUS CLUSTER
            </span>
          </Link>

          <div className="hidden items-center gap-5 lg:flex xl:gap-7">
            {navItems.map(item => (
              <a key={item.href} href={item.href} onClick={event => handleScroll(event, item.href.slice(1))} className={`whitespace-nowrap text-sm font-semibold transition-colors ${theme === 'dark' ? 'text-slate-300 hover:text-white' : 'text-slate-700 hover:text-heal-blue'}`}>
                {item.label}
              </a>
            ))}
          </div>

          <div className="flex items-center gap-2 sm:gap-3">
            <button type="button" onClick={() => setLanguage(current => (current === 'pt' ? 'en' : 'pt'))} className={`hidden items-center gap-1.5 rounded-xl border px-3 py-2 text-xs font-bold transition-all xl:flex ${theme === 'dark' ? 'border-white/10 bg-white/[0.04] text-slate-300 hover:bg-white/10' : 'border-slate-200 bg-slate-100/90 text-slate-700 hover:bg-slate-200'}`} aria-label={language === 'pt' ? 'Mudar idioma para inglês' : 'Change language to Portuguese'}>
              <Globe2 className="h-[14px] w-[14px]" />
              {language.toUpperCase()}
            </button>
            <button type="button" onClick={toggleTheme} className={`inline-flex h-10 w-10 items-center justify-center rounded-xl transition-all ${theme === 'dark' ? 'text-slate-300 hover:bg-white/10 hover:text-heal-blue' : 'text-slate-700 hover:bg-slate-100 hover:text-heal-blue'}`} aria-label="Alternar Tema">
              {theme === 'dark' ? <Sun size={18} className="text-heal-blue" /> : <Moon size={18} />}
            </button>
            <Link to="/login" className={`hidden rounded-xl px-4 py-2.5 text-sm font-semibold transition-colors lg:inline-flex ${theme === 'dark' ? 'text-slate-300 hover:text-white' : 'text-slate-700 hover:text-heal-blue'}`}>
              {t.signIn}
            </Link>
            <Link to="/login" className={`inline-flex shrink-0 items-center justify-center gap-1.5 rounded-full px-3 py-2 text-xs font-semibold shadow-blue transition-all hover:scale-[1.03] active:scale-95 sm:px-5 sm:py-2.5 sm:text-sm ${theme === 'dark' ? 'bg-white text-slate-950 shadow-white/10 hover:bg-slate-100' : 'bg-heal-blue text-slate-950 hover:bg-heal-blueDark'}`} aria-label={t.primaryCta}>
              <span>{t.access}</span><ArrowUpRight size={15} strokeWidth={2.5} />
            </Link>
            <button type="button" onClick={() => setMobileMenuOpen(open => !open)} className={`inline-flex h-10 w-10 items-center justify-center rounded-xl border transition-colors lg:hidden ${theme === 'dark' ? 'border-white/10 bg-white/[0.04] text-white hover:border-heal-blue/50' : 'border-slate-200 bg-slate-100 text-slate-800 hover:border-slate-300'}`} aria-label={mobileMenuOpen ? 'Fechar menu' : 'Abrir menu'} aria-expanded={mobileMenuOpen}>
              {mobileMenuOpen ? <X size={18} /> : <Menu size={18} />}
            </button>
          </div>
        </div>

        {mobileMenuOpen ? (
          <div className={`landing-mobile-menu absolute left-0 top-full mt-2 w-full rounded-2xl border p-4 shadow-xl backdrop-blur-2xl lg:hidden ${theme === 'dark' ? 'border-white/10 bg-[#111111]/95 text-slate-200' : 'border-slate-200 bg-white/95 text-slate-800'}`}>
            <div className="grid gap-2">
              {navItems.map((item, index) => (
                <a key={item.href} href={item.href} onClick={event => handleScroll(event, item.href.slice(1))} className={`flex items-center justify-between rounded-xl px-4 py-3 text-sm font-bold transition-colors ${theme === 'dark' ? 'hover:bg-heal-blue/10 hover:text-heal-blue' : 'hover:bg-slate-100 hover:text-heal-blue'}`} style={{ animationDelay: `${index * 45}ms` }}>
                  {item.label}<ArrowUpRight size={17} />
                </a>
              ))}
              <div className={`mt-2 grid gap-2 border-t pt-3 ${theme === 'dark' ? 'border-white/10' : 'border-slate-200'}`}>
                <button type="button" onClick={() => setLanguage(current => (current === 'pt' ? 'en' : 'pt'))} className={`flex items-center justify-between rounded-xl px-4 py-3 text-sm font-bold transition-colors ${theme === 'dark' ? 'hover:bg-white/10 hover:text-white' : 'hover:bg-slate-100 hover:text-heal-blue'}`} style={{ animationDelay: `${navItems.length * 45}ms` }} aria-label={language === 'pt' ? 'Mudar idioma para inglês' : 'Change language to Portuguese'}>
                  <span className="inline-flex items-center gap-2"><Globe2 className="h-4 w-4" />{language.toUpperCase()}</span>
                  <ArrowUpRight size={17} />
                </button>
                <Link to="/login" onClick={closeMenu} className={`flex items-center justify-between rounded-xl px-4 py-3 text-sm font-bold transition-colors ${theme === 'dark' ? 'hover:bg-white/10 hover:text-white' : 'hover:bg-slate-100 hover:text-heal-blue'}`} style={{ animationDelay: `${(navItems.length + 1) * 45}ms` }}>
                  {t.signIn}<ArrowUpRight size={17} />
                </Link>
              </div>
            </div>
          </div>
        ) : null}
      </nav>

      <main className="pt-0">
        <section id="projeto" className="relative isolate flex min-h-[95vh] items-center justify-center overflow-hidden border-b border-slate-200 bg-white text-slate-900 transition-colors dark:border-white/10 dark:bg-[#111111] dark:text-white">
          <div className="pointer-events-auto absolute inset-0 z-0 opacity-75">
            <DotField dotRadius={1.5} dotSpacing={14} bulgeStrength={67} glowRadius={0} sparkle={false} waveAmplitude={0} gradientFrom={theme === 'dark' ? '#4cc3f2' : '#29abe2'} gradientTo={theme === 'dark' ? 'rgba(76, 195, 242, 0.18)' : 'rgba(41, 171, 226, 0.08)'} glowColor="transparent" />
          </div>

          <div className="relative z-10 mx-auto flex w-full max-w-4xl flex-col items-center px-5 py-32 text-center md:py-40">
            <div className={`inline-flex items-center gap-2.5 rounded-full border px-3.5 py-1.5 text-xs font-semibold shadow-md backdrop-blur-md ${theme === 'dark' ? 'border-white/10 bg-white/[0.06] text-slate-200' : 'border-slate-200/90 bg-white/90 text-slate-700 shadow-slate-200/60'}`}>
              <span className={`rounded-full px-2 py-0.5 text-[10px] font-black uppercase tracking-wider ${theme === 'dark' ? 'bg-white text-slate-950' : 'bg-heal-blue text-slate-950'}`}>NEW</span>
              <span className={theme === 'dark' ? 'text-slate-300' : 'font-medium text-slate-700'}>{t.heroBadge}</span>
            </div>

            <h1 className="mt-8 max-w-4xl font-headline text-4xl font-black leading-[1.08] tracking-[-0.04em] md:text-6xl lg:text-[4.5rem]">
              <span className={theme === 'dark' ? 'text-white' : 'text-heal-blue'}>{t.heroLine1}</span>
              <span className={`block bg-gradient-to-r bg-clip-text text-transparent ${theme === 'dark' ? 'from-white via-[#9ee2ff] to-heal-blue' : 'from-heal-blue via-[#29abe2] to-[#6cd6ff]'}`}>{t.heroLine2}</span>
            </h1>

            <p className={`mt-6 max-w-2xl text-base font-normal leading-8 md:text-lg ${theme === 'dark' ? 'text-slate-300' : 'font-medium text-slate-600'}`}>{t.heroDescription}</p>

            <div className="mt-10 flex flex-col gap-4 sm:flex-row sm:items-center">
              <Link to="/login" className={`inline-flex items-center justify-center gap-2.5 rounded-full px-8 py-3.5 text-base font-black shadow-blue transition-all duration-300 hover:scale-[1.02] active:scale-95 ${theme === 'dark' ? 'bg-white text-slate-950 shadow-white/10 hover:bg-slate-100' : 'bg-heal-blue text-slate-950 hover:bg-heal-blueDark'}`}>
                {t.primaryCta}<ArrowRight size={20} strokeWidth={3} />
              </Link>
              <a href="#plataforma" onClick={event => handleScroll(event, 'plataforma')} className={`inline-flex items-center justify-center gap-2.5 rounded-full border px-8 py-3.5 text-base font-black backdrop-blur-md transition-all duration-300 active:scale-95 ${theme === 'dark' ? 'border-white/15 bg-white/[0.06] text-white hover:bg-white/10' : 'border-slate-300 bg-white/90 text-slate-800 shadow-sm hover:bg-slate-100'}`}>
                {t.heroSecondary}<ArrowUpRight size={19} strokeWidth={3} />
              </a>
            </div>

            <div className="mt-14 grid w-full max-w-3xl grid-cols-2 gap-3 sm:grid-cols-4">
              {heroStats.map(item => (
                <div key={item.label} className={`flex min-h-[96px] flex-col items-center justify-center rounded-[18px] border px-4 py-3.5 text-center shadow-lg backdrop-blur-md ${theme === 'dark' ? 'border-white/10 bg-[#0d1117]/70 text-slate-300' : 'border-slate-200/80 bg-white/85 text-slate-700 shadow-sm'}`}>
                  <p className="font-headline text-xl font-black text-heal-blue">{item.value}</p>
                  <p className={`mt-1.5 text-[11px] font-extrabold uppercase leading-4 tracking-wider ${theme === 'dark' ? 'text-slate-300' : 'text-slate-600'}`}>{item.label}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section aria-label="Recursos da plataforma" className="border-b border-slate-200 bg-white py-4 dark:border-white/10 dark:bg-[#111111]">
          <Marquee items={marqueeItems} />
        </section>

        <section id="fluxo" className="bg-white py-24 dark:bg-[#111111] md:py-32">
          <div className="mx-auto max-w-7xl px-5 md:px-8">
            <div className="grid gap-8 lg:grid-cols-[0.8fr_1.2fr] lg:items-end">
              <div>
                <p className="text-xs font-extrabold uppercase tracking-[0.22em] text-heal-blue">{t.flowEyebrow}</p>
                <h2 className="mt-4 font-headline text-4xl font-extrabold leading-tight tracking-[-0.04em] text-slate-950 dark:text-white md:text-5xl">{t.flowTitle}</h2>
              </div>
              <p className="max-w-2xl text-base leading-8 text-slate-600 dark:text-slate-300 lg:justify-self-end">{t.flowText}</p>
            </div>

            <div className="mt-14 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              {flow.map((item, index) => {
                const Icon = flowIcons[index];
                return (
                  <article key={item.title} className="magic-hover-card group rounded-[1.75rem] border border-slate-200 bg-white p-6 dark:border-white/10 dark:bg-white/[0.035]">
                    <div className="flex items-center justify-between">
                      <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-heal-blue/12 text-heal-blue transition-colors group-hover:bg-heal-blue group-hover:text-slate-950 dark:text-heal-blue">
                        <Icon className="h-5 w-5" />
                      </span>
                      <span className="text-xs font-extrabold tracking-[0.18em] text-slate-400">0{index + 1}</span>
                    </div>
                    <h3 className="mt-7 text-xl font-extrabold text-slate-950 dark:text-white">{item.title}</h3>
                    <p className="mt-3 text-sm leading-7 text-slate-600 dark:text-slate-400">{item.text}</p>
                  </article>
                );
              })}
            </div>
          </div>
        </section>

        <section id="plataforma" className="border-y border-slate-200 bg-white py-24 dark:border-white/10 dark:bg-[#111111] md:py-32">
          <div className="mx-auto max-w-7xl px-5 md:px-8">
            <div className="mx-auto max-w-3xl text-center">
              <p className="text-xs font-extrabold uppercase tracking-[0.22em] text-heal-blue">{t.platformEyebrow}</p>
              <h2 className="mt-4 font-headline text-4xl font-extrabold leading-tight tracking-[-0.04em] text-slate-950 dark:text-white md:text-5xl">{t.platformTitle}</h2>
              <p className="mt-6 text-base leading-8 text-slate-600 dark:text-slate-300">{t.platformText}</p>
            </div>

            <div className="mt-14 grid gap-5 lg:grid-cols-2">
              <article className="magic-hover-card relative overflow-hidden rounded-[2rem] border border-slate-200 bg-white p-8 dark:border-white/10 dark:bg-white/[0.035] lg:row-span-2">
                <div className="absolute right-0 top-0 h-56 w-56 rounded-full bg-heal-blue/10 blur-3xl" />
                <div className="relative">
                  <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-heal-blue/15 text-heal-blue dark:text-heal-blue"><BarChart3 className="h-6 w-6" /></span>
                  <h3 className="mt-7 text-2xl font-extrabold text-slate-950 dark:text-white">{t.cardTimeline}</h3>
                  <p className="mt-3 max-w-lg text-sm leading-7 text-slate-600 dark:text-slate-400">{t.cardTimelineText}</p>
                  <div className="mt-10 space-y-4 border-l-2 border-heal-blue/20 pl-6">
                    {[language === 'pt' ? 'Registro inicial' : 'Initial record', language === 'pt' ? 'Reavaliação' : 'Reassessment', language === 'pt' ? 'Comparativo' : 'Comparison'].map((label, index) => (
                      <div key={label} className="relative rounded-2xl border border-slate-200 bg-slate-50 p-4 dark:border-white/10 dark:bg-white/[0.04]">
                        <span className="absolute -left-[2.05rem] top-5 h-3 w-3 rounded-full border-2 border-white bg-heal-blue dark:border-[#0a101a]" />
                        <p className="text-sm font-bold text-slate-800 dark:text-slate-200">{label}</p>
                        <div className={`mt-2 h-1.5 rounded-full ${index === 0 ? 'w-1/3 bg-heal-blue/30' : index === 1 ? 'w-2/3 bg-heal-blue/50' : 'w-full bg-heal-blue/80'}`} />
                      </div>
                    ))}
                  </div>
                </div>
              </article>

              <article className="magic-hover-card rounded-[2rem] border border-slate-200 bg-white p-8 dark:border-white/10 dark:bg-white/[0.035]">
                <div className="flex items-start gap-5">
                  <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-700 dark:bg-emerald-400/10 dark:text-emerald-300"><ImageIcon className="h-6 w-6" /></span>
                  <div><h3 className="text-xl font-extrabold text-slate-950 dark:text-white">{t.cardImages}</h3><p className="mt-3 text-sm leading-7 text-slate-600 dark:text-slate-400">{t.cardImagesText}</p></div>
                </div>
              </article>

              <article className="magic-hover-card rounded-[2rem] border border-slate-200 bg-white p-8 dark:border-white/10 dark:bg-white/[0.035]">
                <div className="flex items-start gap-5">
                  <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-violet-100 text-violet-700 dark:bg-violet-400/10 dark:text-violet-300"><FileText className="h-6 w-6" /></span>
                  <div><h3 className="text-xl font-extrabold text-slate-950 dark:text-white">{t.cardReports}</h3><p className="mt-3 text-sm leading-7 text-slate-600 dark:text-slate-400">{t.cardReportsText}</p></div>
                </div>
              </article>
            </div>
          </div>
        </section>

        <section id="seguranca" className="relative overflow-hidden bg-white py-24 text-slate-950 dark:bg-[#111111] dark:text-white md:py-32">
          <div className="relative mx-auto grid max-w-7xl gap-12 px-5 md:px-8 lg:grid-cols-[0.92fr_1.08fr] lg:items-center">
            <div>
              <p className="text-xs font-extrabold uppercase tracking-[0.22em] text-heal-blue">{t.safetyEyebrow}</p>
              <h2 className="mt-4 font-headline text-4xl font-extrabold leading-tight tracking-[-0.04em] md:text-5xl">{t.safetyTitle}</h2>
              <p className="mt-6 text-base leading-8 text-slate-600 dark:text-slate-300">{t.safetyText}</p>
              <Link to="/referencias" className="mt-8 inline-flex items-center gap-2 text-sm font-extrabold text-heal-blue hover:text-white">
                {t.references}<ArrowRight className="h-4 w-4" />
              </Link>
            </div>
            <div className="magic-card relative rounded-[2rem] border border-slate-200 bg-slate-50 p-7 backdrop-blur-xl dark:border-white/10 dark:bg-white/[0.055] sm:p-9">
              <div className="relative space-y-4">
                {[t.safetyItem1, t.safetyItem2, t.safetyItem3].map((item, index) => (
                  <div key={item} className="flex gap-4 rounded-2xl border border-slate-200 bg-white p-5 dark:border-white/10 dark:bg-black/20">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-heal-blue/15 text-heal-blue">{index === 0 ? <LockKeyhole className="h-5 w-5" /> : index === 1 ? <ShieldCheck className="h-5 w-5" /> : <Stethoscope className="h-5 w-5" />}</span>
                    <p className="self-center text-sm font-bold leading-6 text-slate-800 dark:text-slate-200">{item}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section id="instituicoes" className="border-b border-slate-200 bg-white py-20 dark:border-white/10 dark:bg-[#111111]">
          <div className="mx-auto max-w-7xl px-5 text-center md:px-8">
            <p className="text-xs font-extrabold uppercase tracking-[0.22em] text-heal-blue">{t.partnersEyebrow}</p>
            <h2 className="mx-auto mt-4 max-w-3xl font-headline text-3xl font-extrabold tracking-[-0.035em] text-slate-950 dark:text-white md:text-4xl">{t.partnersTitle}</h2>
            <div className="mt-12 grid overflow-hidden rounded-[2rem] border border-slate-200 sm:grid-cols-3 dark:border-white/10">
              {partners.map((partner, index) => (
                <div key={partner.name} className={`flex min-h-36 items-center justify-center bg-slate-50 p-8 transition-colors hover:bg-heal-blue/5 dark:bg-white/[0.025] ${index > 0 ? 'border-t border-slate-200 dark:border-white/10 sm:border-l sm:border-t-0' : ''}`}>
                  <img src={theme === 'dark' ? partner.dark : partner.light} alt={partner.name} className="max-h-16 max-w-[190px] object-contain" />
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="faq" className="border-t border-slate-100 bg-white py-[4.5rem] text-slate-800 dark:border-white/10 dark:bg-[#111111] dark:text-white">
          <div className="mx-auto max-w-5xl px-5 md:px-8">
            <div className="text-center">
              <div className="mx-auto inline-flex items-center justify-center gap-3 text-xs font-black uppercase tracking-[0.28em] text-heal-blue">
                <span className="h-px w-10 bg-heal-blue/30" />
                <span>{t.faqEyebrow}</span>
                <span className="h-px w-10 bg-heal-blue/30" />
              </div>
              <h2 className="mt-6 font-headline text-4xl font-black leading-tight tracking-[-0.04em] text-heal-blue dark:text-white md:text-6xl">{t.faqTitle}</h2>
              <p className="mx-auto mt-5 max-w-2xl text-base font-light leading-7 text-slate-500 dark:text-slate-400 md:text-lg">{t.faqDescription}</p>
            </div>

            <div className="mx-auto mt-10 grid max-w-4xl gap-3.5">
              {[[t.faq1, t.faqA1], [t.faq2, t.faqA2], [t.faq3, t.faqA3], [t.faq4, t.faqA4]].map(([question, answer], index) => {
                const isOpen = openFaq === index;
                return (
                  <article key={question} className={`rounded-[1.25rem] border px-6 py-5 shadow-sm transition-all duration-300 hover:border-heal-blue/30 hover:shadow-soft md:px-8 ${isOpen ? 'border-l-4 border-heal-blue/30 border-l-heal-blue bg-gradient-to-r from-heal-blue/[0.03] to-transparent dark:from-heal-blue/[0.06]' : theme === 'dark' ? 'border-slate-800 bg-[#181818]' : 'border-slate-200 bg-white'}`}>
                    <button type="button" onClick={() => setOpenFaq(isOpen ? null : index)} aria-expanded={isOpen} aria-controls={`faq-answer-${index}`} className="flex w-full items-center justify-between gap-6 text-left text-base font-bold text-slate-800 dark:text-white md:text-lg">
                      <span>{question}</span>
                      <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full border text-heal-blue transition-transform duration-300 ${theme === 'dark' ? 'border-slate-700 bg-[#1E1E20]' : 'border-slate-200 bg-slate-50'} ${isOpen ? 'rotate-180' : ''}`}>
                        <ChevronDown size={16} strokeWidth={2.5} />
                      </span>
                    </button>
                    <div id={`faq-answer-${index}`} className={`grid transition-all duration-300 ease-out ${isOpen ? 'mt-4 grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'}`}>
                      <div className="overflow-hidden"><p className="text-sm font-light leading-7 text-slate-500 dark:text-slate-400">{answer}</p></div>
                    </div>
                  </article>
                );
              })}
            </div>
          </div>
        </section>

        <section className="bg-white px-5 py-20 dark:bg-[#111111] md:px-8">
          <div className="landing-cta-panel relative mx-auto max-w-7xl overflow-hidden rounded-[2.5rem] px-7 py-14 text-center text-white shadow-[0_28px_90px_rgba(2,132,199,0.22)] sm:px-12 md:py-20">
            <div aria-hidden="true" className="landing-cta-orb absolute -right-20 -top-20 h-72 w-72 rounded-full blur-3xl" />
            <div className="relative mx-auto max-w-3xl">
              <p className="text-xs font-extrabold uppercase tracking-[0.22em] text-cyan-100">{t.finalEyebrow}</p>
              <h2 className="mt-5 font-headline text-4xl font-extrabold leading-tight tracking-[-0.04em] md:text-5xl">{t.finalTitle}</h2>
              <Link to="/login" className="mt-9 inline-flex h-14 items-center gap-2 rounded-full bg-white px-7 text-sm font-extrabold text-heal-blue transition-transform hover:-translate-y-1 hover:text-heal-blueDark">
                {t.finalCta}<ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-slate-100 bg-white text-slate-700 transition-colors dark:border-white/10 dark:bg-[#111111] dark:text-slate-400">
        <div className="relative z-10 mx-auto max-w-7xl px-5 py-12 md:px-8">
          <div className="grid gap-10 border-b border-slate-200 pb-12 dark:border-slate-800 lg:grid-cols-[0.8fr_1.2fr]">
            <div>
              <img src="/images/Logo_final_modobranco.png" alt="Heal+" className="h-9 w-auto object-contain" />
              <p className="mt-4 max-w-md text-xs font-medium leading-6 text-slate-600 dark:text-zinc-400">{t.footerText}</p>
            </div>

            <div className="grid gap-8 sm:grid-cols-3">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.24em] text-heal-blue">{t.navPlatform}</p>
                <div className="mt-4 space-y-3">
                  <a href="#projeto" onClick={event => handleScroll(event, 'projeto')} className="block text-sm font-medium text-slate-600 transition-colors hover:text-heal-blue dark:text-zinc-400">{t.project}</a>
                  <a href="#plataforma" onClick={event => handleScroll(event, 'plataforma')} className="block text-sm font-medium text-slate-600 transition-colors hover:text-heal-blue dark:text-zinc-400">{t.navPlatform}</a>
                </div>
              </div>
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.24em] text-heal-blue">{t.technology}</p>
                <div className="mt-4 space-y-3">
                  <a href="#seguranca" onClick={event => handleScroll(event, 'seguranca')} className="block text-sm font-medium text-slate-600 transition-colors hover:text-heal-blue dark:text-zinc-400">{t.navSafety}</a>
                  <Link to="/referencias" className="block text-sm font-medium text-slate-600 transition-colors hover:text-heal-blue dark:text-zinc-400">{t.references}</Link>
                </div>
              </div>
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.24em] text-heal-blue">{t.access}</p>
                <div className="mt-4 space-y-3">
                  <Link to="/login" className="block text-sm font-medium text-slate-600 transition-colors hover:text-heal-blue dark:text-zinc-400">{t.primaryCta}</Link>
                  <a href="#instituicoes" onClick={event => handleScroll(event, 'instituicoes')} className="block text-sm font-medium text-slate-600 transition-colors hover:text-heal-blue dark:text-zinc-400">{t.navPartners}</a>
                </div>
              </div>
            </div>
          </div>

          <div className="flex flex-col justify-between gap-4 pt-8 text-xs font-semibold text-slate-500 dark:text-zinc-500 md:flex-row md:items-center">
            <p>© {new Date().getFullYear()} HEAL+ REDI-SUS. {t.copyright}</p>
            <div className="flex flex-wrap gap-x-6 gap-y-2">
              <a href="#projeto" onClick={event => handleScroll(event, 'projeto')} className="hover:text-heal-blue hover:underline">{t.project}</a>
              <a href="#plataforma" onClick={event => handleScroll(event, 'plataforma')} className="hover:text-heal-blue hover:underline">{t.navPlatform}</a>
              <Link to="/login" className="hover:text-heal-blue hover:underline">{t.primaryCta}</Link>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
