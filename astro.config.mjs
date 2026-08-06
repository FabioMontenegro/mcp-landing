import { defineConfig } from 'astro/config';

export default defineConfig({
  output: 'static',
  site: 'https://mcp.fabiomontenegro.com',
  redirects: {
    '/en/': '/',
  },
});
