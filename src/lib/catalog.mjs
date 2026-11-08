import fs from "node:fs";
import { catalogView } from "./catalog-view.mjs";
export { gameUrl, editionUrl, downloadUrl, tagLabel } from "./catalog-view.mjs";

export const content = JSON.parse(
  fs.readFileSync(
    `${process.cwd()}/.cache/site-generated/content.json`,
    "utf8",
  ),
);
export const isPreview = content.mode === "editorial-preview";
export const {
  record,
  games,
  allGames,
  editions,
  sources,
  families,
  defaultEdition,
  gameEditions,
  citedSources,
  formalizations,
} = catalogView(content);
