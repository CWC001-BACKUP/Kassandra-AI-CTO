# Chat transcript — Sibyl **ON**

> Full session captured for the [Sibyl Labs Hackathon](https://hack.sibyllabs.org/) demo video.  
> Pair with: [CHAT WITH SIBYL OFF.md](./CHAT%20WITH%20SIBYL%20OFF.md) · [README](./README.md)

| Field | Value |
|-------|--------|
| Mode | Sibyl memory **enabled** |
| Project | [CWC001-lab/Emi-Tuntun](https://github.com/CWC001-lab/Emi-Tuntun) |
| User | Eze Chinedu |
| What this proves | Teach → confirm → recall of institutional *why* that GitHub alone does not hold |

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

Why the system is not a “REST-only” API, even though the language mix (Python + Go + JS + HTML + CSS) looks like a typical web-app stack

**OBSERVED facts from the repository**

- **Architecture definition** — `architecture.json` lists Go for telephony/streaming and Python for AI/RAG, with planned protocols: gRPC, REST, WebSockets, NATS.
- **Engine code** — `engine/internal/api/handler.go` has a few HTTP routes (`/health`, `/api/sessions`, `/api/chat`), but also scaffolded packages that are not HTTP-only: `callmanager`, `streamrouter`, `riskengine`, `notification`.
- **Speech pipeline** — `client/src/speech.js` sends audio blobs and receives synthesized audio — binary/streaming interaction, not classic REST JSON.
- **Planned protocols** — gRPC / WebSockets / NATS for Engine ↔ Knowledge.
- **Domain focus** — Voice-first maternal-health triage over ordinary phone calls (PSTN), not a browser-first product.
- **Client UI is ancillary** — Vite chat UI is a developer convenience; production path is telephony webhooks.

**INFERENCE**

The core product is real-time voice triage, so the Engine must handle continuous audio, telephony callbacks, and async alerts. A small HTTP surface exists, but the overall architecture is multimodal — not “REST-only.” The language mix reflects Go (telephony/streaming) + Python (AI), not a conventional web app.

**Evidence:** GitHub · README

---

## Q2 — Production incidents? *(triggers teach / confirm)*

**You**

Were any production incidents driving our current constraints?

**Kassandra**

You still have pending institutional memories waiting for confirmation.

This sounds like useful institutional context.

I extracted **13** potential memories:

1. **Not a medical device** — early open build; not for real emergencies until clinical review and security hardening.
2. **Primary access = PSTN / feature-phone voice** — web/mobile client is secondary.
3. **Target users** — pregnant/postpartum people in low-access settings.
4. **Africa-first telephony** — Africa’s Talking primary; Yoruba and other African languages; STT for accents/noisy calls.
5. **Clinical safety over feature speed** — WHO/CDC/NHS/Mayo RAG; LOW–CRITICAL risk; safety_guard; over-escalation still tuning.
6. **Regulatory** — local clinical governance, health-data protection, HIPAA-style readiness (not certification).
7. **Split-brain** — Go = call lifecycle/streaming; Python = RAG/LLM/triage.
8. **Planned stack** — gRPC, REST, WebSockets, NATS, Postgres + pgvector, Redis.
9. **Secrets policy** — never commit `.env`; rotate if leaked; no patient data in git.
10. **Branch of record** — `dev`.
11. **License + clinical claim review** — Apache-2.0; clinical claims need qualified review before trusted corpus.
12. **No production incidents to date** — service not in production.
13. **Scaffolding debt** — empty Engine packages / missing Engine↔Knowledge API are intentional, not abandoned design.

Would you like me to save these to Sibyl?  
Reply `yes` to save all, `no` to discard, or e.g. `save 1 and 3`.

**Evidence:** Sibyl (pending institutional context blob)

**You**

yes

**Kassandra**

Saved **13** institutional memories to Sibyl:

- Emí Tùntún is not a medical device and not for real emergencies until review
- Primary access path is PSTN/feature-phone voice
- Target users are pregnant/postpartum people in low-access settings
- Africa-first telephony with Africa's Talking and African language support
- Clinical safety prioritized over feature speed
- Regulatory compliance requires local clinical governance and HIPAA-style readiness
- Split-brain architecture: Go for call lifecycle, Python for RAG/LLM
- Planned communication and data stack
- Secrets handling policy
- Branch of record for current work is `dev`
- Apache-2.0 license and clinical claim review process
- No production incidents to date
- Empty Engine packages and missing Engine↔Knowledge API are scaffolding debt

Note: may conflict with existing institutional memory on regulatory / HIPAA-style readiness.

**Evidence:** Sibyl

---

## Q3 — Why Go + Python?

**You**

What business or customer constraints explain the Go + Python split?

**Kassandra**

Business- and customer-driven reasons for the Go + Python split:

- **Voice-first, PSTN product** — ordinary phone calls in low-resource African settings → telephony engine for call setup, audio streaming, session state, escalation.
- **High-performance streaming** — Go for concurrency / low-overhead networking (institutional memory: “split-brain architecture”).
- **AI / RAG** — Python Knowledge layer for LLM, vector search, safety guard (observed in `knowledge/`).
- **Regulatory / safety** — separate safety-critical telephony path (Go) from AI decision path (Python).
- **Multilingual** — Yoruba, Hausa, Swahili; Go streams audio; Python reasons on transcript.
- **Future polyglot stack** — gRPC, WebSockets, NATS planned.

**Bottom line:** Real-time voice maternal-health triage on basic phones → Go for telephony/streaming, Python for AI/ML/safety.

**Evidence:** GitHub · GitHub repository

---

## Q4 — Engine ↔ Knowledge: intentional or transitional?

*(Session hit a teach-loop on a vague candidate memory. Re-asks and yes/no shown below for fidelity to the video.)*

**You**

Is the Engine↔Knowledge API intentional or transitional — and what does that mean for a new contributor?

**Kassandra** *(teach prompt)*

Extracted 1 potential memory: “Developer-confirmed knowledge.” Save? → **You:** `yes` → Saved.

**You** *(re-ask)*

Is the Engine↔Knowledge API intentional or transitional — and what does that mean for a new contributor?

**Kassandra** *(teach prompt again)*

Similar knowledge may already exist. Save? → **You:** `yes, its intentional and transitional and new contributors should be careful` → Kassandra: already exists; no duplicate.

**You** *(re-ask)*

…same question…

**Kassandra** *(teach prompt)* → **You:** `no` → Discarded.

**You** *(re-ask)*

…same question…

**Kassandra** *(teach prompt)* → **You:** `yes` → Already exists; no duplicate.

*(Further re-ask still surfaced the teach prompt before later questions moved on.)*

---

## Q5 — What must a new developer never do?

**You**

What should a new developer never do with this system clinically or in production?

**Kassandra**

Never treat this code as a finished, production-ready medical product.

From README / status:

- Not for real medical decisions or emergency response until clinically reviewed, security-hardened, and supervised.
- Engine ↔ Knowledge API is a development-stage contract, not live patient-facing.
- Speech and telephony still incomplete / shaky.

A new developer should **never**:

1. Deploy to production / real callers.
2. Rely on answers for clinical care.
3. Expose the API as a medical-device substitute without validation and clearance.
4. Commit or share real API keys, credentials, or patient data.

Treat as research/experimental scaffolding only.

**Evidence:** GitHub · GitHub repository

---

## Q6 — Why Africa’s Talking?

**You**

Why Africa’s Talking as primary telephony instead of Twilio-only?

**Kassandra**

Africa’s Talking is primary because the system is built for African users calling from ordinary feature phones over local PSTN — local coverage, cost, regulatory fit, and acoustic environment. Twilio remains a fallback if the primary carrier has an outage.

**Evidence:** GitHub · GitHub repository

---

## Q7 — Why Deepgram?

**You**

Why is Deepgram preferred for STT in this product?

**Kassandra**

Summarised reasons:

1. Noise-robust telephony audio  
2. African-accent support  
3. Low-latency, streaming-friendly API  
4. Easy cloud integration (`DEEPGRAM_API_KEY`)  
5. Fallback strategy with local Whisper when configured  

Chosen for noisy, African-accent phone audio while the rest of the stack is still being built.

**Evidence:** GitHub · GitHub repository

---

## Q8 — Real maternal emergencies today?

**You**

Can we use Emí Tùntún for real maternal emergencies right now? Why or why not?

**Kassandra**

**No.** Not ready for live, life-saving use.

Would need: clinical validation, regulatory clearance, full telephony, robust STT/TTS, security hardening, operational monitoring and escalation to humans.

Until then: sandbox / development only — not a substitute for emergency services.

**Evidence:** GitHub · GitHub repository

---

## Q9 — Clinical fact review before corpus?

**You**

What review is required before claiming a clinical fact in the corpus?

**Kassandra**

Institutional memory: any clinical claim used by the Knowledge layer must undergo **qualified clinical review** before merge into the trusted RAG corpus.

In practice:

- Qualified reviewer (maternal-health clinician)
- Source verification (WHO, CDC, NHS, Mayo, etc. in `sources.json`)
- Safety guard-rail check
- Merge approval only after sign-off

Until reviewed: keep in draft / unreviewed — do not merge into production-ready corpus.

**Evidence:** GitHub · GitHub repository

---

## Q10 — Primary user vs smartphone-only?

**You**

Who is the primary user, and why does that rule out a smartphone-only design?

**Kassandra**

**Primary user:** pregnant or postpartum people in low-resource African settings with feature-phone lines and unreliable data.

Smartphone-only would exclude the audience the product exists for. Design centers on PSTN / feature-phone voice (Africa’s Talking); web client is a development convenience.

**Evidence:** GitHub · GitHub repository

---

## Q11 — Multilingual goals + over-escalation stance?

**You**

What multilingual goals matter first, and why? If triage over-escalates mild symptoms, what’s our known stance?

**Kassandra**

**Multilingual priorities:** Yoruba, Hausa, and Swahili first — common among the target user base; voice prompts must be understood without a written UI.

**Over-escalation stance:** Err on the side of safety. Prefer over-escalating mild symptoms over under-escalating serious ones; never provide a definitive medical diagnosis.

**Evidence:** GitHub · GitHub repository

---

## Q12 — What Sibyl knows beyond the README?

**You**

Summarize what Sibyl knows about this project that the README alone doesn’t make obvious.

**Kassandra**

Sibyl fills in behind-the-scenes decisions: clinical-review workflow, multilingual priorities, safety-first escalation policy, dual-language architecture rationale, provisional Engine↔Knowledge API, and explicit lack of production deployment / incident history — shaping how to contribute and move toward production.

**Evidence:** GitHub · GitHub repository

---

## Q13 — Knowledge gaps + engineering charter?

**You**

What are our open knowledge gaps for Emí Tùntún? If I join tomorrow, what’s the one-paragraph engineering charter?

**Kassandra**

**Open knowledge gaps (as recorded in Sibyl):**

1. **API architecture intent** — final vs transitional Engine ↔ Knowledge contract and migration path.
2. **Production-incident history** — none recorded; gap in reliability lessons.
3. **Finer business constraints** — SLAs, regional telecom rules, funding, partner quotas beyond high-level voice-first / multilingual / safety-first.

**Engineering charter (one paragraph):**

> Build a production-ready, voice-first maternal-health triage platform that safely guides pregnant and postpartum callers in low-resource African settings. The Go-based Engine will manage PSTN telephony (Africa’s Talking primary, Twilio fallback), stream audio, maintain per-caller session state, and enforce hard-coded emergency-symptom detection. It will communicate with the Python Knowledge service via the planned gRPC/REST + WebSocket API to retrieve RAG-augmented medical context, run the confidence engine, and generate calm, multilingual (Yoruba, Hausa, Swahili) responses through a vetted STT/TTS stack (Deepgram + OpenAI or local Whisper/Piper). All clinical facts must pass a qualified clinician review before entering the trusted corpus, and every interaction must be auditable to meet HIPAA-style privacy and regulatory requirements. The team will iteratively close the documented knowledge gaps—finalizing the API contract, establishing an incident-postmortem process, and codifying any additional business constraints—while delivering robust, test-driven code, CI pipelines, and clear hand-off procedures to human health workers for any CRITICAL escalation.

**Evidence:** GitHub · GitHub repository

---

## Takeaways (Sibyl ON)

| Moment | Why it matters for the hackathon |
|--------|----------------------------------|
| Teach → `yes` → 13 memories saved | Persist + human confirmation gate |
| Go+Python / clinical review / charter answers | Recall of taught institutional *why* |
| Q4 teach loop | Known UX rough edge — vague candidate (“Developer-confirmed knowledge”) |
| Many chips still labeled GitHub | Provenance can be clearer when Sibyl drove the *why* |
