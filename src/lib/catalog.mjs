import fs from "node:fs";
import { catalogView } from "./catalog-view.mjs";
export { gameUrl, editionUrl, downloadUrl, tagLabel } from "./catalog-view.mjs";

export const content = JSON.parse(
  fs.readFileSync(
    `${process.cwd()}/.cache/site-generated/content.json`,
    "utf8",
  ),
);
export const isFixture = content.mode === "contract-fixture";
export const isPreview = content.mode !== "publication";
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

import { modelView } from "./model-view.mjs";
export const model = modelView(content);
