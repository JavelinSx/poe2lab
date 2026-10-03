// poe2lab's site (docs/SITE.md): pages are served static (SPA), data comes from the API - Nitro's server routes on
// Cloudflare Workers with D1 (the database) and R2 (the builds' packages). In `npm run dev` nitro-cloudflare-dev gives
// the API local copies of both (wrangler.toml).
export default defineNuxtConfig({
  compatibilityDate: "2026-10-01",
  ssr: false,
  devtools: { enabled: false },
  modules: ["nitro-cloudflare-dev"],
  css: ["~/assets/css/ds.css", "~/assets/css/site.css", "~/assets/css/app.css"],
  nitro: { preset: "cloudflare_module" },
  app: {
    head: {
      htmlAttrs: { lang: "ru" },
      title: "poe2lab — билды Path of Exile 2",
      meta: [
        { name: "viewport", content: "width=device-width, initial-scale=1" },
        { name: "description", content: "Билды Path of Exile 2, посчитанные движком Path of Building" },
      ],
    },
  },
});
