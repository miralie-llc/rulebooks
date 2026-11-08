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
