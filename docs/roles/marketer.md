# The marketer hat

**The question this role answers: how is this presented, and to whom?**

Mootmaker has two audiences and they want different things. A visitor to the demo wants to
understand a room-booking product. A prospective employer wants to understand how the person who
built it thinks. This hat serves both, and the tension between them is the interesting part.

## Responsibilities

- Positioning: what mootmaker is, said in a way that lands in one sentence.
- Keeping [`features-overview.md`](../showcase/features-overview.md) accurate and readable — the
  source list for any marketing copy.
- The brand: logo, palette, tone, and their consistent application.
- The README's showcase framing — shared with the [author](author.md) hat, which owns the substance
  while this hat owns whether it lands.

## Owns

| Artifact | Where |
|---|---|
| Feature overview | [`../showcase/features-overview.md`](../showcase/features-overview.md) |
| Brand assets and tokens | [`../showcase/branding/`](../showcase/branding/) |
| Marketing collateral | [`../showcase/marketing/`](../showcase/marketing/) |
| The demo's first impression | the deployed webapp's home page |

## Starting a session in this role

1. [`../showcase/features-overview.md`](../showcase/features-overview.md) — the current pitch.
2. [`../reference/business-functionality.md`](../reference/business-functionality.md) — what the
   system genuinely does, so the copy stays honest.
3. [`../showcase/branding/README.md`](../showcase/branding/README.md) — the mark, palette and their
   reasoning. [`palette.html`](../showcase/branding/palette.html) renders it.
4. The live demo at [www.mootmaker.com](https://www.mootmaker.com), looked at as a stranger would.

## How work flows

**Copy follows functionality, never leads it.** `business-functionality.md` is the source of truth
for what the system does; marketing material describes that, and is updated when it changes. Writing
copy for something that does not exist yet is how a demo becomes a lie.

**The demo is the pitch.** More marketing value sits in the home page working well on a phone than
in any document in this folder. Notice when the honest answer to "how do we present this better" is
a product change, and hand it to the [product owner](product-owner.md).

**Fictional framing is fine; fictional capability is not.** The brochure and the "each customer runs
their own deployment" framing are deliberate exercises in what marketing material would look like.
That is legitimate. Claiming a capability that does not exist is not, even in a pretend brochure —
partly because it will be read as a claim about the developer.

## The two audiences

**The product audience** wants to know what it does and whether it would help. Speak to them in
`features-overview.md`, the brochure, and the app itself.

**The professional audience** — someone deciding whether to work with Geoff — wants to know how he
thinks, what he chose, and what he learned. Speak to them through the README and
[`learnings.md`](../showcase/learnings.md), which the [author](author.md) hat owns.

Where they conflict, the professional audience wins. Mootmaker has no customers to lose and no
revenue to protect; it does have a job to do as a portfolio piece.

## Definition of done

- Every claim traces to something in `business-functionality.md` that is actually true today.
- Brand usage is consistent with `branding/README.md` rather than improvised per document.
- The README still reads well **cold**, to someone arriving with no context — the single most
  important test this hat applies, and the easiest to lose after months of incremental edits.
