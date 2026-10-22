# arm-manifest-hook: ARM writes what reelbarrow reads

## Opening prompt

> Build the script that runs inside ARM's container and writes
> `manifests/job-<id>.json` for reelbarrow, and prove it on a real disc. Read
> `todos/arm-manifest-hook.md`, then *What ARM knows, and where* and *The ARM
> manifest* in `docs/design.md`. Nothing here has been written or run; every
> fact about ARM's hook below was read from ARM `2.24.4`'s source.

## Why it lives here (decided 2026-10-19)

The manifest is how reelbarrow learns of ARM's jobs, so the script that writes it
ships with reelbarrow and every user runs the same one. Will agreed
with this split:

- **Here:** the manifest writer, its schema, and its tests.
- **In each deployment:** wiring it into ARM. ARM's `BASH_SCRIPT` setting holds
  one script. A site with no other hook points it at this one. A site that
  already runs a hook (Will's runs an audio handoff) adds a dispatcher that calls
  both, and the dispatcher belongs to that site.

## What ARM gives a hook (read from source, not exercised)

- `BASH_SCRIPT` runs on **every** notification, with `$1` = title and `$2` =
  body (`ripper/utils.py:88`). There is no completion hook as such.
- It runs as `/usr/bin/env bash <script>`, so **the configured file must be a
  bash script**. A Python file set there directly would be fed to bash.
- `job.pid` is `os.getpid()` of the ripper (`models/job.py:218`), so the hook's
  parent pid should equal `job.pid` and select the job's row in
  `/root/db/arm.db` exactly.

## Design

- **A bash shim that `exec`s a stdlib-only Python script.** ARM's image has
  Python and its `sqlite3` module; the `sqlite3` command-line tool may not be
  there. `exec` keeps the process id, so the Python process's parent is still
  the ripper. Nothing from the reelbarrow package is importable in ARM's
  container, so the script is a single standalone file.
- **The ripper's pid comes from an environment variable when one is set**,
  falling back to the parent pid. A dispatcher that runs the shim as a child
  makes itself the parent, which would select no row. It sets the variable to
  its own `$PPID` instead. Name it in this session, and document it for
  deployments.
- **Write on every notification, not just a few.** Matching message text, the
  way the audio handoff does, breaks when ARM rewords a message. Each run
  rewrites the job's manifest from the database's current state, so the last
  write wins and `status` says where the job is. The first write comes at "Found
  disc", which the case photo depends on. Confirm in ARM's source that this
  notification fires before the rip.
- **Write atomically**: to a temporary file in `manifests/`, then `rename()`.
  The service scans that directory and must never read half a file.
- **Open the database read-only** (`file:…?mode=ro`, with a busy timeout). ARM
  writes to it throughout a rip.
- **Version the schema** with a top-level `"schema": 1`, so reelbarrow's intake
  can refuse a manifest it does not understand rather than misread it. Contents
  are as *The ARM manifest* lists: the job row (title, year, IMDb ID, video type,
  label, disc type, `crc_id`, status, `path`) and its track rows.
- **An export mode** (for example `--all`) writes manifests for every job
  already in the database. Jobs 1–41 predate the hook, and
  [fixtures](fixtures.md) needs their manifests. Run it against a copy of the
  database, not the live one.
- **The manifest doesn't say which raw folder is the job's**, because ARM's
  database records no raw path. The deployment's ARM writes that into the raw
  folder instead, as `arm-job.json` (*The raw folder's stamp* in the design), and
  intake joins the two on `job_id`. So this script needn't look for raw at all,
  and shouldn't guess it from names. The stamp has its own `schema`, separate
  from the manifest's.
- **Fail loudly and never block ARM.** If no row matches the pid, log it and exit
  non-zero. Check in ARM's source what it does with a hook's exit status, so a
  failure here cannot stop a rip or another site's handoff.

## Tests

pytest against a SQLite database built from ARM `2.24.4`'s `job` and `track`
models, with synthetic rows. A real `arm.db` is never committed. Cover: a pid
selecting one job; the environment-variable override; no match; a manifest
rewritten as the status changes; export of every job; and atomic replacement.

## How a deployment gets the script

Decide in this session. Options: copy the file from a tagged release, attach
it to each GitHub release, or ship it in the reelbarrow image for an init
container to copy out. Whichever is chosen, the `schema` field is what keeps a
lagging copy from being misread.

## Done when

- The tests pass, and the script's use is documented, including the
  environment variable and the bash requirement.
- Export mode, run on a copy of the real database, writes a manifest for each of
  jobs 1–41, and their titles and `crc_id`s match the design's fixtures table.
- On a real disc insert, `job-<id>.json` appears at "Found disc", before the rip
  finishes, and is rewritten on completion with the final status. Its job id
  matches ARM's UI. This is the first time the `$PPID` link is exercised. If it
  fails, it is the assumption to revisit.
