# Roles — the hats

Mootmaker is worked on by one person, but not always doing the same *kind* of work. Deciding what
the product should do is a different job from building it, which is different again from writing
about it or keeping it running. Each of those wants different inputs, produces different artifacts,
and has a different idea of what "done" means.

These documents name those jobs so a session can start in one deliberately, rather than drifting
between them and doing all of them badly.

**This is a filing system for kinds of work, not a staffing plan.** One person wears every hat.
The value is in the switch being explicit — "I am wearing the product owner hat now, so I should be
arguing about whether we should build this, not how" — because that is the distinction most easily
lost when you are both the person asking and the person building.

## The hats

| Hat | The question it answers | Owns |
|---|---|---|
| [Developer](developer.md) | How should this be built, and does it work? | `designs/`, all code repos, the test suites |
| [Product owner](product-owner.md) | What should exist, and in what order? | [`business-functionality.md`](../reference/business-functionality.md), [`use-cases.md`](../reference/use-cases.md), issue triage and priority |
| [Marketer](marketer.md) | How is this presented, and to whom? | [`features-overview.md`](../showcase/features-overview.md), the brochure, [branding](../showcase/branding/) |
| [Operator](operator.md) | Is it running, is it safe, and what does it cost? | [`environments.md`](../process/environments.md), the bootstrap repos, admin tooling, security and privacy |
| [Author](author.md) | What did we learn, and can someone else use it? | [`learnings.md`](../showcase/learnings.md), [`debugging-techniques.md`](../showcase/debugging-techniques.md), the README's showcase content |

## Using them

**Starting a session.** Each role document has a "Starting a session in this role" section listing
what to read first. Point an agent at the role document and it has the right context without being
told the same things every time.

**On the board.** Issues carry a `hat:` label, so the project board can be filtered by role. Useful
for spotting that one hat has quietly accumulated everything while another has not been worn in
months.

**Agent definitions.** [`agents/`](agents/) holds a tool-agnostic agent definition per hat.
`tools/install-agents.sh` links them into `~/.claude/agents/` so they are available from any repo
checkout. They live in the repository rather than in the tool's config directory because the
workspace root is inside no git repository — anything left there is unversioned and does not exist
on another machine.

**Templates.** [`templates/`](templates/) holds the document shapes some hats produce repeatedly.

## On the shape of this set

**Security and privacy is folded into Operator**, not given its own hat. One person wearing six hats
is a filing system rather than a process, and security work here — Cognito configuration, IAM
guardrails, the privacy policy — sits naturally with the person already thinking about what is
deployed and what it can reach. Worth revisiting if security work starts feeling homeless.

**Author was not on the original list.** It was proposed because it is genuinely distinct work that
this project does deliberately: the learnings essay and the debugging-techniques write-up exist to
serve the portfolio goal, and writing them is not developer work. If it turns out to be over-fitting
— if nobody ever consciously puts that hat on — it should be removed rather than maintained.
