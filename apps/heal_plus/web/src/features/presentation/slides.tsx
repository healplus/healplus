import { AlertTriangle, ArrowUpRight, GraduationCap, Users } from 'lucide-react';
import type { ReactNode } from 'react';
import { Link } from 'react-router';

import { useTheme } from '../../app/providers/ThemeProvider';
import {
  aiSupport,
  challenge,
  cover,
  idea,
  institutionLogos,
  journey,
  partnership,
  skills,
  team,
  workflow
} from './slideContent';
import type { SlideItem, TimelineItem } from './slideContent';

export interface SlideDefinition {
  id: string;
  label: string;
  render: () => ReactNode;
}

/* ── Primitivas visuais ─────────────────────────────── */

function Eyebrow({ children }: { children: ReactNode }) {
  return <p className="text-sm font-extrabold uppercase tracking-[0.22em] text-heal-blue tall:text-base">{children}</p>;
}

function SlideTitle({ children }: { children: ReactNode }) {
  return (
    <h2 className="mt-3 max-w-5xl font-headline text-3xl font-extrabold leading-[1.1] tracking-[-0.035em] text-slate-950 dark:text-white md:text-4xl xl:text-[2.75rem] tall:mt-4 tall:text-6xl">
      {children}
    </h2>
  );
}

function Lead({ children }: { children: ReactNode }) {
  return <p className="mt-4 max-w-4xl text-lg leading-8 text-slate-600 dark:text-slate-300 md:text-xl tall:mt-5 tall:text-2xl tall:leading-10">{children}</p>;
}

function ItemCard({ item, index, numbered = false }: { item: SlideItem; index: number; numbered?: boolean }) {
  const Icon = item.icon;
  return (
    <article className="flex h-full flex-col rounded-[1.75rem] border border-slate-200 bg-white p-5 shadow-sm dark:border-white/10 dark:bg-white/[0.04] tall:p-7">
      <div className="flex items-center justify-between">
        <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-heal-blue/12 text-heal-blue tall:h-14 tall:w-14">
          <Icon className="h-6 w-6 tall:h-7 tall:w-7" aria-hidden="true" />
        </span>
        {numbered ? <span className="text-sm font-extrabold tracking-[0.18em] text-slate-400">0{index + 1}</span> : null}
      </div>
      <h3 className="mt-4 text-lg font-extrabold text-slate-950 dark:text-white md:text-xl tall:mt-6 tall:text-2xl">{item.title}</h3>
      <p className="mt-2 text-base leading-7 text-slate-600 dark:text-slate-300 tall:mt-3 tall:text-lg tall:leading-8">{item.text}</p>
    </article>
  );
}

/* Ícone ao lado do texto: usado em slides com muitos itens curtos. */
function CompactItemCard({ item }: { item: SlideItem }) {
  const Icon = item.icon;
  return (
    <article className="flex h-full gap-4 rounded-[1.5rem] border border-slate-200 bg-white p-5 shadow-sm dark:border-white/10 dark:bg-white/[0.04] tall:p-6">
      <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-heal-blue/12 text-heal-blue tall:h-12 tall:w-12">
        <Icon className="h-6 w-6" aria-hidden="true" />
      </span>
      <div>
        <h3 className="text-lg font-extrabold leading-6 text-slate-950 dark:text-white tall:text-xl">{item.title}</h3>
        <p className="mt-1.5 text-base leading-6 text-slate-600 dark:text-slate-300 tall:mt-2 tall:text-lg tall:leading-7">{item.text}</p>
      </div>
    </article>
  );
}

function ItemGrid({
  items,
  columns,
  numbered,
  compact = false
}: {
  items: SlideItem[];
  columns: string;
  numbered?: boolean;
  compact?: boolean;
}) {
  return (
    <div className={`mt-8 grid gap-4 tall:mt-10 tall:gap-5 ${columns}`}>
      {items.map((item, index) =>
        compact ? (
          <CompactItemCard key={item.title} item={item} />
        ) : (
          <ItemCard key={item.title} item={item} index={index} numbered={numbered} />
        )
      )}
    </div>
  );
}

function Note({ children }: { children: ReactNode }) {
  return <p className="mt-6 text-sm font-semibold text-slate-500 dark:text-slate-400 tall:mt-8 tall:text-base">{children}</p>;
}

function InstitutionLogos({ size = 'md' }: { size?: 'md' | 'lg' }) {
  const { theme } = useTheme();
  const height = size === 'lg' ? 'max-h-14 tall:max-h-20' : 'max-h-12 tall:max-h-14';
  return (
    <ul className="flex flex-wrap items-center justify-center gap-x-10 gap-y-6" aria-label="Instituições">
      {institutionLogos.map(logo => (
        <li key={logo.name}>
          <img src={theme === 'dark' ? logo.dark : logo.light} alt={logo.name} className={`${height} max-w-[200px] object-contain`} />
        </li>
      ))}
    </ul>
  );
}

