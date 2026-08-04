# Process & Artifacts — What This Project Still Needs

Author: Ismoiljon (Tech Lead / Repo Owner / Slice C)
Reviewed: `HaksengUz_Pollen_Project_Kickoff.pptx`, one design page (`Pollen Today`)

The kickoff deck is a good *motivation* document. It is not a *specification*.
It tells us why the product should exist, who owns which slice, and how we are
graded. It does not tell anyone what to build on Monday morning. This document
lists the artifacts a normal team produces between "here is the idea" and
"here is the code", says who owns each one, and marks which are missing.

---

## 0. What the deck already covers — credit where due

Do not re-request these. They exist and they are good:

| Artifact | Where | Quality |
|---|---|---|
| Problem statement / "why" | Slides 2, 4 | Strong. Slide 4 is a usable product north star. |
| Non-goals / explicit scope cuts | Slide 15 | Unusually good. Most student projects never write this. |
| Roles & ownership | Slides 5–8 | Clear. Vertical slices, no cross-blocking. |
| Release plan & milestones | Slides 9–12 | Three milestones with pass/fail gates. |
| Team working agreement | Slide 13 | Cadence, commit/PR/review targets, blocker SLA. |
| Named primary risk | Slide 14 | The majority-class trap. Correctly identified. |

So roughly half a PRD and most of a team charter already exist. What is missing
is everything between the vision and the keyboard.

---

## 1. The standard artifact chain

The industry-normal flow, in dependency order. Each row says who owns it here.

| # | Artifact | Purpose | Owner | Status |
|---|---|---|---|---|
| 1 | **PRD** (product requirements) | What we build and why. Users, goals, non-goals, success metrics. Deliberately avoids *how*. | Mentor | ~50% — deck slides 2, 4, 15 |
| 2 | **User stories + acceptance criteria** | Per feature: "As a … I want … so that …", plus the specific conditions that make it done. | Mentor drafts, team refines | **Missing** |
| 3 | **Non-functional requirements** | Latency, uptime, retention, timezone, language, accessibility, data licensing. | Mentor | **Missing** |
| 4 | **Wireframes** | Low-fidelity layout and flow. Cheap to argue about. | Mentor / designer | **Missing** (1 of ~8 screens) |
| 5 | **Figma + design tokens** | High fidelity, all states, tokens, dev mode. | Mentor / designer | **Missing** |
| 6 | **Domain model → ERD → data dictionary** | Entities, relationships, types, constraints, indexes. | **Me** | Mine to write — blocked on §3 |
| 7 | **API contract** (OpenAPI / Zod schemas) | The frozen interface all three slices build against. | Jamshid drafts, I own the shared package | Due end of Week 1 |
| 8 | **Architecture doc + ADRs** | System shape, and a written record of each significant decision and its trade-off. | **Me** | Mine to write |
| 9 | **Definition of Done** | One checklist applying to *every* task, distinct from per-story acceptance criteria. | **Me**, team agrees | **Missing** |
| 10 | **Test plan & test data** | What we test, how, and with which fixtures. | Each slice owner | **Missing** |
| 11 | **Runbook / release & rollback plan** | How to deploy, how to roll back, what to do when the 07:00 job fails on a Saturday. | Giyos (Release Owner) + me | **Missing** |
| 12 | **MODEL_CARD.md / PRIVACY.md** | Model behaviour and limits; data handling. | Jamshid / me | Named in deck, not yet written |

Sources for this chain are listed at the bottom.

---

## 2. Correcting my own earlier assumption

I originally had the ER model on the list of things to request. That is wrong.

**The schema is my deliverable, not the mentor's.** I am the fullstack — I decide
where data lives and how it is delivered. Asking for a schema means building
against someone else's guess at my own domain. What I need from the mentor is not
the ERD; it is the **inputs** the ERD is derived from:

- the actual KMA payload shape (§3 below),
- the canonical region list,
- retention and history requirements,
- the user stories that tell me which queries have to be fast.

Given those, I write the ERD and data dictionary, and the mentor reviews it.
That is the correct direction of that conversation.

Note the ordering consequence: **the ERD cannot come after Figma.** It is derived
from the data source and the domain, and it is blocked by §3, not by design.
Design and schema proceed in parallel.

---

## 3. What to actually ask the mentor for — prioritised

### Tier 1 — blocking, need this week

1. **data.go.kr API key** — named owner, and is the application actually submitted?
   Nothing starts without it (deck slide 16 says this itself).
