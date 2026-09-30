import data from './abilities.json';

export type AbilityType = 'read' | 'write' | 'destructive';

export interface Ability {
  key: string;
  label: string;
  type: AbilityType;
  description: string;
}

export interface Section {
  id: string;
  name: string;
  requires: string;
  abilities: Ability[];
}

interface SectionMeta { icon: string; en: string; es: string }

/** Friendly display names for the home cards and directory headings. */
export const sectionMeta: Record<string, SectionMeta> = {
  core:                      { icon: '🧱', en: 'WordPress Core',         es: 'WordPress Core' },
  read:                      { icon: '🔎', en: 'Read & Query',           es: 'Lectura y consulta' },
  write:                     { icon: '📝', en: 'Create & Edit',          es: 'Crear y editar' },
  rankmath:                  { icon: '🔍', en: 'SEO · Rank Math',        es: 'SEO · Rank Math' },
  seopress:                  { icon: '🔍', en: 'SEO · SEOPress',         es: 'SEO · SEOPress' },
  yoast:                     { icon: '🔍', en: 'SEO · Yoast',            es: 'SEO · Yoast' },
  menus:                     { icon: '🔗', en: 'Navigation Menus',       es: 'Menús de navegación' },
  utility:                   { icon: '🛠️', en: 'Utilities & Cache',      es: 'Utilidades y caché' },
  'code-snippets':           { icon: '🧩', en: 'Code Snippets',          es: 'Code Snippets' },
  multilanguage:             { icon: '🌐', en: 'Multilanguage',          es: 'Multilenguaje' },
  woocommerce:               { icon: '🛒', en: 'WooCommerce',            es: 'WooCommerce' },
  tec:                       { icon: '🗓️', en: 'The Events Calendar',    es: 'The Events Calendar' },
  cpt:                       { icon: '🗂️', en: 'Custom Post Types',      es: 'Custom Post Types' },
  'jetengine-options-pages': { icon: '⚡', en: 'JetEngine Options',      es: 'JetEngine: opciones' },
  'jetengine-query-builder': { icon: '⚡', en: 'JetEngine Queries',      es: 'JetEngine: consultas' },
  elementor:                 { icon: '🎨', en: 'Elementor',              es: 'Elementor' },
  learndash:                 { icon: '🎓', en: 'LearnDash',              es: 'LearnDash' },
  tutor:                     { icon: '📚', en: 'Tutor LMS',              es: 'Tutor LMS' },
  'agent-readiness':         { icon: '🤖', en: 'AI Readiness (llms.txt)', es: 'AI Readiness (llms.txt)' },
  accessibility:             { icon: '♿', en: 'Accessibility (WCAG)',    es: 'Accesibilidad (WCAG)' },
  'fse-templates':           { icon: '🖥️', en: 'FSE Block Templates',    es: 'Plantillas de bloques FSE' },
};

export const sections: Section[] = data as Section[];

export function sectionName(s: Section, lang: 'en' | 'es'): string {
  return sectionMeta[s.id]?.[lang] ?? s.name;
}

export function sectionIcon(s: Section): string {
  return sectionMeta[s.id]?.icon ?? '🧩';
}

/** Abilities in a section (all of them, including the core ones). */
export function sectionCount(s: Section): number {
  return s.abilities.length;
}

/** Plugin abilities only (ewpa/*), excluding WordPress core abilities. */
export const ewpaCount: number = sections.reduce(
  (n, s) => n + s.abilities.filter((a) => a.key.startsWith('ewpa/')).length,
  0,
);

export const totalCount: number = sections.reduce((n, s) => n + s.abilities.length, 0);
export const sectionTotal: number = sections.length;

export const typeCounts: Record<AbilityType, number> = sections.reduce(
  (acc, s) => {
    s.abilities.forEach((a) => { acc[a.type] += 1; });
    return acc;
  },
  { read: 0, write: 0, destructive: 0 } as Record<AbilityType, number>,
);