/* ── Slides ─────────────────────────────────────────── */

function CoverSlide() {
  return (
    <div className="flex flex-col items-center text-center">
      <Eyebrow>{cover.eyebrow}</Eyebrow>
      <img src="/images/Logo_final_modobranco.png" alt="Heal+" className="mt-8 h-20 w-auto object-contain tall:mt-10 tall:h-28" />
      <h1 className="mt-8 max-w-5xl font-headline text-3xl font-black leading-[1.1] tracking-[-0.035em] text-slate-950 dark:text-white md:text-5xl tall:mt-10 tall:text-6xl">
        {cover.title}
      </h1>
      <p className="mt-5 text-lg font-semibold text-slate-600 dark:text-slate-300 md:text-xl tall:mt-6 tall:text-2xl">
        {cover.course}
        <span className="mx-3 text-heal-blue" aria-hidden="true">·</span>
        {cover.institution}
      </p>
      <div className="mt-10 tall:mt-12">
        <InstitutionLogos />
      </div>
    </div>
  );
}

function ChallengeSlide() {
  return (
    <div>
      <Eyebrow>{challenge.eyebrow}</Eyebrow>
      <SlideTitle>{challenge.title}</SlideTitle>
      <ItemGrid items={challenge.items} columns="md:grid-cols-3" />
      <Note>{challenge.source}</Note>
    </div>
  );
}

function IdeaSlide() {
  return (
    <div>
      <Eyebrow>{idea.eyebrow}</Eyebrow>
      <SlideTitle>{idea.title}</SlideTitle>
      <Lead>{idea.lead}</Lead>
      <ItemGrid items={idea.items} columns="md:grid-cols-3" />
    </div>
  );
}

function WorkflowSlide() {
  return (
    <div>
      <Eyebrow>{workflow.eyebrow}</Eyebrow>
      <SlideTitle>{workflow.title}</SlideTitle>
      <ItemGrid items={workflow.items} columns="md:grid-cols-2 xl:grid-cols-4" numbered />
      <div className="mt-6 flex flex-wrap items-center gap-4 tall:mt-8">
        <p className="text-sm font-semibold text-slate-500 dark:text-slate-400 tall:text-base">{workflow.note}</p>
        <Link
          to="/login"
          className="inline-flex items-center gap-2 rounded-full border border-heal-blue/40 px-4 py-2 text-sm font-extrabold text-heal-blue transition-colors hover:bg-heal-blue/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-heal-blue"
        >
          Abrir a plataforma
          <ArrowUpRight className="h-4 w-4" aria-hidden="true" />
        </Link>
      </div>
    </div>
  );
}

