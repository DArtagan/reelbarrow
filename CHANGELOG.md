# Changelog

## [0.5.1](https://github.com/DArtagan/reelbarrow/compare/v0.5.0...v0.5.1) (2026-11-11)


### Documentation

* **agents:** quieten direnv, and run wt switch with --yes ([41eb1dd](https://github.com/DArtagan/reelbarrow/commit/41eb1ddb03fc10916b8fe7d0e64cbd1922aadc9e))
* **executor:** give the filing record a JSON Schema, docs/filing.schema.json ([41eb1dd](https://github.com/DArtagan/reelbarrow/commit/41eb1ddb03fc10916b8fe7d0e64cbd1922aadc9e))
* retire executor ([#24](https://github.com/DArtagan/reelbarrow/issues/24)) ([ae5cc94](https://github.com/DArtagan/reelbarrow/commit/ae5cc94e416bfdab52d3636079f64191e55167ad))
* **todos:** a spec shows an example of each new thing it writes ([41eb1dd](https://github.com/DArtagan/reelbarrow/commit/41eb1ddb03fc10916b8fe7d0e64cbd1922aadc9e))

## [0.5.0](https://github.com/DArtagan/reelbarrow/compare/v0.4.0...v0.5.0) (2026-11-11)


### Features

* **cli:** `reelbarrow file` files each automatic plan, and leaves review and hold plans alone ([5838560](https://github.com/DArtagan/reelbarrow/commit/5838560b64b8fc8cbd4d6fed7b054a988e4fe477))
* **disc-record:** file disc.json as the manifest as filed, with docs/disc.schema.json ([5838560](https://github.com/DArtagan/reelbarrow/commit/5838560b64b8fc8cbd4d6fed7b054a988e4fe477))
* **executor:** carry out automatic plans through one Writer, which refuses every change while dry run is on ([5838560](https://github.com/DArtagan/reelbarrow/commit/5838560b64b8fc8cbd4d6fed7b054a988e4fe477))
* **executor:** keep each filing's record beside disc.json, holding the case it was planned from ([5838560](https://github.com/DArtagan/reelbarrow/commit/5838560b64b8fc8cbd4d6fed7b054a988e4fe477))
* **plex:** ask Plex to scan each filed film's folder ([5838560](https://github.com/DArtagan/reelbarrow/commit/5838560b64b8fc8cbd4d6fed7b054a988e4fe477))
* **sidecars:** write movie.nfo from TMDB, and artwork from TMDB and fanart.tv ([5838560](https://github.com/DArtagan/reelbarrow/commit/5838560b64b8fc8cbd4d6fed7b054a988e4fe477))


### Documentation

* agent notes from single-manifest-plan, and no CLAUDE.local.md ([#21](https://github.com/DArtagan/reelbarrow/issues/21)) ([273c435](https://github.com/DArtagan/reelbarrow/commit/273c43593b1f96871e466406c355b5398847c664))
* **releasing:** list several changelog notes from one squash ([b02cd08](https://github.com/DArtagan/reelbarrow/commit/b02cd089c87084eb70e60a680daf8c1c75024d00))
* **releasing:** the commit-override marker is only ever the block ([baad413](https://github.com/DArtagan/reelbarrow/commit/baad413bf20ccb5634db116408986e375088f2f4))
* retire single-manifest-plan ([#19](https://github.com/DArtagan/reelbarrow/issues/19)) ([e815480](https://github.com/DArtagan/reelbarrow/commit/e815480cdc108710414d1e195167542fe963d2c1))
* **todos:** the embedded-tags and extras specs, ahead of first-filing and manifest-loop ([5838560](https://github.com/DArtagan/reelbarrow/commit/5838560b64b8fc8cbd4d6fed7b054a988e4fe477))

## [0.4.0](https://github.com/DArtagan/reelbarrow/compare/v0.3.1...v0.4.0) (2026-11-10)


### Features

* **plan:** plan and gate one manifest, executing nothing ([#18](https://github.com/DArtagan/reelbarrow/issues/18)) ([16c53e2](https://github.com/DArtagan/reelbarrow/commit/16c53e2ae8dfa67d5aeb00fdcbe14ea531ee4d9a))


### Documentation

* **exporter:** record the exporter proven on the cluster and a real disc ([#17](https://github.com/DArtagan/reelbarrow/issues/17)) ([323ff37](https://github.com/DArtagan/reelbarrow/commit/323ff37a82be68e0fbe40c486265abf2cd68f0ef))
* **todos:** build the pipeline from the smallest loop outward ([#15](https://github.com/DArtagan/reelbarrow/issues/15)) ([a43353d](https://github.com/DArtagan/reelbarrow/commit/a43353dff515ea952f7bd54598e006994ec9d957))

## [0.3.1](https://github.com/DArtagan/reelbarrow/compare/v0.3.0...v0.3.1) (2026-11-09)


### Bug Fixes

* **exporter:** export the jobs the sidecar's first pass skipped ([#14](https://github.com/DArtagan/reelbarrow/issues/14)) ([2897b40](https://github.com/DArtagan/reelbarrow/commit/2897b40bfd5834afd720b17fe4d92f568184e0a6))


### Documentation

* **todos:** fold the fixtures capture into dry-run-planner ([da2c90e](https://github.com/DArtagan/reelbarrow/commit/da2c90ed71ea97fb171f6a0a47ccf8c9fb5282af))

## [0.3.0](https://github.com/DArtagan/reelbarrow/compare/v0.2.0...v0.3.0) (2026-11-09)


### Features

* **analysis:** measure files and raw disc copies ([#5](https://github.com/DArtagan/reelbarrow/issues/5)) ([67ed9e6](https://github.com/DArtagan/reelbarrow/commit/67ed9e669611759574c809eea04ce34cf751d373))
* **exporter:** export ARM's jobs as manifests in reelbarrow's vocabulary ([#12](https://github.com/DArtagan/reelbarrow/issues/12)) ([eb91b70](https://github.com/DArtagan/reelbarrow/commit/eb91b70af01369f5516ae97afc1b19948499cf32))


### Documentation

* **design:** name the stamp's fields for their numbering ([a9a3dac](https://github.com/DArtagan/reelbarrow/commit/a9a3dac17387049f6c8c79d81af60fcb3008096b))
* **design:** name the stamp's title map by its field, `extracted` ([bb867c8](https://github.com/DArtagan/reelbarrow/commit/bb867c8a5e603f5a9c8e996dfed9047de007c6df))
* **design:** pair raw folders by the deployment's job stamp ([df3fb71](https://github.com/DArtagan/reelbarrow/commit/df3fb71ae98fef3d89f7a227349952c3a8797a24))
* **design:** pair raw folders by the deployment's job stamp ([b418158](https://github.com/DArtagan/reelbarrow/commit/b4181583583db1332d9b7b2eebb74bb7228b4532))
* **design:** read the stamp's duplicates and ARM's unrenamed feature ([c8e745d](https://github.com/DArtagan/reelbarrow/commit/c8e745daeed1d0fbf1fb9dbb20ea812a49060116))
* **design:** state the stamp's evolution rule and what `ripped` means ([62a20ce](https://github.com/DArtagan/reelbarrow/commit/62a20cecc8a13fd758467b57dbb8518c1eece918))
* fix references left by the AGENTS.md rename and the stamp field ([ad5da0f](https://github.com/DArtagan/reelbarrow/commit/ad5da0ffb07fde252b3055750b9b141b11dd38c5))
* let a pull request's title decide how it is merged ([#10](https://github.com/DArtagan/reelbarrow/issues/10)) ([6486a47](https://github.com/DArtagan/reelbarrow/commit/6486a4783073f1f2b1a5e7ab9a4bbef8ac134033))
* point references to CLAUDE.md at AGENTS.md ([643f622](https://github.com/DArtagan/reelbarrow/commit/643f622f0195f9f57af431728af60061a28aab51))
* **todos:** export ARM's manifests by polling its database ([#11](https://github.com/DArtagan/reelbarrow/issues/11)) ([5af4d12](https://github.com/DArtagan/reelbarrow/commit/5af4d121f870d08cb4584fe9079635060fb5eea1))

## [0.2.0](https://github.com/DArtagan/reelbarrow/compare/v0.1.1...v0.2.0) (2026-10-20)


### Features

* example compose deployment, generic docs, ARM hook spec ([3e9820c](https://github.com/DArtagan/reelbarrow/commit/3e9820c3c7ac973a1d3a18bf8fde0a5261468f05))
* ship an example compose.yaml ([f8d7c8d](https://github.com/DArtagan/reelbarrow/commit/f8d7c8d4da2aeaf5c689dbe482f83bc4cd391472))


### Bug Fixes

* create /data in the image, owned by the runtime user ([e212319](https://github.com/DArtagan/reelbarrow/commit/e212319449930bd00539d58763c3e4da7f07cc81))


### Documentation

* drop the cluster's internal hostnames ([dfcf5d0](https://github.com/DArtagan/reelbarrow/commit/dfcf5d0e7a077146dccb39e060c060b72cd2c2b2))
* refer to the deployment repository generically ([69459c0](https://github.com/DArtagan/reelbarrow/commit/69459c08da329c2bbec7598d6d161a8454bf705f))

## [0.1.1](https://github.com/DArtagan/reelbarrow/compare/v0.1.0...v0.1.1) (2026-10-19)


### Documentation

* name release tags as release-please writes them ([eb4c5e0](https://github.com/DArtagan/reelbarrow/commit/eb4c5e05654997e5b99e203e3ab77acc5b65c6ba))

## 0.1.0 (2026-10-19)


### Features

* scaffold reelbarrow ([a39258c](https://github.com/DArtagan/reelbarrow/commit/a39258c3bcdd81a59ec570c6bbb52e2e5cb0fd13))


### Documentation

* record what the first push verified ([6b57fd6](https://github.com/DArtagan/reelbarrow/commit/6b57fd67b09912c94fb51ca50121f2dec36a9ba8))
