# reelbarrow

A wheelbarrow for reels: it files what
[automatic-ripping-machine](https://github.com/automatic-ripping-machine/automatic-ripping-machine)
rips into an archival video library. It identifies films and episodes, keeps each
disc's raw copy beside its transcode, writes sidecars that any player can read,
and asks a person only when it cannot be excellently sure.

It is built for one home server, deployed by
[vulcanus-proxmox](https://github.com/DArtagan/vulcanus-proxmox), and is in its
dry-run phase: it plans, records, and changes nothing.

- [docs/design.md](docs/design.md): what it does and why, with the evidence
- [docs/releasing.md](docs/releasing.md): how versions are cut and deployed
- [todos/](todos/README.md): the work remaining, one spec per step

## Development

```bash
devenv shell                   # Python, uv, ffmpeg, chromaprint
devenv test                    # every hook over every file, as CI runs it
reelbarrow serve               # the web UI on :8000, in dry-run mode
```

## Licence

MIT
