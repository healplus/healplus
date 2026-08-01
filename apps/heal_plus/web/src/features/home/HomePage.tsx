import DotField from "../../components/ui/DotField";
import { useState, useRef, useEffect } from "react";
import Image from "next/image";
import Link from "next/link";
import { useTheme } from "../../app/providers/ThemeProvider";
import {
  ArrowRight,
  ArrowUpRight,
  BadgeCheck,
  BookOpenCheck,
  BrainCircuit,
  Camera,
  CheckCircle2,
  ChevronDown,
  ClipboardList,
  Cpu,
  Database,
  FileText,
  Globe2,
  Layers3,
  LineChart,
  LockKeyhole,
  Network,
  ScanLine,
  ShieldCheck,
  Sparkles,
  Stethoscope,
  Target,
  UserRoundCheck,
  Workflow,
  Sun,
  Moon,
  Menu,
  X,
} from "lucide-react";

const translations = {
  pt: {
    // Nav
    plataforma: "Plataforma",
    projeto: "O projeto",
    fluxo: "Fluxo",
    tecnologia: "Tecnologia",
    instituicoes: "Instituições",
    entrar: "Entrar",
    acessar: "Acessar",
    
    // Hero
    appClinico: "Plataforma de apoio ao diagnóstico de feridas",
    cuidadoInteligente: "Cuidado inteligente.",
    evolucaoVisivel: "Evolução visível.",
    heroSubtitle: "O Heal+ transforma o acompanhamento de feridas em um fluxo claro: cadastro, avaliação, imagem, ROI, comparativo e relatório em uma base preparada para integrar o ecossistema REDI-SUS.",
    acessarAreaClinica: "Acessar área clínica",
    conhecerPlataforma: "Conhecer plataforma",
    
    // Stats
    stat1: "Fluxo clínico centralizado",
    stat2: "Imagens e evidências visuais",
    stat3: "Base preparada para análise assistida",
    stat4: "Relatórios e histórico longitudinal",
    
    // Badges strip
    badge1: "Pacientes em ordem",
    badge2: "Avaliação estruturada",
    badge3: "Comparativo fotográfico",
    badge4: "Relatórios exportáveis",
    
    // Plataforma section
    plataformaTitle: "Uma central clínica para acompanhar feridas com clareza.",
    plataformaDesc: "Do primeiro registro ao acompanhamento longitudinal, o Heal+ conecta dados, imagens e decisões em uma experiência clínica simples de entender e rápida de usar.",
    focoExp: "Foco da experiência",
    focoDesc: "Menos tempo procurando informações. Mais contexto para avaliar, comparar a evolução e documentar cada conduta com segurança.",
    cardCadastrar: "Cadastrar",
    cardCadastrarDesc: "Organize pacientes, contatos, histórico e dados iniciais em uma experiência direta para a rotina clínica.",
    cardAvaliar: "Avaliar",
    cardAvaliarDesc: "Registre sinais clínicos, evolução, dor, tecido, borda, umidade e observações com campos estruturados.",
    cardROI: "Marcar ROI",
    cardROIDesc: "Prepare imagens para comparação, análise visual e documentação da evolução da ferida ao longo do tempo.",
    cardDocumentar: "Documentar",
    cardDocumentarDesc: "Gere relatórios, consolide evidências e entregue uma visão mais clara para revisão, pesquisa e auditoria.",

    // Fluxo section
    fluxoLabel: "Fluxo do módulo",
    fluxoTitle: "Do cadastro ao relatório, tudo segue uma sequência lógica.",
    fluxoDesc: "Cada etapa preserva o contexto da anterior, reduzindo retrabalho e criando um histórico confiável para a equipe, o paciente e a instituição.",
    step1Title: "Entrada clínica",
    step1Desc: "O profissional registra o paciente, adiciona dados iniciais e cria a base do acompanhamento.",
    step2Title: "Imagem e avaliação",
    step2Desc: "O acompanhamento é documentado com foto, ROI, sinais clínicos e observações do atendimento.",
    step3Title: "Comparativo de evolução",
    step3Desc: "O histórico permite visualizar mudanças, revisar condutas e acompanhar a resposta ao tratamento.",
    step4Title: "Relatório e integração",
    step4Desc: "O caso vira evidência estruturada para relatório, auditoria, pesquisa e integração com a plataforma.",

    // REDI-SUS Section
    clusterSus: "Cluster REDI-SUS",
    susTitle: "Um bloco de saúde digital dentro de uma arquitetura maior.",
    susDesc: "A proposta combina uma identidade visual limpa com mensagens fortes de confiança, integração e evolução clínica.",
    susCard1: "Módulo acoplável",
    susCard1Desc: "Estrutura pensada para conversar com o ecossistema REDI-SUS sem virar uma aplicação isolada.",
    susCard2: "Dados clínicos organizados",
    susCard2Desc: "Contratos para pacientes, lesões, imagens, avaliações, evolução e relatórios em um fluxo consistente.",
    susCard3: "Pronto para IA",
    susCard3Desc: "Base preparada para segmentação, classificação, comparação visual e apoio computacional no futuro.",
    susCard4: "Governança e acesso",
    susCard4Desc: "Arquitetura com foco em rastreabilidade, perfis de acesso e evolução segura da plataforma.",

    // Base tecnica
    techLabel: "Base técnica",
    techTitle: "Tecnologia clara, segura e pronta para evoluir.",
    techRef: "Referências do projeto",
    techCard1Label: "Interface web",
    techCard1Val: "Next.js, React e TypeScript para uma experiência responsiva, rápida e escalável.",
    techCard2Label: "Integração",
    techCard2Val: "APIs e contratos clínicos preparados para conectar o módulo ao REDI-SUS.",
    techCard3Label: "Camada analítica",
    techCard3Val: "Base para visão computacional, ROI, segmentação, classificação e relatórios inteligentes.",
    techCard4Label: "Segurança",
    techCard4Val: "RBAC, auditoria, separação de responsabilidades e cuidado com dados sensíveis de saúde.",

    // CTA
    ctaLabel: "Próximo passo",
    ctaTitle: "Leve o acompanhamento de feridas para uma experiência mais clara, visual e segura.",
    ctaBtn: "Acessar módulo",

    // FAQ
    faqLabel: "FAQ",
    faqTitle: "Perguntas frequentes.",
    faqDesc: "Respostas rápidas sobre o Heal+, acesso ao módulo e uso na rotina clínica.",
    faqQ1: "O Heal+ é gratuito?",
    faqA1: "O Heal+ é um módulo integrado ao ambiente REDI-SUS e seu acesso é regulado pelas diretrizes do cluster parceiro.",
    faqQ2: "Preciso de um equipamento especial?",
    faqA2: "Não. O registro de imagens pode ser realizado utilizando a câmera nativa de dispositivos móveis como tablets e smartphones da instituição.",
    faqQ3: "Os dados dos pacientes ficam seguros?",
    faqA3: "Sim. A aplicação foi desenhada considerando LGPD, anonimização e RBAC (Role-Based Access Control) robustos.",
    faqQ4: "O módulo já faz diagnósticos por IA?",
    faqA4: "No momento, preparamos a base da inteligência. Os modelos e segmentações estão em desenvolvimento, e a documentação serve de alicerce para tal.",

    // Footer
    footerDesc: "Módulo de saúde digital do cluster REDI-SUS para apoio à avaliação, acompanhamento e documentação de feridas crônicas.",
    supportDesc: "Projeto desenvolvido com apoio institucional da RNP, Fatec Ferraz de Vasconcelos e Centro Paula Souza.",
  },
  en: {
    // Nav
    plataforma: "Platform",
    projeto: "The project",
    fluxo: "Flow",
    tecnologia: "Technology",
    instituicoes: "Institutions",
    entrar: "Sign In",
    acessar: "Access",
    
    // Hero
    appClinico: "Wound diagnostics support platform",
    cuidadoInteligente: "Smart care.",
    evolucaoVisivel: "Visible evolution.",
    heroSubtitle: "Heal+ transforms wound monitoring into a clear workflow: registration, evaluation, imaging, ROI, comparison, and reporting in a platform prepared to integrate with the REDI-SUS ecosystem.",
    acessarAreaClinica: "Access clinical area",
    conhecerPlataforma: "Discover platform",
    
    // Stats
    stat1: "Centralized clinical flow",
    stat2: "Images & visual evidence",
    stat3: "AI-ready analysis base",
    stat4: "Reports & longitudinal history",
    
    // Badges strip
    badge1: "Organized patients",
    badge2: "Structured evaluation",
    badge3: "Photographic comparison",
    badge4: "Exportable reports",
    
    // Plataforma section
    plataformaTitle: "A clinical hub to monitor wounds with clarity.",
    plataformaDesc: "From the first record to longitudinal follow-up, Heal+ connects data, images, and decisions in a clinical experience that is easy to understand and quick to use.",
    focoExp: "Experience Focus",
    focoDesc: "Less time searching for information. More context to assess, compare progress, and document every care decision safely.",
    cardCadastrar: "Register",
    cardCadastrarDesc: "Organize patients, contacts, history, and intake data in a direct, easy-to-use clinical routine experience.",
    cardAvaliar: "Evaluate",
    cardAvaliarDesc: "Record clinical signs, progress, pain level, tissue, margins, exudate, and remarks with structured fields.",
    cardROI: "Mark ROI",
    cardROIDesc: "Prepare images for comparison, visual tracking, and wound progress documentation over time.",
    cardDocumentar: "Document",
    cardDocumentarDesc: "Generate reports, consolidate clinical evidence, and deliver a clear view for review, research, and audit.",

    // Fluxo section
    fluxoLabel: "Module Flow",
    fluxoTitle: "From intake to reporting, everything follows a logical path.",
    fluxoDesc: "Every step preserves the context of the previous one, reducing rework and creating a reliable history for teams, patients, and institutions.",
    step1Title: "Clinical Intake",
    step1Desc: "The practitioner registers the patient, adds initial records, and initializes the follow-up timeline.",
    step2Title: "Imaging & Assessment",
    step2Desc: "The wound status is documented with photos, ROI coordinates, clinical parameters, and notes.",
    step3Title: "Evolution Comparison",
    step3Desc: "A timeline history allows comparing changes, reviewing decisions, and tracking response to treatment.",
    step4Title: "Reporting & Integration",
    step4Desc: "The clinical case becomes structured evidence for auditing, research, and integration with other systems.",

    // REDI-SUS Section
    clusterSus: "REDI-SUS Cluster",
    susTitle: "A digital health block inside a larger clinical architecture.",
    susDesc: "The platform combines a clean visual identity with strong statements of trust, integration, and clinical evolution.",
    susCard1: "Pluggable Module",
    susCard1Desc: "Architecture designed to integrate smoothly with the REDI-SUS ecosystem without being isolated.",
    susCard2: "Structured Clinical Data",
    susCard2Desc: "Standardized schemas for patients, wounds, images, assessments, and reports in a unified flow.",
    susCard3: "AI-Ready",
    susCard3Desc: "Prepared dataset structure for computer vision, segmentations, visual comparisons, and clinical assistance.",
    susCard4: "Governance & Access",
    susCard4Desc: "Secure environment focusing on audit trails, distinct access roles, and platform compliance.",

    // Base tecnica
    techLabel: "Technical Base",
    techTitle: "Clear, secure technology, ready to scale.",
    techRef: "Project References",
    techCard1Label: "Web Interface",
    techCard1Val: "Next.js, React, and TypeScript for a fast, responsive, and highly scalable user experience.",
    techCard2Label: "Integration APIs",
    techCard2Val: "Clinically structured schemas and secure APIs built to bridge the module to the REDI-SUS cluster.",
    techCard3Label: "Analytical Layer",
    techCard3Val: "Underlying base for computer vision algorithms, ROI mapping, segmentations, and smart reporting.",
    techCard4Label: "Security Protocols",
    techCard4Val: "Role-based controls, logs, data isolation, and strict compliance with health data privacy rules.",

    // CTA
    ctaLabel: "Next Step",
    ctaTitle: "Bring wound tracking to a clearer, more visual, and highly secure digital experience.",
    ctaBtn: "Access module",

    // FAQ
    faqLabel: "FAQ",
    faqTitle: "Frequently asked questions.",
    faqDesc: "Quick answers about Heal+, clinical module access, and daily routine usage.",
    faqQ1: "Is Heal+ free?",
    faqA1: "Heal+ is a digital health module integrated into the REDI-SUS platform. Access rules depend on partner cluster agreements.",
    faqQ2: "Do I need special equipment?",
    faqA2: "No. High-quality clinical imaging can be recorded using standard built-in cameras on smartphones or tablets of the institution.",
    faqQ3: "Is patient data secure?",
    faqA3: "Yes. The system is designed following privacy acts, including anonymization protocols and granular role-based controls (RBAC).",
    faqQ4: "Does the module perform automated diagnosis?",
    faqA4: "Currently, we prepare the analytical foundation. Advanced models and automated segmentations are in active development.",

    // Footer
    footerDesc: "REDI-SUS digital health module for wound evaluation, longitudinal monitoring, and clinical documentation.",
    supportDesc: "Project developed with the institutional support of RNP, Fatec Ferraz de Vasconcelos, and Centro Paula Souza.",
  }
};

