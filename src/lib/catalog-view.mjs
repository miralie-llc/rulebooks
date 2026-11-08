// A pure projection shared by the page routes and fixture tests.
export const gameUrl = (game) =>
  `/games/${typeof game === "string" ? game : game.id}/`;
export const editionUrl = (edition) =>
  `/editions/${edition.id}/${edition.revision}/`;
export const downloadUrl = (value) =>
  `/data/records/${value.kind}/${value.kind === "BGSMRelease" ? value.version : `${value.id}/${value.revision}`}.json`;
export const tagLabel = (tag) => tag.replaceAll("-", " ");

export function catalogView(content) {
  const key = (kind, id, revision) => `${kind}/${id}/${revision}`;
  const index = new Map(
    content.records.map((r) => [key(r.kind, r.id, r.revision), r]),
  );
  function record(kind, pin) {
    const value = index.get(key(kind, pin.id, pin.revision));
    if (!value) throw new Error(`Unresolved site record: ${kind}`);
    return value;
  }
  const ofKind = (kind) => content.records.filter((r) => r.kind === kind);
  const games = content.games.map((pin) => record("Game", pin));
  // Selected pins win; historical game pages remain reachable after discovery changes.
  const retained = new Map();
  for (const game of ofKind("Game").sort((a, b) => a.revision - b.revision))
    retained.set(game.id, game);
  for (const game of games) retained.set(game.id, game);
  const editions = ofKind("RulebookEdition");
  function gameEditions(game) {
    return editions
      .filter((e) => e.gameId === game.id)
      .sort((a, b) => a.id.localeCompare(b.id) || b.revision - a.revision);
  }
  function citedSources(edition) {
    const pins = new Map();
    for (const section of edition.sections)
      for (const rule of section.rules) {
        for (const citation of (rule.origin || edition.origin)?.citations ||
          []) {
          pins.set(
            key("Source", citation.source.id, citation.source.revision),
            citation.source,
          );
        }
      }
    return [...pins.values()].map((pin) => record("Source", pin));
  }
  return {
    record,
    games,
    allGames: [...retained.values()],
    editions,
    sources: ofKind("Source"),
    families: ofKind("GameFamily"),
    defaultEdition: (game) => record("RulebookEdition", game.defaultEdition),
    gameEditions,
    citedSources,
    formalizations: (edition) =>
      ofKind("Formalization").filter(
        (r) =>
          r.edition.id === edition.id &&
          r.edition.revision === edition.revision,
      ),
  };
}
