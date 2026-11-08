import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
const root = path.resolve("dist");
const read = (name) => fs.readFileSync(path.join(root, name), "utf8");
const walk = (dir) =>
  fs
    .readdirSync(dir, { withFileTypes: true })
    .flatMap((e) =>
      e.isDirectory() ? walk(path.join(dir, e.name)) : [path.join(dir, e.name)],
    );
const pages = walk(root).filter((p) => p.endsWith(".html"));
const catalog = JSON.parse(read("data/catalog.json"));

test("every built local link, asset and fragment resolves without duplicate anchors", () => {
  for (const file of pages) {
    const html = fs.readFileSync(file, "utf8");
    const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map((m) => m[1]);
    assert.equal(new Set(ids).size, ids.length, `Duplicate anchor: ${file}`);
    const relative = path.relative(root, file);
    const base = new URL(
      relative === "index.html"
        ? "/"
        : "/" + relative.replace(/index\.html$/, ""),
      "https://example.test",
    );
    for (const [, href] of html.matchAll(/\b(?:href|src)="([^"]+)"/g)) {
      const url = new URL(href.replaceAll("&amp;", "&"), base);
      if (url.origin !== base.origin) continue;
      const target = path.join(
        root,
        decodeURIComponent(url.pathname),
        url.pathname.endsWith("/") ? "index.html" : "",
      );
      assert.ok(fs.existsSync(target), `${relative}: missing ${url.pathname}`);
      if (url.hash && target.endsWith(".html")) {
        assert.ok(
          fs
            .readFileSync(target, "utf8")
            .includes(`id="${decodeURIComponent(url.hash.slice(1))}"`),
          `${relative}: missing ${url.href}`,
        );
      }
    }
  }
});

