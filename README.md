# reelbarrow

A wheelbarrow for reels: it files what
[automatic-ripping-machine](https://github.com/automatic-ripping-machine/automatic-ripping-machine)
rips into an archival video library. It identifies films and episodes, keeps each
disc's raw copy beside its transcode, writes sidecars that any player can read,
and asks a person only when it cannot be excellently sure.

It is built for one home server's Kubernetes cluster, and is in its dry-run
phase: it plans, records, and changes nothing.

- [docs/design.md](docs/design.md): what it does and why, with the evidence
- [docs/exporter.md](docs/exporter.md): the sidecar that copies ARM's jobs out as
  manifests
- [docs/releasing.md](docs/releasing.md): how versions are cut and deployed
- [todos/](todos/README.md): the work remaining, one spec per step

## Running it

[`compose.yaml`](compose.yaml) is an example deployment, in dry run with the
share mounted read-only:

```bash
VIDEO_ROOT=/path/to/video docker compose up -d
```

`VIDEO_ROOT` holds ARM's output and the `movies/` and `shows/` libraries, on one
filesystem. The web UI is on port 8000. `TMDB_TOKEN`, TMDB's API Read Access
Token, is what identifies films, and `FANART_KEY`, fanart.tv's personal API
key, is what filing fetches artwork with:

```bash
docker compose exec reelbarrow reelbarrow plan    # every manifest's plan
docker compose exec reelbarrow reelbarrow file    # each automatic plan carried out;
                                                  # in dry run, every change refused
```

## Development

```bash
devenv shell                   # Python, uv, ffmpeg, chromaprint
devenv test                    # every hook over every file, as CI runs it
reelbarrow serve               # the web UI on :8000, in dry-run mode
```

The secrets it reads are declared in [`secretspec.toml`](secretspec.toml), and
kept in your system keyring rather than a file. Store each once, then give it
only to the command that needs it:

```bash
secretspec set REELBARROW_TMDB_TOKEN               # prompts; not echoed
secretspec set REELBARROW_FANART_KEY
secretspec run -- reelbarrow plan path/to/manifest.json
```

The tests need none of them.

## Licence

MIT