function AiSupportSlide() {
  return (
    <div>
      <Eyebrow>{aiSupport.eyebrow}</Eyebrow>
      <SlideTitle>{aiSupport.title}</SlideTitle>
      <ol className="mt-8 grid gap-3 md:grid-cols-5 md:gap-4 tall:mt-10" aria-label="Etapas da análise assistida">
        {aiSupport.items.map((item, index) => {
          const Icon = item.icon;
          const isHuman = index === aiSupport.items.length - 1;
          return (
            <li
              key={item.title}
              className={`flex h-full flex-col rounded-[1.5rem] border p-5 ${
                isHuman
                  ? 'border-emerald-300 bg-emerald-50 dark:border-emerald-400/30 dark:bg-emerald-400/10'
                  : 'border-slate-200 bg-white dark:border-white/10 dark:bg-white/[0.04]'
              }`}
            >
              <span className="flex items-center gap-3">
                <span
                  className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${
                    isHuman ? 'bg-emerald-600 text-white' : 'bg-heal-blue/12 text-heal-blue'
                  }`}
                >
                  <Icon className="h-5 w-5" aria-hidden="true" />
                </span>
                <span className="text-xs font-extrabold tracking-[0.18em] text-slate-400">0{index + 1}</span>
              </span>
              <h3 className="mt-4 text-lg font-extrabold leading-6 text-slate-950 dark:text-white tall:mt-5 tall:text-xl">{item.title}</h3>
              <p className="mt-2 text-sm leading-6 text-slate-600 dark:text-slate-300 tall:text-base tall:leading-7">{item.text}</p>
            </li>
          );
        })}
      </ol>
      <p className="mt-6 flex max-w-5xl gap-3 rounded-2xl border border-amber-300 bg-amber-50 p-4 text-base font-semibold leading-7 text-amber-900 dark:border-amber-400/30 dark:bg-amber-400/10 dark:text-amber-100 tall:mt-8 tall:p-5 tall:text-lg">
        <AlertTriangle className="mt-1 h-5 w-5 shrink-0" aria-hidden="true" />
        <span>{aiSupport.caution}</span>
      </p>
    </div>
  );
}

function JourneySlide() {
  const items: TimelineItem[] = journey.items;
  return (
    <div>
      <Eyebrow>{journey.eyebrow}</Eyebrow>
      <SlideTitle>{journey.title}</SlideTitle>
      <ol className="mt-10 grid gap-5 md:grid-cols-4 tall:mt-12">
        {items.map((item, index) => {
          const Icon = item.icon;
          return (
            <li key={item.title} className="relative">
              <div className="flex items-center gap-3">
                <span
                  className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-full border-2 ${
                    item.current
                      ? 'border-heal-blue bg-heal-blue text-slate-950'
                      : 'border-heal-blue/40 bg-white text-heal-blue dark:bg-[#111111]'
                  }`}
                >
                  <Icon className="h-5 w-5" aria-hidden="true" />
                </span>
                {index < items.length - 1 ? <span className="hidden h-0.5 flex-1 bg-heal-blue/25 md:block" aria-hidden="true" /> : null}
              </div>
              <h3 className="mt-5 text-xl font-extrabold text-slate-950 dark:text-white tall:text-2xl">
                {item.title}
                {item.current ? <span className="sr-only"> (etapa atual)</span> : null}
              </h3>
              <p className="mt-2 text-base leading-7 text-slate-600 dark:text-slate-300 tall:text-lg tall:leading-8">{item.text}</p>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function SkillsSlide() {
  return (
    <div>
      <Eyebrow>{skills.eyebrow}</Eyebrow>
      <SlideTitle>{skills.title}</SlideTitle>
      <ItemGrid items={skills.items} columns="md:grid-cols-2 lg:grid-cols-3" compact />
      <Note>{skills.note}</Note>
    </div>
  );
}

function PartnershipSlide() {
  return (
    <div>
      <Eyebrow>{partnership.eyebrow}</Eyebrow>
      <SlideTitle>{partnership.title}</SlideTitle>
      <Lead>{partnership.lead}</Lead>
      <ItemGrid items={partnership.items} columns="md:grid-cols-2 xl:grid-cols-4" />
    </div>
  );
}

function TeamSlide() {
  return (
    <div className="text-center">
      <Eyebrow>{team.eyebrow}</Eyebrow>
      <h2 className="mt-3 font-headline text-5xl font-black tracking-[-0.04em] text-heal-blue tall:mt-4 tall:text-7xl">{team.title}</h2>
      <div className="mx-auto mt-8 grid max-w-4xl gap-5 text-left md:grid-cols-2 tall:mt-10">
        <section className="rounded-[1.75rem] border border-slate-200 bg-white p-6 dark:border-white/10 dark:bg-white/[0.04]">
          <h3 className="flex items-center gap-2 text-sm font-extrabold uppercase tracking-[0.18em] text-heal-blue">
            <Users className="h-4 w-4" aria-hidden="true" /> Autores
          </h3>
          <ul className="mt-4 space-y-2 text-lg font-semibold text-slate-800 dark:text-slate-100">
            {team.authors.map(name => <li key={name}>{name}</li>)}
          </ul>
        </section>
        <section className="rounded-[1.75rem] border border-slate-200 bg-white p-6 dark:border-white/10 dark:bg-white/[0.04]">
          <h3 className="flex items-center gap-2 text-sm font-extrabold uppercase tracking-[0.18em] text-heal-blue">
            <GraduationCap className="h-4 w-4" aria-hidden="true" /> Orientação
          </h3>
          <ul className="mt-4 space-y-2 text-lg font-semibold text-slate-800 dark:text-slate-100">
            {team.advisors.map(name => <li key={name}>{name}</li>)}
          </ul>
        </section>
      </div>
      <div className="mt-8 tall:mt-10">
        <InstitutionLogos size="lg" />
      </div>
    </div>
  );
}

export const slides: SlideDefinition[] = [
  { id: 'capa', label: 'Heal+', render: () => <CoverSlide /> },
  { id: 'desafio', label: 'O desafio', render: () => <ChallengeSlide /> },
  { id: 'ideia', label: 'A ideia inicial', render: () => <IdeaSlide /> },
  { id: 'fluxo', label: 'Como funciona', render: () => <WorkflowSlide /> },
  { id: 'ia', label: 'IA como apoio', render: () => <AiSupportSlide /> },
  { id: 'trajetoria', label: 'Nossa trajetória', render: () => <JourneySlide /> },
  { id: 'formacao', label: 'Formação', render: () => <SkillsSlide /> },
  { id: 'parcerias', label: 'Parcerias', render: () => <PartnershipSlide /> },
  { id: 'equipe', label: 'Equipe', render: () => <TeamSlide /> }
];
