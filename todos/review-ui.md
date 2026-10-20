# review-ui: when the gate says "ask"

## Opening prompt

> Build reelbarrow's review page and its notifications. Read
> `todos/review-ui.md`, then *The review UI* and the decisions on reviews in
> `docs/design.md`. The reviewer is usually Will's brother, on a phone, with the
> disc case in hand.

## Who it is for

*"Preferably my brother at his house - as he'll be the one inserting the discs
and will have the cases on-hand for easy identification"*, on *"Phone, desktop or
laptop"* (Will, 2026-10-03). The page has to be usable by someone who is not
going to read documentation.

## Scope

- One page per job: what ARM thought; the plan in plain language; and, for each
  uncertain item, the evidence that made it uncertain (a frame grab, a transcript
  excerpt, a runtime comparison).
- Actions: accept; correct (search TMDB, pick an episode, label an edition); or
  "not sure, leave for Will". A correction replans the job and goes back
  through the gate. It does not bypass the gate.
- Pushover: "filed" or "review needed", with a link. ARM's Pushover keys are
  in the deployment repository, with ARM's other keys. A separate app token
  keeps reelbarrow's messages distinguishable.
- Every correction is logged with its evidence, ready to become an eval sample
  (*Testing*, layer 4).
- Server-rendered with HTMX, phone-first, no SPA build. LAN-only, on the internal
  ingress like ARM's own web UI. Whether it needs auth beyond that is a
  question to raise with Will, not a default to pick.

## Done when

- Will's brother resolves a real review job from his phone without help. Ask
  him how it went, and write down what confused him.
- A correction made on the page produces a replanned job that the gate then
  passes or holds by its ordinary rules.