2. **One real sample response** from the pollen endpoint. Not documentation — an
   actual JSON/XML body. Field names, types, region encoding, how the four risk
   levels are represented. Without this I cannot write the schema, and without the
   schema there is no frozen contract at end of Week 1.
3. **Canonical region list** — exact codes and names, frozen. Every slice keys off
   it: forecasts, charts, Telegram channels. If it changes in Week 3, all three
   slices break at once.

### Tier 2 — need before Week 2 deploy

4. **User stories with acceptance criteria**, at least for the four core screens.
   Deck slide 10 calls milestones "binary, pass or fail" — that is only true if
   somebody wrote down the conditions.
5. **Wireframes for the remaining screens.** We have `Pollen Today`. Still missing:
   3-day forecast card, analytics dashboard (3 charts), subscribe page, alert
   history, region picker, and the empty/loading/error/off-season states. Empty and
   error states are the ones teams forget and then argue about in Week 5.
6. **Design tokens — specifically the four KMA risk colours.** Fixed by KMA, or
   ours to pick? One token set must serve the forecast card, the charts, and the
   Telegram message.
7. **Language decision: Korean, English, or both.** This decides i18n now or never,
   and it decides the actual wording of every alert we send. Not cheap to defer.

### Tier 3 — needed, but can land by Week 3

8. **Non-functional requirements** — page load target, uptime expectation, how many
   years of history we retain, timezone handling (everything is KST; say so once,
   in writing).
9. **Data licensing / attribution terms.** We are republishing Korean government
   data to public Telegram channels under the HaksengUz name. What does data.go.kr
   require — attribution string, redistribution limits? This is a legal question,
   not a technical one, and it is the mentor's to answer before M3's "at least one
   real alert delivered to a live channel."
10. **Approved Telegram message template.** Slide 15 forbids medical advice. The
    exact wording that goes to a real channel should be reviewed by him, not
    invented by me.
11. **Numeric pass thresholds for M2.** "Beats the persistence baseline" is not
    binary until there is a number attached.

---

## 4. What I produce, and when

Not blocked on any answer. Starting now:

| Artifact | By |
|---|---|
| Repo, branch protection, required reviews, CI skeleton | Week 0 |
| Definition of Done — one checklist, team-agreed | Week 0 |
| Architecture doc + first ADRs (stack, batch-not-service, monorepo) | Week 0 |
| Draft Zod contract shapes, so Jamshid reacts to something concrete | Week 0–1 |
| Region enum scaffolded, placeholder until Tier-1 item 3 lands | Week 0 |
| ERD + data dictionary | Week 1, once Tier-1 item 2 lands |
| `PRIVACY.md` first draft | Week 0 — trivial given slide 15 |
| Runbook + rollback, with Giyos | Week 2 |

---

## 5. How to frame the ask

Not "the deck is not enough." Rather: the deck did its job, and the next
artifacts are the ones that let three people work in parallel without colliding.
Concretely — a sample API response, a frozen region list, and acceptance criteria
are what turn slide 10's pass/fail gates into something actually checkable.

The Tier-1 items are three concrete things, and two of them are a copy-paste.

---

## Sources

- [SDLC documentation guide — Leanware](https://leanware.co/insights/sdlc-documentation-guide)
- [SDLC artifacts across the lifecycle — Medium](https://medium.com/@wasowski.jarek/the-agile-manifesto-lies-about-documentation-sdlc-artifacts-2807bd4b6ad4)
- [PRD vs SRS checklist — Practical Logix](https://www.practicallogix.com/prd-vs-srs-7-step-checklist-for-choosing-the-right-document-for-your-project/)
- [What is a PRD — Atlassian](https://www.atlassian.com/agile/product-management/requirements)
- [Software requirements document template — Asana](https://asana.com/resources/software-requirement-document-template)
- [Guide to developer handoff — Figma](https://www.figma.com/best-practices/guide-to-developer-handoff/)
- [Developer handoff checklist — Figma Community](https://www.figma.com/community/widget/1323260930163364205/developer-handoff-checklist)
- [Data model vs data dictionary vs schema vs ERD — Dataedo](https://dataedo.com/blog/data-model-data-dictionary-database-schema-erd)
- [Definition of Done vs acceptance criteria — Altexsoft](https://www.altexsoft.com/blog/acceptance-criteria-definition-of-done/)
- [Definition of Done checklist examples — Plane](https://plane.so/blog/definition-of-done-dod-checklist-examples-for-agile-teams)
- [What is a RACI matrix — Rework](https://resources.rework.com/libraries/project-management/what-is-raci-matrix)
