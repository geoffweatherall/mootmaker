# Photorealistic demo avatars

## Summary

Replace the procedural cartoon avatars that
[person-avatar-upload-refactor.md](person-avatar-upload-refactor.md) ships with generated
photorealistic faces, so a demo environment looks like a company rather than a game lobby. This is a
change of image bytes only: the upload API, the storage model, the hosting and every handler are
built by that design and are not touched here.

## Status

**Shipped** — 2026-10-01. Geoff generated and reviewed the pool (mootmaker-demo-data #47, #48),
and demo-data was switched to it in #49, merged to `main` on 2026-10-01 without a release.

Verified on `claude-260929-9mjc` on 2026-10-01, after a reset and a fresh demo-data run, by
checking the result against the pool files rather than trusting the code: 100 people, 88 with a
photograph, 88 distinct, 88 of 88 served, and **0 where the photograph's sex differs from the one
the person's first name is tagged with** (40 women, 48 men). Signed in as the demo user, all 88
decoded on `/persons`.

Where it differs from the text below:

- **The pool is in `avatars-photo/`**, as `man-N.jpg` and `woman-N.jpg`, not a replacement of
  `avatars/`. That directory - the DiceBear drawings - was deleted in #49 rather than kept as a
  fallback, which settles open question 5.
- **The generator does not currently reproduce the committed pool.** Its ethnicity mix was changed
  after the pool was generated, which reshuffles every prompt and makes `pool.py` fail an assertion
  on start (see #47). The images and `manifest.json` are unaffected, so the pool is still
  *documented* - but the Definition of done's "reproducible from the committed script" holds only
  once the mix is restored or the pool is regenerated at the new one.
- Photographs are about 13 KB each after the API normalises them, against 5 KB for the drawings,
  and the jar carries 10 MB of them.

Split out of [person-avatar-upload-refactor.md](person-avatar-upload-refactor.md) on 2026-09-29, so
that design could proceed on hardware this one required and did not yet have.

## Scope / non-goals

**In scope**

- Choosing and installing a local image-generation stack on a GPU machine.
- Generating a pool of photorealistic face images.
- **Re-introducing gender matching**, which the parent design deliberately dropped. It restores
  `SampleData.FEMALE_FIRST_NAMES` (deleted there rather than left as dead code) and the
  male/female split of the pool, plus the unit case asserting an assigned image matches its name's
  tagged gender. This belongs here and not there because DiceBear styles are seeded from a string
  and take no gender at all, whereas a generated photograph does — the requirement only becomes
  expressible once the images are photorealistic.
- Replacing the committed pool in `mootmaker-demo-data/impl/src/main/resources/avatars/`.
- Recording the model, prompts and seeds so the pool is reproducible.

**Explicit non-goals**

- **No API change whatsoever.** No schema, no handler, no bucket, no distribution. If this design
  finds itself proposing one, something has been misunderstood.
- **No upload UI.** Still out of scope, as in the parent design.
- **No photographs of real people**, generated or otherwise sourced. See the parent design's
  reasoning on publicity rights.
- **No runtime generation.** The pool stays pre-generated and committed, for the same reason the
  parent design gives: demo-data is a Java Lambda and must not depend on a model or a third-party
  service while seeding.

## Trade-offs and decisions

### The model must be Apache-2.0 or equivalently unrestricted

The outputs are committed to a **public** repository, so the licence must permit redistribution, not
merely use. That rules out more of the field than people expect.

| Model | Licence | Verdict |
|---|---|---|
| **FLUX.2 [klein] 4B** | Apache 2.0 | **Preferred** — cleanest licence, ~10 GB VRAM at FP16, ~6 GB at FP8, 4-step generation |
| FLUX.1-schnell | Apache 2.0 | Fine, but superseded by the above |
| SDXL base 1.0 | OpenRAIL++-M | Acceptable; commercial use permitted |
| Stable Diffusion 1.5 | OpenRAIL-M | Acceptable; the CPU-only fallback |
| FLUX.1-dev | Non-commercial | **Excluded** |
| SDXL-Turbo, SD3 | Non-commercial / conditional | **Excluded** |

Verify the licence at the point of download rather than from this table — licences get revised, and
this document will not.

### Generation runs on a GPU machine, not this workstation

The primary workstation has no GPU, 16 cores and ~7 GB of free RAM. It can run SD 1.5 on CPU at
roughly 1–2 minutes per image, which is workable for an unattended batch but produces the weakest
faces of any option here. A machine with an RTX 3090/4070 or better runs FLUX.2 [klein] in seconds
per image.

Either [ComfyUI](https://github.com/black-forest-labs/flux2) or Hugging Face `diffusers` drives it
on Ubuntu. `diffusers` is preferred for this job: a fixed reproducible batch wants a seedable script,
not a node graph clicked once and forgotten.

### Small-model artifacts do not matter at avatar size

Avatars render at 32–40 px in the app. Distortions that would be glaring in a 1024 px portrait are
invisible there, which means the quality bar is far lower than "convincing photograph" and a
mid-sized model is genuinely sufficient. This is worth stating because it is the main argument
against spending effort on a larger model or a face-specific fine-tune.

## Choices you had me make

None yet — this document is a placeholder for work that has not started. Everything above is either
a constraint inherited from the parent design or a licence fact.

## Open questions

### Blocking

1. **Which machine, and what GPU is in it?** Determines whether FLUX.2 [klein] runs at FP16, needs
   FP8 quantisation, or is out of reach and the job falls back to SDXL or SD 1.5.
2. **Is the install acceptable on that machine?** Roughly 3 GB of Python packages plus a model
   checkpoint of 3–7 GB depending on variant and quantisation.

### Non-blocking

3. **Pool size.** The parent design ships 200. Photorealistic generation is slower but still cheap
   on a GPU, so there is no strong reason to shrink it.
4. **How much prompt variety is needed** for 200 faces that read as a plausible workforce — age,
   ethnicity, clothing, background — without drifting into caricature.
5. **Should the procedural pool be kept** as a fallback or for a "demo lite" mode, or deleted once
   this lands?

## Impacts on components

**mootmaker-demo-data only.**

- `impl/src/main/resources/avatars/` — contents replaced. Filenames and the male/female split keep
  their existing shape, so `SampleData` needs no change.
- The generation script and its README note are replaced to record the model, prompts and seeds.

No other repository is touched. That is the whole point of the split.

## Changes to the domain data model and data storage models

**N/A.** No schema, no DynamoDB attribute, no S3 layout change. Stored `avatarUrl` values change
because the bytes change, which is an ordinary reseed, not a migration.

## Technical considerations

- **Generation is reproducible or it is not worth doing.** Commit the script, the model identifier,
  the prompt list and the seeds. A pool nobody can regenerate is a pile of mystery bytes, and the
  parent design already sets this expectation for the procedural pool.
- **Images are normalised by the API on upload anyway** — decoded, resized to 256×256 and re-encoded
  as JPEG. Generating at 512 or 1024 and letting the API downscale is fine; generating below 256 is
  not.
- **Faces should not be recognisable as any real person.** Generated models can occasionally
  reproduce training-set likenesses. Spot-checking 200 images is impractical, but avoiding prompts
  that name real people is both obvious and sufficient.
- **What this leaves behind:** the model checkpoint on whichever machine runs it (several GB, and
  not something CI or any environment needs), plus the committed images themselves. Nothing new
  accumulates at runtime.
- **Cost:** none beyond electricity, assuming the GPU machine already exists.

## Testing impacts

**Unit (mootmaker-demo-data)** — one genuinely new case, for the gender matching this design
re-introduces: an assigned image's half of the pool matches its name's tag in
`FEMALE_FIRST_NAMES`. The existing pool tests carry over unchanged: every bundled resource
loads from the classpath, no avatar repeats within an environment. They are
written against the pool's shape rather than its contents, so replacing the images should not touch
them. If a test needs changing, that is a signal the parent design leaked image specifics into logic
that should not know about them.

**Every other layer: not impacted.** No API surface changes, so no new acceptance coverage is
warranted — the parent design's round-trip and decode checks already prove the machinery, and they
are image-agnostic by construction.

**mootmaker-release's smoke suite: not impacted.** It does not assert on avatars.

## Documentation impacts

- `mootmaker-demo-data/README.md` — update the note describing where the avatar library comes from.
- `tools/workstation/manifest.yaml` — add the generation toolchain, on the machine that runs it.
- [person-avatar-upload-refactor.md](person-avatar-upload-refactor.md) — once shipped, its note
  about procedural avatars being a first phase should point here as done rather than pending.

## Rollout & migration

Deploy demo-data, then `database-reset` and reseed per environment. Identical to the parent design's
rollout and for the same reason: avatar values point at objects that no longer exist once the pool
changes, and there is nothing worth migrating in demo data.

## Risks

- **Model licence turning out to be wrong after the images are committed** is the one hard-to-reverse
  outcome, since a public repository means a history rewrite rather than a deletion. Verify before
  generating, not after.
- **Uncanny or obviously-AI faces** would be worse than the cartoons they replace. Worth a human
  look at the pool before committing — this is a judgement call no test will catch.
- **This design never happening** is a real possibility and an acceptable one; the parent design
  ships a working product without it. It should be closed deliberately rather than left drifting.

## Implementation checklist

1. `[Geoff]` Confirm the machine and its GPU, and approve the install.
2. `[Claude]` Install the toolchain; record it in the workstation manifest.
3. `[Claude]` Draft and iterate the prompt set; generate a small sample for review.
4. `[Geoff]` Look at the sample and say whether it reads right.
5. `[Claude]` Generate the full pool; commit it with its script, seeds and prompts.
6. `[Claude]` Replace the pool in mootmaker-demo-data; confirm its unit tests still pass unchanged.
7. `[Claude]` Deploy to one ephemeral environment, reset, reseed, and look at the result.
8. `[Claude]` Documentation updates above.

## Definition of done

- mootmaker-demo-data's unit suite green, **without having needed changes** — the pool's shape is
  what its tests assert, not its contents.
- One ephemeral environment reseeded, where 100 demo people hold 90 distinct photorealistic avatars
  and 10 none, with no image shared by two people.
- A human has looked at the pool and is happy with it.
- The pool is reproducible from the committed script, model id, prompts and seeds.
- Documentation impacts done, including the parent design's pointer.
