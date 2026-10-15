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

These commands prepare and restore a complete local, checksum-pinned publication, including comparisons. They do not create releases, upload assets, or deploy. Snapshot creation includes only resources referenced by the current manifest, excluding stale files from earlier exports. A clean checkout needs the reviewed snapshot manifest and its matching archive; no frontend archive has been published as part of this migration.

`romwiki site restore-data` imports only normalized downloads from the checksum-pinned historical wiki snapshots. It validates historical archive identity and member paths, without claiming that historical data matches current generator code. New schema-5 data snapshots retain current-source fingerprint checks. `restore-snapshot` also recognizes schema-4 historical archives and imports only their normalized downloads. Historical downloads alone cannot produce complete comparison pages; `export-web` fails if a comparative game lacks its comparison inputs.

### Migration boundary

Publishing is frozen in the workflow configuration. The last deployed MkDocs site remains available. The Python page renderers, MkDocs configuration, templates, assets, and serving/audit tooling have been removed. Their implementation remains in Git history. The unfinished agent worktree is preserved, and no archive tag is assumed to exist. The last working main commit before this migration is `04b72f24827b557df4f8b4bf61cff8c3146fd824`.