const institutionalLogos = [
  {
    name: "RNP",
    src: "/images/partners/rnp.png",
    alt: "Logo da RNP",
    width: 400,
    height: 125,
    className: "h-12 w-auto md:h-16",
  },
  {
    name: "Fatec Ferraz",
    src: "/images/partners/fatec-ferraz.png",
    alt: "Logotipo da Fatec Ferraz de Vasconcelos",
    width: 863,
    height: 544,
    className: "h-20 w-auto md:h-24",
  },
  {
    name: "Centro Paula Souza",
    src: "/images/partners/cps.svg",
    alt: "Logo do Centro Paula Souza",
    width: 122,
    height: 80,
    className: "h-16 w-auto md:h-20",
  },
];

export default function HomePage() {
  const { theme, toggleTheme } = useTheme();
  const [lang, setLang] = useState<"pt" | "en">("pt");
  const [openFaq, setOpenFaq] = useState<number | null>(null);
  const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);
  const [isScrolled, setIsScrolled] = useState(false);
  const faqAnswerRefs = useRef<(HTMLDivElement | null)[]>([]);

  // Custom Toast State
  const [toastMsg, setToastMsg] = useState<string | null>(null);
  const [showToast, setShowToast] = useState(false);
  const [toastTimeoutId, setToastTimeoutId] = useState<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let ticking = false;

    const updateScrollState = () => {
      setIsScrolled(window.scrollY > 25);
      ticking = false;
    };

    const onScroll = () => {
      if (!ticking) {
        window.requestAnimationFrame(updateScrollState);
        ticking = true;
      }
    };

    updateScrollState();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const triggerToast = (msg: string) => {
    if (toastTimeoutId) clearTimeout(toastTimeoutId);
    setToastMsg(msg);
    setShowToast(true);
    const id = setTimeout(() => {
      setShowToast(false);
    }, 2800);
    setToastTimeoutId(id);
  };

  // Smooth scroll handler
  const handleScroll = (e: React.MouseEvent<HTMLAnchorElement>, id: string) => {
    e.preventDefault();
    setIsMobileNavOpen(false);
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  const t = (key: keyof typeof translations.pt) => {
    return translations[lang][key] || translations.pt[key];
  };

  const navItems = [
    { label: t("plataforma"), href: "#plataforma" },
    { label: t("fluxo"), href: "#fluxo" },
    { label: t("tecnologia"), href: "#tecnologia" },
    { label: t("instituicoes"), href: "#instituicoes" },
  ];

  const heroStats = [
    { value: "01", label: t("stat1") },
    { value: "ROI", label: t("stat2") },
    { value: "IA", label: t("stat3") },
    { value: "PDF", label: t("stat4") },
  ];

  const clinicalFlow = [
    {
      icon: ClipboardList,
      title: t("cardCadastrar"),
      text: t("cardCadastrarDesc"),
    },
    {
      icon: Camera,
      title: t("cardAvaliar"),
      text: t("cardAvaliarDesc"),
    },
    {
      icon: ScanLine,
      title: t("cardROI"),
      text: t("cardROIDesc"),
    },
    {
      icon: FileText,
      title: t("cardDocumentar"),
      text: t("cardDocumentarDesc"),
    },
  ];

  const platformHighlights = [
    {
      icon: Layers3,
      title: t("susCard1"),
      text: t("susCard1Desc"),
    },
    {
      icon: Database,
      title: t("susCard2"),
      text: t("susCard2Desc"),
    },
    {
      icon: BrainCircuit,
      title: t("susCard3"),
      text: t("susCard3Desc"),
    },
    {
      icon: LockKeyhole,
      title: t("susCard4"),
      text: t("susCard4Desc"),
    },
  ];

  const techItems = [
    {
      icon: Globe2,
      label: t("techCard1Label"),
      value: t("techCard1Val"),
    },
    {
      icon: Network,
      label: t("techCard2Label"),
      value: t("techCard2Val"),
    },
    {
      icon: Cpu,
      label: t("techCard3Label"),
      value: t("techCard3Val"),
    },
    {
      icon: ShieldCheck,
      label: t("techCard4Label"),
      value: t("techCard4Val"),
    },
  ];

  const journeySteps = [
    {
      step: "01",
      title: t("step1Title"),
      text: t("step1Desc"),
    },
    {
      step: "02",
      title: t("step2Title"),
      text: t("step2Desc"),
    },
    {
      step: "03",
      title: t("step3Title"),
      text: t("step3Desc"),
    },
    {
      step: "04",
      title: t("step4Title"),
      text: t("step4Desc"),
    },
  ];

  return (
    <div className={`min-h-screen overflow-x-hidden font-sans antialiased selection:bg-[#41B6E6]/20 transition-colors duration-300 ${theme === "dark" ? "bg-[#050608] text-[#f2f4f7]" : "bg-white text-slate-900"}`}>
      
      {/* ─── HEADER (NAVBAR) - AURELIS CREATIVE INTELLIGENCE DESIGN ─── */}
      <nav
        className={`fixed z-50 left-1/2 -translate-x-1/2 w-[calc(100%-32px)] sm:w-[calc(100%-48px)] transition-all duration-500 ease-out flex items-center justify-between border ${
          isScrolled
            ? theme === "dark"
              ? "top-4 max-w-[1020px] py-2 px-3.5 sm:px-5 rounded-[20px] border-white/[0.095] bg-[#08080c]/80 backdrop-blur-2xl shadow-[0_24px_70px_rgba(0,0,0,0.45)] text-white"
              : "top-4 max-w-[1020px] py-2 px-3.5 sm:px-5 rounded-[20px] border-slate-200 bg-white/85 backdrop-blur-2xl shadow-[0_16px_50px_rgba(0,0,0,0.08)] text-slate-900"
            : theme === "dark"
              ? "top-5 max-w-[1340px] py-3 px-4 sm:px-6 rounded-[24px] border-transparent bg-transparent backdrop-blur-none text-white"
              : "top-5 max-w-[1340px] py-3 px-4 sm:px-6 rounded-[24px] border-transparent bg-transparent backdrop-blur-none text-slate-900"
        }`}
      >
        <Link href="/" className="group flex items-center gap-3" aria-label="Heal+ — início">
          <Image
            src="/images/Logo_final_modobranco.png"
            alt="Heal+"
            width={140}
            height={50}
            priority
            className="h-8 w-auto shrink-0 object-contain transition-transform duration-300 group-hover:scale-[1.03] sm:h-10"
          />
          <span className={`hidden items-center gap-2 border-l pl-3 text-[10px] font-mono tracking-widest uppercase md:inline-flex ${theme === "dark" ? "border-white/15 text-slate-400" : "border-slate-300 text-slate-600 font-semibold"}`}>
            REDI-SUS CLUSTER
          </span>
        </Link>

        <div className="hidden items-center gap-1 xl:flex">
          {navItems.map((item) => (
            <a
              key={item.href}
              href={item.href}
              onClick={(e) => handleScroll(e, item.href.substring(1))}
              className={`rounded-xl px-3.5 py-1.5 text-xs font-semibold transition-all ${
                theme === "dark"
                  ? "text-slate-300 hover:bg-white/[0.08] hover:text-white"
                  : "text-slate-700 hover:bg-slate-100 hover:text-[#0A4D68]"
              }`}
            >
              {item.label}
            </a>
          ))}
        </div>

        <div className="flex items-center gap-2 sm:gap-3">
          {/* Language Selector Button */}
          <button
            type="button"
            onClick={() => {
              const nextLang = lang === "pt" ? "en" : "pt";
              setLang(nextLang);
              triggerToast(nextLang === "pt" ? "Idioma: Português (BR)" : "Language: English (US)");
            }}
            className={`hidden items-center gap-1.5 rounded-xl border px-2.5 py-1.5 text-[11px] font-bold transition-all md:flex ${
              theme === "dark"
                ? "border-white/10 bg-white/[0.04] text-slate-300 hover:bg-white/10"
                : "border-slate-200 bg-slate-100/90 text-slate-700 hover:bg-slate-200"
            }`}
            aria-label={lang === "pt" ? "Switch to English" : "Mudar para português"}
          >
            <Globe2 size={13} />
            {lang === "pt" ? "PT" : "EN"}
          </button>

          {/* Dark/Light mode toggle switch */}
          <button
            onClick={toggleTheme}
            className={`rounded-xl p-2 transition-all ${
              theme === "dark"
                ? "text-slate-300 hover:bg-white/10 hover:text-[#6cd6ff]"
                : "text-slate-700 hover:bg-slate-100 hover:text-[#0A4D68]"
            }`}
            aria-label="Alternar Tema"
          >
            {theme === "dark" ? <Sun size={17} className="text-[#41B6E6]" /> : <Moon size={17} className="text-slate-700" />}
          </button>

          <Link
            href="/login"
            className={`hidden rounded-xl px-3 py-1.5 text-xs font-bold transition-colors lg:inline-flex ${
              theme === "dark" ? "text-slate-300 hover:text-white" : "text-slate-700 hover:text-[#0A4D68]"
            }`}
          >
            {t("entrar")}
          </Link>

          <Link
            href="/login"
            className={`inline-flex h-9 items-center justify-center gap-1.5 rounded-xl px-4 text-xs font-black transition-all hover:scale-[1.03] active:scale-95 shadow-md ${
              theme === "dark"
                ? "bg-white text-slate-950 hover:bg-slate-100 shadow-white/10"
                : "bg-[#0A4D68] text-white hover:bg-[#083D54] shadow-[#0A4D68]/20"
            }`}
            aria-label={t("acessarAreaClinica")}
          >
            <span>{t("acessar")}</span>
            <ArrowUpRight size={15} strokeWidth={2.5} />
          </Link>

          <button
            type="button"
            onClick={() => setIsMobileNavOpen(open => !open)}
            className={`inline-flex h-9 w-9 items-center justify-center rounded-xl border transition-colors xl:hidden ${
              theme === "dark"
                ? "border-white/10 bg-white/[0.04] text-white hover:border-[#41B6E6]/50"
                : "border-slate-200 bg-slate-100 text-slate-800 hover:border-slate-300"
            }`}
            aria-label={isMobileNavOpen ? "Fechar menu" : "Abrir menu"}
            aria-expanded={isMobileNavOpen}
          >
            {isMobileNavOpen ? <X size={18} /> : <Menu size={18} />}
          </button>
        </div>

        {isMobileNavOpen && (
          <div className={`absolute left-0 top-full mt-2 w-full rounded-2xl border p-4 shadow-xl backdrop-blur-2xl xl:hidden ${
            theme === "dark"
              ? "border-white/10 bg-[#080a0d]/96 text-slate-200"
              : "border-slate-200 bg-white/96 text-slate-800"
          }`}>
            <div className="grid gap-2">
              {navItems.map((item, index) => (
                <a
                  key={item.href}
                  href={item.href}
                  onClick={(event) => handleScroll(event, item.href.substring(1))}
                  className={`flex items-center justify-between rounded-xl px-4 py-3 text-sm font-bold transition-colors ${
                    theme === "dark"
                      ? "hover:bg-[#41B6E6]/10 hover:text-[#6cd6ff]"
                      : "hover:bg-slate-100 hover:text-[#0A4D68]"
                  }`}
                  style={{ animationDelay: `${index * 45}ms` }}
                >
                  {item.label}
                  <ArrowUpRight size={17} />
                </a>
              ))}
            </div>
          </div>
        )}


      </nav>

      <main className="pt-0">
        
        {/* ─── HERO SECTION WITH DOTFIELD (CENTERED, NO IMAGE) ─── */}
        <section
          id="projeto"
          className={`relative isolate min-h-[95vh] flex items-center justify-center overflow-hidden border-b transition-colors duration-300 ${
            theme === "dark"
              ? "bg-[#050608] text-white border-white/10"
              : "bg-gradient-to-b from-[#f8fafc] via-white to-[#f1f5f9] text-slate-900 border-slate-200"
          }`}
        >
          {/* DotField Canvas Component */}
          <div className="absolute inset-0 z-0 pointer-events-auto opacity-75">
            <DotField
              dotRadius={1.5}
              dotSpacing={14}
              bulgeStrength={67}
              glowRadius={0}
              sparkle={false}
              waveAmplitude={0}
              gradientFrom={theme === "dark" ? "#09b2ff" : "#0284c7"}
              gradientTo={theme === "dark" ? "rgba(9, 178, 255, 0.18)" : "rgba(2, 132, 199, 0.08)"}
              glowColor="transparent"
            />
          </div>

          <div className="relative z-10 mx-auto flex w-full max-w-4xl flex-col items-center text-center px-5 py-32 md:py-40">
            {/* React Bits style pill badge */}
            <div className={`inline-flex items-center gap-2.5 rounded-full border backdrop-blur-md px-3.5 py-1.5 text-xs font-semibold shadow-md ${
              theme === "dark"
                ? "border-white/10 bg-white/[0.06] text-slate-200"
                : "border-slate-200/90 bg-white/90 text-slate-700 shadow-slate-200/60"
            }`}>
              <span className={`rounded-full px-2 py-0.5 text-[10px] font-black uppercase tracking-wider ${
                theme === "dark" ? "bg-white text-slate-950" : "bg-[#0A4D68] text-white"
              }`}>
                NEW
              </span>
              <span className={theme === "dark" ? "text-slate-300" : "text-slate-700 font-medium"}>{t("appClinico")}</span>
            </div>

            <h1 className="mt-8 max-w-4xl text-4xl font-black leading-[1.08] tracking-[-0.04em] font-headline md:text-6xl lg:text-[4.5rem]">
              <span className={theme === "dark" ? "text-white" : "text-[#0A4D68]"}>
                {t("cuidadoInteligente")}
              </span>
              <span className={`block bg-gradient-to-r bg-clip-text text-transparent ${
                theme === "dark"
                  ? "from-white via-[#9ee2ff] to-[#41B6E6]"
                  : "from-[#0077b6] via-[#0284c7] to-[#41B6E6]"
              }`}>
                {t("evolucaoVisivel")}
              </span>
            </h1>

            <p className={`mt-6 max-w-2xl text-base font-normal leading-8 md:text-lg ${
              theme === "dark" ? "text-slate-300" : "text-slate-650 font-medium"
            }`}>
              {t("heroSubtitle")}
            </p>

            <div className="mt-10 flex flex-col gap-4 sm:flex-row sm:items-center">
              <Link
                href="/login"
                className={`inline-flex items-center justify-center gap-2.5 rounded-full px-8 py-3.5 text-base font-black transition-all duration-300 hover:scale-[1.02] active:scale-95 shadow-xl ${
                  theme === "dark"
                    ? "bg-white text-slate-950 hover:bg-slate-100 shadow-white/10"
                    : "bg-[#0A4D68] text-white hover:bg-[#083D54] shadow-[#0A4D68]/25"
                }`}
              >
                {t("acessarAreaClinica")}
                <ArrowRight size={20} strokeWidth={3} />
              </Link>
              <a
                href="#plataforma"
                onClick={(e) => handleScroll(e, "plataforma")}
                className={`inline-flex items-center justify-center gap-2.5 rounded-full border backdrop-blur-md px-8 py-3.5 text-base font-black transition-all duration-300 active:scale-95 ${
                  theme === "dark"
                    ? "border-white/15 bg-white/[0.06] text-white hover:bg-white/10"
                    : "border-slate-250 bg-white/90 text-slate-800 hover:bg-slate-100 shadow-sm"
                }`}
              >
                {t("conhecerPlataforma")}
                <ArrowUpRight size={19} strokeWidth={3} />
              </a>
            </div>

            {/* Stats Cards */}
            <div className="mt-14 grid w-full max-w-3xl grid-cols-2 gap-3 sm:grid-cols-4">
              {heroStats.map((item) => (
                <div
                  key={item.label}
                  className={`min-h-[96px] rounded-[18px] border backdrop-blur-md px-4 py-3.5 shadow-lg flex flex-col items-center justify-center text-center ${
                    theme === "dark"
                      ? "border-white/10 bg-[#0d1117]/70 text-slate-300"
                      : "border-slate-200/80 bg-white/85 text-slate-700 shadow-sm"
                  }`}
                >
                  <p className={`text-xl font-black font-headline ${
                    theme === "dark" ? "text-[#41B6E6]" : "text-[#0284c7]"
                  }`}>
                    {item.value}
                  </p>
                  <p className={`mt-1.5 text-[11px] font-extrabold leading-4 uppercase tracking-wider ${
                    theme === "dark" ? "text-slate-300" : "text-slate-600"
                  }`}>
                    {item.label}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ─── CHECKBOX BADGES STRIP ─── */}
        <section className={`border-b transition-colors duration-300 py-5 ${
          theme === "dark" ? "border-white/10 bg-[#050608]" : "border-slate-200 bg-slate-50"
        }`}>
          <div className="mx-auto grid max-w-7xl grid-cols-2 gap-3 px-5 md:grid-cols-4 md:px-8" data-reveal-group>
            {[
              t("badge1"),
              t("badge2"),
              t("badge3"),
              t("badge4"),
            ].map((item) => (
              <div 
                key={item} 
                data-reveal
                className="landing-proof-pill flex min-h-14 items-center justify-center gap-2 rounded-2xl border border-[#41B6E6]/10 bg-[#41B6E6]/5 px-3 py-3 text-center text-xs font-black text-[#159dce] dark:border-[#41B6E6]/10 dark:bg-[#41B6E6]/5 dark:text-[#6cd6ff] sm:text-sm"
              >
                <BadgeCheck size={18} />
                {item}
              </div>
            ))}
          </div>
        </section>

        {/* ─── PLATAFORMA SECTION ─── */}
        <section id="plataforma" className="bg-[#fcfdfe] dark:bg-[#090b0e] py-[4.5rem] text-slate-850 dark:text-white/90">
          <div className="mx-auto grid max-w-7xl gap-10 px-5 md:px-8 lg:grid-cols-[0.82fr_1.18fr] lg:gap-14">
            <div className="lg:sticky lg:top-32 lg:self-start" data-reveal>
              <p className="text-sm font-black uppercase tracking-[0.24em] text-[#41B6E6] dark:text-[#41B6E6]">
                {t("plataforma")}
              </p>
              <h2 className="mt-4 text-4xl font-black leading-tight tracking-[-0.04em] font-headline text-[#0A4D68] dark:text-white md:text-5xl">
                {t("plataformaTitle")}
              </h2>
              <p className="mt-5 text-lg leading-8 text-slate-650 dark:text-slate-400 font-light">
                {t("plataformaDesc")}
              </p>
              <div className="mt-6 rounded-[2rem] border border-[#41B6E6]/25 dark:border-[#41B6E6]/25 bg-white dark:bg-[#111115] p-5 shadow-sm">
                <div className="flex items-start gap-4">
                  <div className="rounded-2xl bg-[#41B6E6]/10 dark:bg-[#41B6E6]/10 p-3 text-[#41B6E6] dark:text-[#41B6E6]">
                    <Target size={28} />
                  </div>
                  <div>
                    <p className="text-xl font-black font-headline text-[#0A4D68] dark:text-white">{t("focoExp")}</p>
                    <p className="mt-2 text-sm leading-7 text-slate-500 dark:text-slate-400 font-light">
                      {t("focoDesc")}
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Clinical Flow Cards */}
            <div className="grid gap-4 sm:grid-cols-2" data-reveal-group>
              {clinicalFlow.map((item) => (
                <article
                  key={item.title}
                  data-reveal
                  className="landing-interactive-card group rounded-[2rem] border border-slate-100 bg-white p-6 shadow-sm transition-all hover:-translate-y-1.5 hover:border-[#41B6E6]/30 hover:shadow-[0_22px_60px_rgba(15,76,104,0.12)] dark:border-slate-900 dark:bg-[#111115] dark:hover:border-[#41B6E6]/30"
                >
                  <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#41B6E6]/10 dark:bg-[#41B6E6]/10 text-[#41B6E6] dark:text-[#41B6E6] transition-colors group-hover:bg-[#41B6E6] dark:group-hover:bg-[#41B6E6] group-hover:text-white dark:group-hover:text-[#050608]">
                    <item.icon size={26} />
                  </div>
                  <h3 className="mt-5 text-2xl font-black tracking-[-0.03em] font-headline text-slate-800 dark:text-white">
                    {item.title}
                  </h3>
                  <p className="mt-3 text-sm leading-7 text-slate-500 dark:text-slate-400 font-light">
                    {item.text}
                  </p>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* ─── FLUXO SECTION ─── */}
        <section id="fluxo" className="bg-white dark:bg-[#050608] py-[5.5rem] text-slate-855 dark:text-white/90 transition-colors duration-300 border-b border-slate-100 dark:border-zinc-900">
          <div className="mx-auto max-w-7xl px-5 md:px-8">
            <div className="grid gap-8 lg:grid-cols-[0.9fr_1.1fr] lg:items-end mb-12">
              <div>
                <p className="text-xs font-black uppercase tracking-[0.24em] text-[#41B6E6]">
                  {t("fluxoLabel")}
                </p>
                <h2 className="mt-4 text-3xl font-black leading-tight tracking-[-0.04em] font-headline text-slate-900 dark:text-white md:text-5xl">
                  {t("fluxoTitle")}
                </h2>
              </div>
              <p className="text-base leading-8 text-slate-500 dark:text-zinc-400">
                {t("fluxoDesc")}
              </p>
            </div>

            <div className="relative mt-8">
              {/* Desktop Horizontal flow line */}
              <div className="absolute top-[44px] left-[12.5%] right-[12.5%] h-[2px] bg-gradient-to-r from-[#41B6E6] via-[#41B6E6]/60 to-[#41B6E6]/10 hidden lg:block z-0" />
              
              {/* Mobile Vertical flow line */}
              <div className="absolute left-[36px] top-11 bottom-11 w-[2px] bg-gradient-to-b from-[#41B6E6] via-[#41B6E6]/50 to-[#41B6E6]/10 lg:hidden z-0" />

              <div className="grid gap-8 lg:grid-cols-4 md:grid-cols-2 relative z-10">
                {journeySteps.map((item) => (
                  <div key={item.step} className="relative flex items-stretch">
                    <article
                      className="group w-full rounded-[1.75rem] border border-slate-100 dark:border-zinc-800/60 bg-slate-50/50 dark:bg-[#0c0c0e] p-6 pl-14 lg:pl-6 transition-all duration-350 hover:-translate-y-1 hover:border-[#41B6E6]/40 hover:shadow-[0_8px_30px_rgba(65,182,230,0.08)] flex flex-col items-start lg:items-center text-left lg:text-center"
                    >
                      {/* Step Number Circle */}
                      <div className="absolute left-4 top-6 lg:relative lg:left-0 lg:top-0 lg:mx-auto z-20 flex h-10 w-10 items-center justify-center rounded-full border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#1A1A1E] text-sm font-black text-[#41B6E6] font-headline shadow-sm group-hover:bg-[#41B6E6] group-hover:text-white dark:group-hover:text-[#050608] group-hover:border-[#41B6E6] transition-all duration-300">
                        {item.step}
                      </div>

                      <h3 className="mt-0 lg:mt-5 text-lg font-bold tracking-[-0.02em] font-headline text-slate-800 dark:text-white group-hover:text-[#41B6E6] transition-colors duration-300">
                        {item.title}
                      </h3>
                      <p className="mt-3 text-xs leading-relaxed text-slate-550 dark:text-zinc-400">
                        {item.text}
                      </p>
                    </article>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* ─── CLUSTER HIGHLIGHTS SECTION ─── */}
        <section className="bg-slate-50/30 dark:bg-[#090b0e] border-b border-slate-100 dark:border-zinc-900 relative overflow-hidden py-[5.5rem] text-slate-800 dark:text-white transition-colors duration-300">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(65,182,230,0.04),transparent_28%),radial-gradient(circle_at_78%_30%,rgba(65,182,230,0.03),transparent_30%)]" />
          <div className="relative mx-auto max-w-7xl px-5 md:px-8">
            <div className="grid gap-10 lg:grid-cols-[0.9fr_1.1fr] lg:items-center lg:gap-14">
              <div data-reveal>
                <p className="text-xs font-black uppercase tracking-[0.24em] text-[#41B6E6]">
                  {t("clusterSus")}
                </p>
                <h2 className="mt-4 text-3xl font-black leading-tight tracking-[-0.04em] font-headline text-slate-900 dark:text-white md:text-5xl">
                  {t("susTitle")}
                </h2>
                <p className="mt-5 text-base leading-8 text-slate-500 dark:text-zinc-400">
                  {t("susDesc")}
                </p>
              </div>

              <div className="grid gap-4 sm:grid-cols-2" data-reveal-group>
                {platformHighlights.map((item) => (
                  <article
                    key={item.title}
                    data-reveal
                    className="landing-interactive-card rounded-[1.75rem] border border-slate-100 bg-white p-6 shadow-sm transition-all duration-300 hover:-translate-y-1.5 hover:border-[#41B6E6]/40 hover:shadow-[0_18px_50px_rgba(15,76,104,0.10)] dark:border-zinc-800/60 dark:bg-[#0c0c0e]"
                  >
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#41B6E6]/10 text-[#41B6E6]">
                      <item.icon size={20} />
                    </div>
                    <h3 className="mt-4 text-base font-bold tracking-[-0.02em] font-headline text-slate-800 dark:text-white">
                      {item.title}
                    </h3>
                    <p className="mt-2.5 text-xs leading-relaxed text-slate-550 dark:text-zinc-400">
                      {item.text}
                    </p>
                  </article>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* ─── BASE TÉCNICA SECTION ─── */}
        <section id="tecnologia" className="bg-white dark:bg-[#050608] py-[5.5rem] text-slate-855 dark:text-white transition-colors duration-300 border-b border-slate-100 dark:border-zinc-900">
          <div className="mx-auto max-w-7xl px-5 md:px-8">
            <div className="mb-12 flex flex-col justify-between gap-6 md:flex-row md:items-end" data-reveal>
              <div>
                <p className="text-xs font-black uppercase tracking-[0.24em] text-[#41B6E6]">
                  {t("techLabel")}
                </p>
                <h2 className="mt-4 max-w-2xl text-3xl font-black leading-tight tracking-[-0.04em] font-headline text-slate-900 dark:text-white md:text-5xl">
                  {t("techTitle")}
                </h2>
              </div>
              <Link
                href="/referencias"
                className="inline-flex items-center gap-2 rounded-full border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0c0c0e] px-5 py-3 text-sm font-black text-[#41B6E6] hover:text-[#35a3d0] dark:hover:text-[#4fc3f7] shadow-sm transition-all duration-300 hover:-translate-y-0.5"
              >
                {t("techRef")}
                <BookOpenCheck size={16} />
              </Link>
            </div>

            <div className="grid gap-4 md:grid-cols-2" data-reveal-group>
              {techItems.map((item) => (
                <article
                  key={item.label}
                  data-reveal
                  className="landing-interactive-card rounded-[1.75rem] border border-slate-100 bg-slate-50/50 p-6 shadow-sm transition-all duration-300 hover:-translate-y-1 hover:border-[#41B6E6]/40 hover:bg-white hover:shadow-[0_18px_50px_rgba(15,76,104,0.10)] dark:border-zinc-800/60 dark:bg-[#0c0c0e] dark:hover:bg-[#101216]"
                >
                  <div className="flex items-start gap-4">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#41B6E6]/10 text-[#41B6E6]">
                      <item.icon size={20} />
                    </div>
                    <div>
                      <p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-400 dark:text-slate-500">
                        {item.label}
                      </p>
                      <p className="mt-2 text-base font-bold leading-normal tracking-[-0.02em] font-headline text-slate-800 dark:text-white">
                        {item.value}
                      </p>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* ─── NEXT STEP CALL-TO-ACTION BANNER ─── */}
        <section className="bg-white dark:bg-[#050608] px-5 py-[4.5rem] md:px-8 transition-colors duration-300 border-b border-slate-100 dark:border-zinc-900">
          <div className="landing-cta-panel relative mx-auto max-w-7xl overflow-hidden rounded-[2.25rem] border border-[#41B6E6]/25 p-8 shadow-[0_24px_80px_rgba(15,76,104,0.12)] transition-all duration-300 hover:border-[#41B6E6]/45 md:p-12" data-reveal>
            <div className="landing-cta-orb absolute -right-24 -top-24 h-96 w-96 rounded-full blur-3xl" />
            <div className="landing-cta-orb landing-cta-orb-secondary absolute -bottom-44 left-[30%] h-80 w-80 rounded-full blur-3xl" />
            <div className="relative z-10 grid gap-8 lg:grid-cols-[1fr_auto] lg:items-center">
              <div>
                <p className="text-xs font-black uppercase tracking-[0.24em] text-[#41B6E6]">
                  {t("ctaLabel")}
                </p>
                <h2 className="mt-4 max-w-3xl font-headline text-3xl font-black leading-tight tracking-[-0.04em] text-white md:text-5xl">
                  {t("ctaTitle")}
                </h2>
              </div>
              <Link
                href="/login"
                className="group inline-flex items-center justify-center gap-2 rounded-full bg-white px-8 py-4 text-base font-black text-[#087aa5] shadow-[0_16px_45px_rgba(0,0,0,0.18)] transition-all hover:-translate-y-1 hover:shadow-[0_20px_55px_rgba(0,0,0,0.24)]"
              >
                {t("ctaBtn")}
                <ArrowRight size={18} strokeWidth={2.5} className="transition-transform group-hover:translate-x-1" />
              </Link>
            </div>
          </div>
        </section>

        {/* ─── FAQ SECTION ─── */}
        <section id="faq" className="bg-[#fcfdfe] dark:bg-[#090b0e] py-[4.5rem] text-slate-850 dark:text-white border-t border-slate-100 dark:border-slate-900">
          <div className="mx-auto max-w-5xl px-5 md:px-8">
            <div className="text-center" data-reveal>
              <div className="mx-auto inline-flex items-center justify-center gap-3 text-xs font-black uppercase tracking-[0.28em] text-[#41B6E6] dark:text-[#41B6E6]">
                <span className="h-px w-10 bg-[#41B6E6]/30 dark:bg-[#41B6E6]/30" />
                <span>{t("faqLabel")}</span>
                <span className="h-px w-10 bg-[#41B6E6]/30 dark:bg-[#41B6E6]/30" />
              </div>
              <h2 className="mt-6 text-4xl font-black leading-tight tracking-[-0.04em] font-headline text-[#0A4D68] dark:text-white md:text-6xl">
                {t("faqTitle")}
              </h2>
              <p className="mx-auto mt-5 max-w-2xl text-base leading-7 text-slate-500 dark:text-slate-400 font-light md:text-lg">
                {t("faqDesc")}
              </p>
            </div>

            {/* Previous Accordion Layout with Smooth Height Animation */}
            <div className="mx-auto mt-10 grid max-w-4xl gap-3.5" data-reveal-group>
              {[
                {
                  question: t("faqQ1"),
                  answer: t("faqA1")
                },
                {
                  question: t("faqQ2"),
                  answer: t("faqA2")
                },
                {
                  question: t("faqQ3"),
                  answer: t("faqA3")
                },
                {
                  question: t("faqQ4"),
                  answer: t("faqA4")
                }
              ].map((faq, idx) => (
                <article
                  key={idx}
                  data-reveal
                  className={`rounded-[1.25rem] border px-6 py-5 shadow-sm transition-all duration-350 md:px-8 hover:shadow-soft hover:border-[#41B6E6]/30 ${
                    openFaq === idx
                      ? "border-[#41B6E6]/30 bg-gradient-to-r from-[#41B6E6]/3 to-transparent border-l-4 border-l-[#41B6E6] dark:from-[#41B6E6]/6"
                      : theme === "dark" 
                      ? "border-slate-900 bg-[#111115]" 
                      : "border-slate-150 bg-white"
                  }`}
                >
                  <button
                    onClick={() => setOpenFaq(openFaq === idx ? null : idx)}
                    className="flex w-full items-center justify-between gap-6 text-left text-base font-bold text-slate-800 dark:text-white md:text-lg"
                  >
                    <span>{faq.question}</span>
                    <span 
                      className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full border transition-transform duration-350 ${
                        theme === "dark" 
                          ? "border-slate-800 bg-[#1E1E20] text-[#41B6E6]" 
                          : "border-slate-150 bg-slate-50 text-[#41B6E6]"
                      } ${openFaq === idx ? "rotate-180" : ""}`}
                    >
                      <ChevronDown size={16} strokeWidth={2.5} />
                    </span>
                  </button>
                  <div
                    ref={(el) => { faqAnswerRefs.current[idx] = el; }}
                    className="overflow-hidden transition-all duration-350 ease-in-out"
                    style={{
                      maxHeight: openFaq === idx ? faqAnswerRefs.current[idx]?.scrollHeight + "px" : "0px",
                      opacity: openFaq === idx ? 1 : 0,
                      marginTop: openFaq === idx ? "1rem" : "0px"
                    }}
                  >
                    <p className="text-sm leading-7 text-slate-500 dark:text-slate-400 font-light">
                      {faq.answer}
                    </p>
                  </div>
                </article>
              ))}
            </div>

          </div>
        </section>

        {/* ─── INSTITUTIONAL SUPPORT ─── */}
        <section
          id="instituicoes"
          aria-labelledby="institutional-support-title"
          className="border-t border-slate-100 dark:border-slate-900 bg-white dark:bg-[#050608] py-[4.5rem] text-slate-800 dark:text-slate-300"
        >
          <div className="mx-auto max-w-7xl px-5 md:px-8">
            <div className="mt-4" data-reveal>
              <div className="grid grid-cols-2 divide-x divide-y divide-slate-100 overflow-hidden rounded-[2rem] border border-slate-100 dark:divide-slate-900 dark:border-slate-900 md:grid-cols-4 md:divide-y-0">
                
                {institutionalLogos.map((logo) => (
                  <div
                    key={logo.name}
                    className="landing-logo-cell flex min-h-[140px] items-center justify-center px-5 py-8 transition-colors hover:bg-[#41B6E6]/5 md:min-h-[170px] md:px-8"
                  >
                    <Image
                      src={
                        logo.name === "RNP"
                          ? (theme === "dark" ? "/images/partners/rnp_modoDark.png" : "/images/partners/rnp.png")
                          : logo.name === "Centro Paula Souza"
                          ? (theme === "dark" ? "/images/partners/cps_modoDark.svg" : "/images/partners/cps.svg")
                          : logo.src
                      }
                      alt={logo.alt}
                      width={logo.width}
                      height={logo.height}
                      className={`${logo.className} object-contain`}
                    />
                  </div>
                ))}

                <div className="landing-logo-cell flex min-h-[140px] items-center justify-center px-5 py-8 transition-colors hover:bg-[#41B6E6]/5 md:min-h-[170px] md:px-8">
                  <div className="flex items-center gap-3">
                    <Image
                      src="/images/Logo_final_modobranco.png"
                      alt="Logo do Heal+"
                      width={160}
                      height={64}
                      className="h-16 md:h-20 w-auto object-contain"
                    />
                  </div>
                </div>

              </div>
            </div>

            <p className="mt-8 text-center text-sm font-medium text-slate-500 dark:text-slate-400">
              {t("supportDesc")}
            </p>
          </div>
        </section>

      </main>

      {/* ─── FOOTER ─── */}
      <footer className="bg-white dark:bg-[#050608] text-slate-700 dark:text-slate-400 border-t border-slate-100 dark:border-slate-900 transition-colors duration-300">
        <div className="relative z-10 mx-auto max-w-7xl px-5 py-12 md:px-8">
          <div className="grid gap-10 border-b border-slate-200 dark:border-slate-800 pb-12 lg:grid-cols-[0.8fr_1.2fr]">
            <div>
              <div className="flex items-center gap-3">
                <Image 
                  src="/images/Logo_final_modobranco.png" 
                  alt="Heal+" 
                  width={120} 
                  height={44} 
                  className="h-9 w-auto object-contain" 
                />
              </div>
              <p className="mt-4 max-w-md text-xs leading-6 text-slate-550 dark:text-zinc-400 font-medium">
                {t("footerDesc")}
              </p>
            </div>

            <div className="grid gap-8 sm:grid-cols-3">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.24em] text-[#41B6E6]">
                  {t("plataforma")}
                </p>
                <div className="mt-4 space-y-3">
                  <a href="#projeto" onClick={(e) => handleScroll(e, "projeto")} className="block text-sm font-medium text-slate-650 dark:text-zinc-400 hover:text-[#41B6E6] dark:hover:text-[#41B6E6] transition-colors">
                    {t("projeto")}
                  </a>
                  <a href="#plataforma" onClick={(e) => handleScroll(e, "plataforma")} className="block text-sm font-medium text-slate-650 dark:text-zinc-400 hover:text-[#41B6E6] dark:hover:text-[#41B6E6] transition-colors">
                    {t("plataforma")}
                  </a>
                </div>
              </div>
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.24em] text-[#41B6E6]">
                  {t("tecnologia")}
                </p>
                <div className="mt-4 space-y-3">
                  <a href="#tecnologia" onClick={(e) => handleScroll(e, "tecnologia")} className="block text-sm font-medium text-slate-650 dark:text-zinc-400 hover:text-[#41B6E6] dark:hover:text-[#41B6E6] transition-colors">
                    {t("techLabel")}
                  </a>
                  <Link href="/referencias" className="block text-sm font-medium text-slate-650 dark:text-zinc-400 hover:text-[#41B6E6] dark:hover:text-[#41B6E6] transition-colors">
                    {t("techRef")}
                  </Link>
                </div>
              </div>
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.24em] text-[#41B6E6]">
                  {t("acessar")}
                </p>
                <div className="mt-4 space-y-3">
                  <Link href="/login" className="block text-sm font-medium text-slate-650 dark:text-zinc-400 hover:text-[#41B6E6] dark:hover:text-[#41B6E6] transition-colors">
                    {t("acessarAreaClinica")}
                  </Link>
                  <a href="#instituicoes" onClick={(e) => handleScroll(e, "instituicoes")} className="block text-sm font-medium text-slate-650 dark:text-zinc-400 hover:text-[#41B6E6] dark:hover:text-[#41B6E6] transition-colors">
                    {t("instituicoes")}
                  </a>
                </div>
              </div>
            </div>
          </div>

          <div className="flex flex-col justify-between gap-4 pt-8 text-xs font-semibold text-slate-550 dark:text-zinc-500 md:flex-row md:items-center">
            <p>&copy; {new Date().getFullYear()} HEAL+ REDI-SUS. Pesquisa aplicada em saúde digital.</p>
            <div className="flex flex-wrap gap-x-6 gap-y-2">
              <a href="#projeto" onClick={(e) => handleScroll(e, "projeto")} className="hover:underline hover:text-[#41B6E6] dark:hover:text-[#41B6E6]">
                {t("projeto")}
              </a>
              <a href="#plataforma" onClick={(e) => handleScroll(e, "plataforma")} className="hover:underline hover:text-[#41B6E6] dark:hover:text-[#41B6E6]">
                {t("plataforma")}
              </a>
              <Link href="/login" className="hover:underline hover:text-[#41B6E6] dark:hover:text-[#41B6E6]">
                {t("acessarAreaClinica")}
              </Link>
            </div>
          </div>
        </div>
      </footer>

      {/* Toast Notification */}
      <div 
        className={`fixed top-6 left-1/2 -translate-x-1/2 z-[9999] flex items-center gap-2.5 rounded-xl border border-[#41B6E6] bg-white dark:bg-[#111115] px-5 py-3.5 text-sm font-semibold text-slate-800 dark:text-white shadow-[0_12px_40px_rgba(65,182,230,0.18)] transition-transform duration-400 ease-[cubic-bezier(0.34,1.56,0.64,1)] ${
          showToast ? "translate-y-0 opacity-100" : "-translate-y-[200%] opacity-0"
        }`}
      >
        <svg className="w-5 h-5 text-[#41B6E6] shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
          <circle cx="12" cy="12" r="10"/>
          <path d="M12 6v6l4 2"/>
        </svg>
        <span>{toastMsg}</span>
      </div>

    </div>
  );
}

