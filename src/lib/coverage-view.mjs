import { catalogView } from "./catalog-view.mjs";
export const coverageUrl = (edition) =>
  `/editions/${edition.id}/${edition.revision}/coverage/`;
export function coverageView(content, edition) {
  const view = catalogView(content);
  return {
    reading: edition.readingStatus,
    mappings: view.formalizations(edition).map((mapping) => ({
      mapping,
      counts: mapping.coverage.reduce(
        (all, row) => ({ ...all, [row.status]: (all[row.status] || 0) + 1 }),
        {},
      ),
      evidence: content.records.filter(
        (r) =>
          r.kind === "VerificationRecord" &&
          r.formalization.id === mapping.id &&
          r.formalization.revision === mapping.revision,
      ),
      artifacts: content.records.filter(
        (r) =>
          r.kind === "BuildArtifact" &&
          r.formalization.id === mapping.id &&
          r.formalization.revision === mapping.revision,
      ),
    })),
  };
}
