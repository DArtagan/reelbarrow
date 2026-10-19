# movie-filing: the first real filing

## Opening prompt

> Turn reelbarrow's plans into actions on the share, for the four unambiguous
> films only. Read `todos/movie-filing.md`, then step 7 of *The service*,
> *Target layout* and *Sidecars and embedded metadata* in `docs/design.md`.
> This is the first step that writes to the media library. Prove each
> precondition below before turning dry run off.

## Scope

- **The executor**: the single choke point for every write, rename and delete
  under the video root, which refuses all of them while `dry_run` is true. Add the
  test that no other module writes there (see *Rules that protect the library*
  in `CLAUDE.md`).
- **Order**: renames on the same filesystem, then sidecars, then leftover
  deletion, then the ledger entry. Then a Plex partial scan of the touched folder
  (`/library/sections/{id}/refresh?path=…`), because Plex's own change detection
  cannot be relied on over CIFS.
- **Sidecars**: NFO and artwork per *Sidecars and embedded metadata*, from TMDB and
  fanart.tv.
- **`raw/<LABEL> [<identity>]/disc.json`** and the ignore markers in every `raw/`.
- **Films**: Hallelujah Trail, Jaunty Jalopies, The Great Race, and The Polar
  Express, including its raw pairing to the misnamed Mary-Kate folder.

## Preconditions, each checked rather than assumed

- **Write permission.** The image runs as uid 1000, and the CIFS mount of
  `video-pv` sets no `uid`, `gid`, `file_mode` or `dir_mode` (its options are just
  `rw`), so what that uid may write is unknown. Test it on a scratch directory
  before anything else, and fix it in vulcanus-proxmox if needed.
- **Plex keeps watched state** when a folder is renamed and its file replaced.
  This matters for every re-ripped legacy title (*Case 9*). Test it once on a
  throwaway item.
- **Snapshots are current** on `rpool/storage/media`. Deleting leftovers is
  acceptable only because of them (Will, 2026-10-04).
- **Secrets** for fanart.tv and Plex added to vulcanus-proxmox's reelbarrow
  secret.

## The switch, in vulcanus-proxmox

Set `REELBARROW_DRY_RUN` to `"false"` and drop `readOnly` from the video mount,
in one commit. Only these four films should be gated automatic at that moment.
Every other job must come out review or hold, so confirm that in the dry-run
plans first.

Before turning it on, decide the backup for the ledger: once it records real
moves, it is the only history of what was moved where. vulcanus-proxmox's
`docs/kubernetes.md`, *Adding a stateful workload*, has the options. A SQLite
database with steady writes gets a dump.

## Done when

Measured on the share and in Plex:

- Each of the four is visible in Plex without a manual scan.
- Each `raw/` holds the right disc, with `disc.json`.
- `completed/movies/` holds nothing for those jobs.
- The ledger's record of each matches the share.
