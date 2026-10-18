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

These commands prepare and restore a complete local, checksum-pinned publication, including comparisons. They do not create releases, upload assets, or deploy. Snapshot creation includes only resources referenced by the current manifest, excluding stale files from earlier exports.

The reviewed publication is pinned by `sites/frontend-snapshot/manifest.json`. Its content-addressed archive is an asset of the existing `snapshots` release. For a clean checkout, download the archive named in that manifest (its `archive` field), then restore and check it:

```sh
gh release download snapshots --repo pokelitee/rom-wiki --pattern <archive> --dir sites/frontend-snapshot
python -m romwiki site restore-web sites/frontend-snapshot
python scripts/check_frontend_publication.py
```

The restore verifies the archive and every resource checksum. The coverage check requires all published games, configured sections, reference guides, detail records, and applicable comparisons. CI runs this path and browser tests against the complete dataset in addition to the synthetic tests.

To update publication data, generate and review a new snapshot, upload its uniquely named archive to the existing release without replacing assets, and update the committed manifest through a PR. Keep older archives for historical restoration.

### Deployment

The React site is deployed on GitHub Pages. Every CI run builds and verifies a Pages artifact. On a push to `main`, CI deploys that same artifact once the `CI gate` passes, so a merged PR goes live without a separate step. PR runs never deploy. See [Operations](../operations.md#ci-and-github-pages) for manual redeploys and rollback.

### Migration history

The Python page renderers, MkDocs configuration, templates, assets, and serving/audit tooling have been removed. Their implementation remains in Git history at the last main commit before migration, `04b72f24827b557df4f8b4bf61cff8c3146fd824`.

Keep the `snapshots` release and the `frontend-*` archives that current or historical frontend manifests reference; they support restoration from earlier commits, and absence from the current manifest does not make one disposable. The retired per-game `generated-wiki` archives were deleted, so commits from before the frontend snapshot can no longer restore their data. The protected `archive/dev-2026-10-13` tag preserves development history and is separate from publication snapshots.
