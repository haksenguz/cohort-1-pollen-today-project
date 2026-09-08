# How disciplined teams keep AI agents on-spec — and how we do it here

Short version: seniors don't trust agents, they constrain them. The output looks
professional when the process forces it to, not when you ask nicely. Below is
what the 2026 practice converges on, then exactly where each idea lives in this
repo.

## What the research says

**Drift is the real problem, not speed.** The failure mode in 2026 isn't slow
generation. It's confident code that solves the wrong problem because nobody
grounded it in a spec. Spec-driven development (SDD) makes a written spec the
shared source of truth for humans and agents both. ([Microsoft][ms],
[Pluralsight][ps])

**Standing instruction files must stay short.** AGENTS.md / CLAUDE.md ride along
in every session, but models reliably follow only ~150–200 rules before
compliance decays. The auto-generated everything-file is "a failure mode wearing
a diligence costume." Keep it tight, categorized, and pointing to detail rather
than inlining it. ([TrueFoundry][tf])

**Encode standards, don't describe them.** Martin Fowler's team recommends four
parts per instruction (role, context, categorized standards by
critical/important/advisory, output format), kept small and single-purpose,
versioned in the repo through PRs. The governance is the workflow: standards
apply when the check runs, not when someone remembers to audit. ([Fowler][mf])

**Rules are errors, not warnings.** Repository-scoped rules injected at session
start work as hard gates. Every rule is "error" severity so it blocks, it
doesn't nag. ([Codacy][cd])

**Three layers, in order.** Constraint harness first (cut the failure volume),
feedback loops second (let the agent self-correct), quality gates third (catch
what the first two missed). A CI pipeline turns review burden into deterministic
evidence: lint, types, tests, security. ([Augment][ag], [Axiom][ax])

**Separate who decides from who executes.** Give each agent one responsibility.
Keep planning/deciding agents apart from executing agents. For anything
high-impact, a human reviews. This is exactly our LLM-vs-triage split. ([Camunda][cm])

**Don't over-constrain.** Limits set too low flag legitimate work and slow
agents without improving output. Start narrow, measure, expand. ([Augment][ag])

**Acceptance criteria in EARS.** "When <trigger>, the system shall <response>"
is unambiguous to a human and a model. Use it for done-conditions. ([DEV][dev])

## Where each idea lives in this repo

| Practice | Here |
| --- | --- |
| Spec as source of truth | `docs/pollen_documentation.md` |
| Short, categorized standing rules | [`AGENTS.md`](../AGENTS.md) — critical / important / advisory |
| Decide-vs-execute split | rule engine `backend/app/services/triage.py`, [ADR 0001](adr/0001-llm-does-not-decide-safety.md) |
| Rules as errors, not warnings | `ruff` config + CI, all failures block |
| Quality gate in CI | [`.github/workflows/ci.yml`](../.github/workflows/ci.yml): ruff, format, pytest |
| Definition of done + EARS criteria | [`DEFINITION_OF_DONE.md`](DEFINITION_OF_DONE.md) |
| Decisions with rejected alternatives | [`docs/adr/`](adr/) |
| Progress + task boundaries | [`TASKS.md`](../TASKS.md), mapped to the spec's Phase 1–7 |
| Staleness mechanism | `research/` + `headache/` frontmatter (`status`, `owner`, `review-by`) |
| Verify, don't trust the agent | DoD rule: builds green on your machine before merge |

## The one-line rule for us

Ground every change in the spec, encode the standard as a check that fails loud,
and treat an agent's report as a hypothesis until the running system agrees.

[ms]: https://developer.microsoft.com/blog/spec-driven-development-ai-native-engineering/
[ps]: https://www.pluralsight.com/resources/blog/software-development/spec-driven-development-with-AI-SDD
[tf]: https://www.truefoundry.com/blog/spec-driven-development-ai-agents
[mf]: https://martinfowler.com/articles/reduce-friction-ai/encoding-team-standards.html
[cd]: https://blog.codacy.com/why-coding-agents-need-independent-quality-gates
[ag]: https://www.augmentcode.com/guides/harness-engineering-ai-coding-agents
[ax]: https://axiomstudio.ai/blog/quality-gates-for-ai-generated-code-automated-review-and-compliance
[cm]: https://camunda.com/blog/2026/01/guardrails-and-best-practices-for-agentic-orchestration/
[dev]: https://dev.to/krlz/spec-driven-development-in-2026-what-it-is-the-tooling-and-how-teams-actually-use-it-2fk2
