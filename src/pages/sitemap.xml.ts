import type { APIRoute } from 'astro';

const origin = 'https://mcp.fabiomontenegro.com';

/** Page paths without language prefix; every page exists in English (root) and Spanish (/es/). */
const paths = ['', 'abilities/'];

function entry(loc: string, path: string): string {
  const en = `${origin}/${path}`;
  const es = `${origin}/es/${path}`;
  return [
    '  <url>',
    `    <loc>${loc}</loc>`,
    `    <xhtml:link rel="alternate" hreflang="en" href="${en}"/>`,
    `    <xhtml:link rel="alternate" hreflang="es" href="${es}"/>`,
    `    <xhtml:link rel="alternate" hreflang="x-default" href="${en}"/>`,
    '  </url>',
  ].join('\n');
}

export const GET: APIRoute = () => {
  const urls = paths.flatMap((p) => [entry(`${origin}/${p}`, p), entry(`${origin}/es/${p}`, p)]);
  const body = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">',
    ...urls,
    '</urlset>',
    '',
  ].join('\n');
  return new Response(body, { headers: { 'Content-Type': 'application/xml; charset=utf-8' } });
};
