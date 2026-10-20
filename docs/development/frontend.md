# Frontend

## React application

`web/` is one React/TypeScript application built with Vite, Tailwind, and selected shadcn/ui controls. Python publishes data; React owns presentation. Game descriptors select identity, themes, and capabilities instead of separate application bundles.

The portal manifest contains only navigation and section summaries. Per-game guide search, section metadata, indexes, comparisons, and detail chunks load on demand. Hash routes work below `/rom-wiki/` on a plain static server. Legacy pathname bookmarks are not mapped to new routes; the custom 404 links back to the library.

### Local workflow

```sh
python -m romwiki site export-web --data-root build/data
npm --prefix web ci
npm --prefix web run dev
npm --prefix web run lint
npm --prefix web run typecheck
npm --prefix web test
npm --prefix web run build
npm --prefix web exec playwright install chromium
npm --prefix web run test:e2e
```

Use Node 22.12+. Browser tests serve the production artifact through the standard-library HTTP server without SPA rewrites. CI uses explicitly synthetic, ROM-free browser fixtures; local publication smoke tests iterate the actual exported game manifest. `scripts/frontend_fixture.py` is for isolated test workspaces only and must never supply published data.

### Complete frontend snapshots

```sh
python -m romwiki site snapshot-web
python -m romwiki site restore-web .romwiki/frontend-snapshot
```

These commands prepare and restore a complete local, checksum-pinned publication, including comparisons. `export-web` deletes files an earlier export left in its output that the new manifest no longer references, and refuses to write into a non-empty directory that holds no earlier export. `snapshot-web` also pins the new snapshot by writing its manifest to `sites/frontend-snapshot/manifest.json` and publishes its archive to the `snapshots` release (see below); pass `--no-upload` to pin without publishing, or `--no-pin` for a local trial snapshot. Neither command deploys.

The reviewed publication is pinned by `sites/frontend-snapshot/manifest.json`. Its content-addressed archive is an asset of the existing `snapshots` release. For a clean checkout, download the archive named in that manifest (its `archive` field), then restore and check it:

```sh
gh release download snapshots --repo pokelitee/rom-wiki --pattern <archive> --dir sites/frontend-snapshot
python -m romwiki site restore-web sites/frontend-snapshot
python scripts/check_frontend_publication.py
```

The restore verifies the archive and every resource checksum. The coverage check requires all published games, configured sections, reference guides, detail records, and applicable comparisons. CI runs this path and browser tests against the complete dataset in addition to the synthetic tests.

To update publication data after generating and reviewing it:

```sh
python -m romwiki site export-web --data-root build/data
python -m romwiki site snapshot-web
python scripts/check_frontend_publication.py
```

Then commit the pinned manifest through a PR. `snapshot-web` needs an authenticated GitHub CLI (`gh`). It uploads the archive under its content-addressed name, so an asset is never overwritten in place, and deletes every other `frontend-*` archive except the one `main` currently pins, which `main`'s CI and redeploys still need until the new manifest merges. The release therefore holds at most two archives. Older commits cannot restore their data; this project does not roll back by snapshot.

### Browser generator

The **Make a wiki** page (`#/make`, `web/src/features/generate/`) builds a wiki from the reader's ROM without uploading it:

- `web/src/generate/worker.ts` runs in a module worker. It loads Pyodide (pinned in the worker) from jsDelivr, installs the `generator/` bundle below after checking each file's SHA-256, mounts the ROM read-only with Emscripten's WORKERFS so a DS image is never copied into memory, and calls `romwiki.web_build.build_wiki(..., id_prefix="local-")`. Python log messages stream to the page as progress, and the runtime stays loaded for further builds while the page is open.
- A generated wiki's game ID is `local-` plus the first 12 hex digits of the ROM's SHA-256, so every resource path begins with an ID no published game uses. `web/src/data/client.ts` reads any path under a local ID from IndexedDB (`web/src/generate/store.ts`) instead of the network, so every page renders local wikis unchanged; `loadManifest` adds them to the library, marked unverified when no profile knew the ROM and outdated when a different generator wheel built them.
- Wikis export to and import from one gzipped JSON file (`web/src/generate/bundle.ts`), which is rejected unless its ID is a local ID and every file lies under it.

Browser tests import an export built from the published Platinum wiki (`web/tests/local-wiki.spec.ts`), since CI has no ROMs.

### Browser generator runtime

The Pages build also serves what the in-browser generator downloads, under `generator/`: the `romwiki` wheel, a zip of the profiles, site descriptors, and guides that `romwiki.web_build.build_wiki` reads, and one PokéDB pack per generation, all listed with checksums in `generator/manifest.json`. CI builds the wheel and the resources zip from the checkout. PokéDB is not in the repository, so its packs are published like the frontend snapshot: one `pokedb-*.tar` archive in the `snapshots` release, pinned by `sites/generator-runtime/manifest.json`.

After PokéDB changes, repack and pin it:

```sh
python -m romwiki site pack-pokedb
```

Then commit the pinned manifest through a PR. A pack drops the Pokémon fields the pipeline doesn't read (`moves` and `unverified_historical_fields`), which keeps each generation under half a megabyte compressed; the same PokéDB always gives the same archive. To lay out the bundle locally:

```sh
python -m pip wheel . --no-deps --wheel-dir .romwiki/wheel
python -m romwiki site restore-pokedb sites/generator-runtime --output .romwiki/pokedb-packs
python -m romwiki site bundle-generator --wheel .romwiki/wheel/*.whl --packs .romwiki/pokedb-packs
```

### Deployment

The React site is deployed on GitHub Pages. Every CI run builds and verifies a Pages artifact. On a push to `main`, CI deploys that same artifact once the `CI gate` passes, so a merged PR goes live without a separate step. PR runs never deploy. See [Operations](../operations.md#ci-and-github-pages) for manual redeploys and rollback.

### Migration history

The Python page renderers, MkDocs configuration, templates, assets, and serving/audit tooling have been removed. Their implementation remains in Git history at the last main commit before migration, `04b72f24827b557df4f8b4bf61cff8c3146fd824`.

Only the current snapshot archives are kept (see [Complete frontend snapshots](#complete-frontend-snapshots)). The protected `archive/dev-2026-10-13` tag preserves development history and is separate from publication snapshots.
