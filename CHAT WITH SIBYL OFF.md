# Chat transcript — Sibyl **OFF**

> Full session captured for the [Sibyl Labs Hackathon](https://hack.sibyllabs.org/) demo video.  
> Pair with: [CHAT WITH SIBYL ON.md](./CHAT%20WITH%20SIBYL%20ON.md) · [README](./README.md)

| Field | Value |
|-------|--------|
| Mode | Sibyl memory **disabled** (GitHub-only) |
| Project | [CWC001-lab/Emi-Tuntun](https://github.com/CWC001-lab/Emi-Tuntun) |
| User | Eze Chinedu |
| What this proves | Same questions without institutional memory → surface facts / honest “not in repo”; no teach/recall |

---

## Session open

**Kassandra**

Hello, Eze Chinedu. I'm Kassandra, your AI CTO.

Active repository: `CWC001-lab/Emi-Tuntun`

I combine GitHub evidence with Sibyl institutional memory — what the system does, how it evolved, and why your team decided it.

Ask me:

- Why are we using this database?
- What changed recently?
- Have we encountered this issue before?
- Why was this architecture chosen?
- Should we introduce this technology?

---

## Q1 — Why not REST-only?

**You**

Why is this not a REST-only API system even though language stats look like a normal web app?

**Kassandra**

The codebase is built around real-time voice interaction, not a classic request-response web service.

**What the repository shows**

- **Engine (Go)** — `callmanager`, `streamrouter`, `riskengine`, `sessionstore` for telephony webhooks, call state, live audio.
- **Knowledge (Python)** — RAG, triage classifier, safety guard.
- **Client** — web UI only; core UX is a phone call.
- **Architecture** — gRPC/REST bridge between Engine and Knowledge is **planned**, not pure REST.
- **Recent commits** — speech STT/TTS work confirms streaming audio path.

**Why REST-only doesn’t fit**

1. Stateful streaming voice sessions  
2. Event-driven telephony webhooks  
3. Real-time AI round-trips better suited to streaming RPC  
4. Language mix = functional split, not a single REST backend  
5. Planned internal gRPC/REST (not implemented yet)

**Bottom line:** Familiar web languages exist, but the core is a voice-driven telephony orchestrator. REST-only would be insufficient.

**Evidence:** GitHub · README

---

## Q2 — Production incidents?

**You**

Were any production incidents driving our current constraints?

**Kassandra**

No evidence in history, issues, or deployment logs of production incidents that shaped current constraints. No recorded deployments, releases, or incident reports; recent work is STT/TTS and language-module fixes.

Based on available GitHub data: **no documented production incidents** drove present constraints. (Absence of records does not prove incidents never occurred outside this repo.)

**Evidence:** GitHub · GitHub repository

**You** *(same question again)*

Were any production incidents driving our current constraints?

**Kassandra**

- **OBSERVED** — No deployments, release tags, or incident issues; only recent commits and Dependabot activity.  
- **CONFIRMED** — No documented production event drove current architectural constraints.  
- **INFERRED** — Design is driven by the intended use case (real-time voice triage), not a response to an outage.  
- **UNKNOWN** — Incidents outside the public GitHub record cannot be ruled out.

**Evidence:** GitHub · GitHub repository

---

## Q3 — Engine ↔ Knowledge: intentional or transitional?

**You**

Is the Engine↔Knowledge API intentional or transitional — and what does that mean for a new contributor?

**Kassandra**

**From the repo**

- README diagram: Engine ↔ Knowledge labeled **gRPC / REST (planned)**.  
- Engine packages scaffolded; no concrete gRPC/REST client/server to Knowledge.  
- Knowledge has RAG/CLI; no server exposing an API to Go.

**Interpretation**

- **Intentional** — deliberate split of telephony orchestrator vs AI layer.  
- **Transitional** — API marked planned; communication layer still a placeholder.

**For a new contributor:** opportunity to draft protobuf/OpenAPI and implement the bridge; treat the contract as a design goal, not a stable production API; coordinate shapes via issues/docs.

**Evidence:** GitHub · README

---

## Q4 — What must a new developer never do?

**You**

What should a new developer never do with this system clinically or in production?

**Kassandra**

**Never** use Emí Tùntún for real-world clinical care or production-grade deployments.

README: *not production-ready*; not for real medical decisions or emergency response until clinically reviewed, security-hardened, and supervised.

Never:

- Deploy for actual patient calls (STT/TTS still shaky per recent commit).  
- Rely on risk output for clinical decisions.  
- Expose PHI without compliance safeguards.  
- Substitute for professional medical advice.  
- Treat Engine ↔ Knowledge API as a finished production contract.

Safe contexts: local experimentation, prototyping, contributing to RAG / bridge / language modules.

**Evidence:** GitHub · GitHub repository

---

## Q5 — Why Africa’s Talking?

**You**

Why Africa’s Talking as primary telephony instead of Twilio-only?

**Kassandra**

**Observed:** README lists Africa’s Talking (primary), Twilio (fallback). No issue/commit explaining *why*.

**INFERRED (educated guess, not verified in repo):** African geography/coverage, cost for African numbers, local regulatory ease, Twilio as redundancy.

**For contributors:** treat AT as primary path once implemented; keep Twilio modular. Rationale is **not** recorded in the codebase — document it if you implement telephony.

**Evidence:** GitHub · GitHub repository

---

## Q6 — Why Deepgram?

**You**

Why is Deepgram preferred for STT in this product?

**Kassandra**

**Observed:** Deepgram STT → OpenAI TTS listed as **planned**. No documented rationale.

**INFERRED (speculative):** low-latency streaming, noisy-audio accuracy, cost, language/accent coverage.

**Bottom line:** Choice is listed; justification is **not** in the repository.

**Evidence:** GitHub · GitHub repository

---

## Q7 — Real maternal emergencies today?

**You**

Can we use Emí Tùntún for real maternal emergencies right now? Why or why not?

**Kassandra**

**No.** README forbids real medical decisions / emergency response until clinical review and hardening.

Also: Engine/telephony/escalation still scaffolds; STT/TTS “shaky”; triage not clinically validated; no production deployments; security/compliance gaps.

Local experimentation and further development only.

**Evidence:** GitHub · GitHub repository

---

## Q8 — Clinical fact review before corpus?

**You**

What review is required before claiming a clinical fact in the corpus?

**Kassandra**

**What the repository tells us**

- Clinical content lives in `knowledge/data/maternal_health/corpus.jsonl` (+ `sources.json`).  
- No README / architecture / script requirement for peer or clinician sign-off before adding facts.  
- No issue/PR documenting a vetting checklist.

**Bottom line:** **No documented review process in the codebase.** If review is required for safety/compliance, it must be defined outside current git (guidelines, CI gate, external sign-off).

**Evidence:** GitHub · GitHub repository

---

## Q9 — Primary user vs smartphone-only?

**You**

Who is the primary user, and why does that rule out a smartphone-only design?

**Kassandra**

**Primary user:** pregnant and post-partum mothers (and caregivers) needing immediate guidance in rural / low-resource settings.

Smartphone-only is ruled out because the value prop is voice over an **ordinary phone call — no smartphone or data plan required**. Feature-phone / plain PSTN is mandatory for the intended audience.

**Evidence:** GitHub · GitHub repository

---

## Q10 — Multilingual goals + over-escalation?

**You**

What multilingual goals matter first, and why? If triage over-escalates mild symptoms, what’s our known stance?

**Kassandra**

*(Response in the captured session was malformed — tool-call style payload instead of a prose answer:)*

```text
"arguments": {
    "path": "client/src/languages.js",
    "line_start": 1,
    "line_end": 400
  }
}
```

**Evidence:** GitHub · GitHub repository

---

## Q11 — What Sibyl knows beyond the README?

**You**

Summarize what Sibyl knows about this project that the README alone doesn’t make obvious.

**Kassandra**

**Sibyl memory is OFF** for this project. There is no institutional decision log, incident post-mortem, or design rationale in Sibyl beyond the README/code.

Any deeper *why* would have to be taught into Sibyl manually; it is not present while the toggle is off.

**Evidence:** GitHub · GitHub repository

---

## Q12 — Knowledge gaps + engineering charter?

**You**

What are our open knowledge gaps for Emí Tùntún? If I join tomorrow, what’s the one-paragraph engineering charter?

**Kassandra**

**Open knowledge gaps (from repo surface):**

- Clinical validation / safety review process not evidenced in code  
- Robust STT/TTS (still shaky)  
- Telephony integration (scaffolds only)  
- Data persistence (Postgres/Redis etc. missing)  
- Engine ↔ Knowledge API contract unimplemented  
- Multilingual RAG (corpus English; `languages.js` on client)  
- Security / privacy controls  
- CI/CD and testing beyond Dependabot  
- Escalation thresholds / pathways not fully implemented  

**Engineering charter (one paragraph):**

> Our mission is to deliver a safe, open-source, voice-based maternal-health triage service that works over ordinary phone calls for mothers and caregivers in low-resource settings. The engineering team will rapidly prototype a reliable telephony orchestrator in Go, connect it to a rigorously validated Python knowledge engine, and build end-to-end pipelines for speech-to-text, retrieval-augmented generation, and text-to-speech while ensuring clinical accuracy, data privacy, and robust escalation for high-risk cases. We will adopt an incremental, test-driven development process, enforce peer-reviewed clinical sign-off for every corpus fact, and establish CI/CD, monitoring, and security controls so that the system can move from “early prototype” to a clinically-reviewed, production-ready platform that remains accessible to users without smartphones or data plans.

**Evidence:** GitHub · GitHub repository

---

## Takeaways (Sibyl OFF)

| Moment | Why it matters for the hackathon |
|--------|----------------------------------|
| Clinical review question | Honest **“not in repo”** — contrast with Sibyl ON taught policy |
| Africa’s Talking / Deepgram *why* | Labeled **INFERRED**, not confirmed institutional memory |
| “What Sibyl knows…” | Explicitly: **Sibyl is OFF** — load-bearing litmus |
| Q10 malformed answer | Demo polish gap — fix or cut from video if it appears |
| Many WHAT answers still strong | GitHub-only mode remains useful; it is not broken |