test("collected catalog is actual draft content with scope, citations and exact rule URLs", () => {
  assert.equal(catalog.mode, "editorial-preview");
  assert.equal(catalog.games.length, 3);
  const editions = catalog.records.filter((r) => r.kind === "RulebookEdition");
  assert.equal(editions.length, 4);
  for (const edition of editions) {
    const url = `editions/${edition.id}/${edition.revision}/`;
    const html = read(url + "index.html");
    assert.match(html, /Editorial draft/);
    assert.match(html, /noindex, nofollow/);
    assert.match(html, /Not yet formalized/);
    assert.ok(!html.includes("Reviewed edition"));
    for (const section of edition.sections)
      for (const rule of section.rules) {
        assert.ok(html.includes(`href="/${url}#rule-${rule.id}"`));
        assert.ok(html.includes(`id="rule-${rule.id}"`));
      }
    const download = JSON.parse(
      read(
        `data/records/RulebookEdition/${edition.id}/${edition.revision}.json`,
      ),
    );
    assert.deepEqual(download.record, edition);
    assert.equal(download.purpose, "editorial-preview");
    assert.ok(!("review" in download.record));
  }
  assert.match(read("games/chess/index.html"), /not a complete playing guide/);
  assert.match(read("games/nim-normal-play/index.html"), /nim-one-two\/1\//);
  assert.match(
    read("games/rock-paper-scissors/index.html"),
    /Editorial choice/,
  );
});

test("site has no fixture artifacts, private workflow files or raw captures", () => {
  const files = walk(root).map((p) => path.relative(root, p));
  assert.ok(
    !files.some((p) =>
      /(?:^|\/)(tests|work|reference|tools|node_modules)\//.test(p),
    ),
  );
  assert.ok(!files.some((p) => /\.(pdf|py|md)$/.test(p)));
  for (const file of files.filter((p) => /\.(json|html)$/.test(p))) {
    assert.doesNotMatch(
      read(file),
      /"testOnly"|contract-fixture|GameKnowledgeDraft|ReferenceAsset/,
    );
  }
});

test("publisher fixtures keep separate games, default pins and earlier rulebook revisions", async () => {
  const { catalogView, editionUrl } = await import(
    "../src/lib/catalog-view.mjs"
  );
  const fixture = JSON.parse(
    fs.readFileSync(
      "tests/fixtures/publication/publisher-editions.json",
      "utf8",
    ),
  );
  const view = catalogView({
    records: fixture.records,
    games: fixture.publication.games,
  });
  assert.equal(view.games.length, 2);
  const [first, second] = view.games;
  assert.notEqual(first.id, second.id);
  assert.equal(first.family.id, second.family.id);
  assert.equal(
    view.record("PublisherEdition", first.publisherEdition).label,
    "First edition",
  );
  assert.equal(view.defaultEdition(first).revision, 2);
  assert.deepEqual(
    view.gameEditions(first).map((e) => e.revision),
    [2, 1],
  );
  assert.match(editionUrl(view.gameEditions(first)[1]), /\/1\/$/);
  const old = structuredClone(first);
  old.revision = 2;
  old.title = "New title not selected";
  const retained = catalogView({
    records: [...fixture.records, old],
    games: [fixture.publication.games[0]],
  });
  assert.equal(retained.games.length, 1);
  assert.equal(retained.allGames.length, 2);
  assert.equal(
    retained.allGames.find((g) => g.id === first.id).title,
    first.title,
  );
});

test("formalization coverage belongs to an exact edition revision", async () => {
  const { catalogView } = await import("../src/lib/catalog-view.mjs");
  const fixture = JSON.parse(
    fs.readFileSync("tests/fixtures/publication/first-games.json", "utf8"),
  );
  const view = catalogView({
    records: fixture.records,
    games: fixture.publication.games,
  });
  const formal = fixture.records.find((r) => r.kind === "Formalization");
  assert.ok(
    view.formalizations(formal.edition).some((r) => r.id === formal.id),
  );
  assert.deepEqual(
    view.formalizations({ ...formal.edition, revision: 999 }),
    [],
  );
});

test("BGSM is explicitly empty while editorial vocabulary is browsable", () => {
  assert.match(read("bgsm/index.html"), /No published BGSM release yet/);
  const vocabulary = JSON.parse(read("data/vocabulary/0.2.json"));
  assert.equal(vocabulary.status, "editorial-draft");
  assert.ok(vocabulary.terms.length > 40);
  const html = read("vocabulary/0.2/index.html");
  assert.match(html, /NOT EXECUTABLE SEMANTICS/);
  for (const term of vocabulary.terms)
    assert.ok(html.includes(`id="term-${term.id}"`));
});

test("concept usages follow exact model, concept and rulebook pins in both directions", async () => {
  const { modelView } = await import("../src/lib/model-view.mjs");
  const fixture = JSON.parse(
    fs.readFileSync("tests/fixtures/publication/first-games.json", "utf8"),
  );
  const view = modelView({
    records: fixture.records,
    games: fixture.publication.games,
  });
  const release = view.releases[0];
  const concept = view
    .concepts(release.version)
    .find((c) => view.usages(release.version, c).length);
  assert.ok(concept);
  const usage = view.usages(release.version, concept)[0];
  assert.ok(usage.rule.statement);
  assert.ok(
    view
      .ruleConcepts(usage.edition, usage.rule.id)
      .some(
        (link) =>
          link.concept.id === concept.id && link.href.includes(release.version),
      ),
  );
  assert.equal(view.usages("99.0.0", concept).length, 0);
  assert.equal(
    view.usages(release.version, { ...concept, revision: 999 }).length,
    0,
  );
  assert.equal(
    view.ruleConcepts({ ...usage.edition, revision: 999 }, usage.rule.id)
      .length,
    0,
  );
  const archived = {
    ...release,
    version: "0.0.0-fixture.0",
    status: "archived",
  };
  const history = modelView({
    records: [...fixture.records, archived],
    games: fixture.publication.games,
  });
  assert.equal(history.release(archived.version).status, "archived");
  assert.equal(
    history.concepts(archived.version)[0].revision,
    release.concepts[0].revision,
  );
});

test("download inventory matches served bytes and discovery stays under budget", async () => {
  const { createHash } = await import("node:crypto");
  const inventory = JSON.parse(read("data/downloads.json"));
  for (const item of inventory.files) {
    const raw = fs.readFileSync(path.join(root, item.url));
    assert.equal(raw.length, item.bytes, item.url);
    assert.equal(
      createHash("sha256").update(raw).digest("hex"),
      item.sha256,
      item.url,
    );
  }
  const budget = JSON.parse(read("data/discovery/budget.json"));
  assert.equal(budget.limitBytes, 20 * 1024);
  for (const [id, size] of Object.entries(budget.games)) {
    assert.equal(
      Buffer.byteLength(read(`data/discovery/games/${id}.json`)),
      size,
    );
    assert.ok(size <= budget.limitBytes);
    const row = JSON.parse(read(`data/discovery/games/${id}.json`));
    assert.ok(!("records" in row) && !("sections" in row));
  }
});

test("search distinguishes draft games, formal concepts and editorial terms", () => {
  const index = JSON.parse(read("data/search.json"));
  assert.equal(index.entries.filter((e) => e.kind === "game").length, 3);
  assert.equal(index.entries.filter((e) => e.kind === "concept").length, 0);
  assert.equal(index.entries.filter((e) => e.kind === "vocabulary").length, 50);
  assert.ok(
    index.entries
      .filter((e) => e.kind === "game")
      .every((e) => e.status === "editorial-preview"),
  );
  assert.match(read("gaps/index.html"), /No evidenced semantic gaps/);
  const html = read("editions/nim-one-two/1/coverage/index.html");
  for (const label of [
    "Reading completeness",
    "Formal coverage",
    "Verification evidence",
    "Not yet formalized",
  ])
    assert.ok(html.includes(label));
});

test("coverage never converts a mapping into successful executable verification", async () => {
  const { coverageView } = await import("../src/lib/coverage-view.mjs");
  const fixture = JSON.parse(
    fs.readFileSync("tests/fixtures/publication/first-games.json", "utf8"),
  );
  const content = {
    records: fixture.records,
    games: fixture.publication.games,
  };
  const formal = fixture.records.find((r) => r.kind === "Formalization");
  const edition = fixture.records.find(
    (r) =>
      r.kind === "RulebookEdition" &&
      r.id === formal.edition.id &&
      r.revision === formal.edition.revision,
  );
  const view = coverageView(content, edition);
  assert.ok(view.mappings.length);
  assert.ok(view.mappings.every((m) => m.evidence.length === 0));
  const evidence = {
    kind: "VerificationRecord",
    id: "fixture-failed",
    revision: 1,
    formalization: { id: formal.id, revision: formal.revision },
    result: "fail",
    method: "scenarios",
    scope: "Test only",
  };
  const withEvidence = coverageView(
    { ...content, records: [...content.records, evidence] },
    edition,
  );
  assert.equal(
    withEvidence.mappings.find((m) => m.mapping.id === formal.id).evidence[0]
      .result,
    "fail",
  );
});
