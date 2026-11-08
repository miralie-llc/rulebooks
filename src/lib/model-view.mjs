import { catalogView, editionUrl } from "./catalog-view.mjs";
export const releaseUrl = (version) => `/bgsm/${version}/`;
export const conceptUrl = (version, id) => `/bgsm/${version}/concepts/${id}/`;
export function modelView(content) {
  const catalog = catalogView(content);
  const releases = content.records.filter((r) => r.kind === "BGSMRelease");
  const release = (version) => {
    const value = releases.find((r) => r.version === version);
    if (!value) throw new Error("Unknown BGSM version");
    return value;
  };
  const concepts = (version) =>
    release(version).concepts.map((pin) => catalog.record("Concept", pin));
  const usages = (version, concept) =>
    content.records
      .filter((r) => r.kind === "Formalization" && r.bgsm === version)
      .flatMap((mapping) => {
        const edition = catalog.record("RulebookEdition", mapping.edition);
        return mapping.coverage
          .filter((row) =>
            (row.concepts || []).some(
              (pin) =>
                pin.id === concept.id && pin.revision === concept.revision,
            ),
          )
          .map((row) => ({
            mapping,
            edition,
            row,
            rule: edition.sections
              .flatMap((s) => s.rules)
              .find((r) => r.id === row.rule),
            href: editionUrl(edition) + "#rule-" + row.rule,
          }));
      });
  // Membership in a release is a specification claim, not proof of implementation.
  const ruleConcepts = (edition, ruleId) =>
    catalog.formalizations(edition).flatMap((mapping) =>
      mapping.coverage
        .filter((row) => row.rule === ruleId)
        .flatMap((row) =>
          (row.concepts || []).map((pin) => ({
            concept: catalog.record("Concept", pin),
            mapping,
            status: row.status,
            href: conceptUrl(mapping.bgsm, pin.id),
          })),
        ),
    );
  return { releases, release, concepts, usages, ruleConcepts };
}
