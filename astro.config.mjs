import { defineConfig } from "astro/config";

export default defineConfig({
  site: "https://rulebooks.games",
  output: "static",
  publicDir: "./.cache/site-generated/public",
  trailingSlash: "always",
  server: { host: "127.0.0.1" },
});
