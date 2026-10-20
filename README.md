# Lder

A daily voice check-in for elderly parents, in their own language.

Lder asks an older person how they are, every day, as a short spoken question in Malayalam. They answer by voice. Lder transcribes the reply, understands it, keeps a record, and quietly alerts family when something sounds wrong or when nobody answers. Family can be anywhere in the world and see everything in their own time zone.

It is built for the many families in Keralam where parents live alone or with a spouse while the children work in the Gulf or in other cities. It is a check-in aid, not a medical device and not an emergency service.

## Contents

1. [The problem](#the-problem)
2. [What Lder does](#what-lder-does)
3. [How it works](#how-it-works)
4. [Technology and cost](#technology-and-cost)
5. [Run it on your computer](#run-it-on-your-computer)
6. [Deploy it for free (Render, Vercel, Supabase)](#deploy-it-for-free)
7. [Deploy it all on Render instead](#option-b-both-services-on-render)
8. [What the free tiers mean in practice](#what-the-free-tiers-mean-in-practice)
9. [Configuration reference](#configuration-reference)
10. [WhatsApp and email](#whatsapp-and-email)
11. [Demo script](#demo-script)
12. [Evaluation](#evaluation)
13. [Tests](#tests)
14. [Privacy and responsible design](#privacy-and-responsible-design)
15. [API overview](#api-overview)
16. [Troubleshooting](#troubleshooting)
17. [Limitations](#limitations)
18. [Project layout](#project-layout)
19. [Sources to cite](#sources-to-cite)

## The problem

Keralamm has the highest share of older people among Indian states, and many of them live alone or with a spouse while their children are abroad or in other cities. Families rely on irregular phone calls. A missed medicine, a fall or a quiet few days can go unnoticed until it is serious. A smartphone app is hard for an elderly person to learn, and reading and typing in English is not an option for many of them.

Lder asks the one thing a worried child would ask, in the language they would use, and it does not need the parent to learn anything new.

## What Lder does

- **Scheduled check-ins** at times you choose for each person, in that person's own time zone.
- **A spoken Malayalam question**, delivered through WhatsApp or through a web page that works in any browser, with one large button to answer.
- **Malayalam speech to text**, then structured understanding of the reply: doing well, unwell, needs help, confused or unclear, plus whether medicine was taken and the person's mood.
- **An emergency safety layer.** A deterministic Malayalam, Manglish and English keyword check runs beside the language model, so an alert for a fall, chest pain, trouble breathing, bleeding, fainting or a call for help never depends on the model alone. Negations such as "വേദനയില്ല" (no pain) are understood.
- **Retries and escalation.** If there is no reply, the person is asked again after 15 and then 30 minutes. After that the check-in is marked missed and family are alerted in priority order until someone acknowledges.
- **A family dashboard** with a timeline, medicine adherence, response rate, progress rings, a two-week chart and open alerts, with every time shown in the time zone you pick.
- **Pattern alerts** after three low or unwell check-ins in a row, a weekly email summary, and a late-reply update when a missed check-in is finally answered.
- **Consent and control.** Check-ins start only after consent is recorded. The person can stop by replying STOP or with the Stop check-ins link on their page. Transcripts are encrypted at rest, and one click deletes a person and all of their data.

## How It Works

A decision is made per reply:

| Situation | Result |
|---|---|
| Emergency words, or the model flags distress | Urgent alert to every contact |
| Unwell, confused, unclear, or medicine not taken | Follow-up alert to the first contact |
| Fine, medicine taken | No alert, logged on the timeline |
| No reply after the retries | Marked missed, alerts walk down the contact list until acknowledged |
| Model unavailable | The keyword layer still raises emergencies; everything else is flagged for a human call |
| Low-confidence or unintelligible reply | Never treated as fine; flagged for a follow-up call |

## API overview

All routes are under `/api`. Dashboard routes need a bearer token from `POST /auth/login`.

| Route | Purpose |
|---|---|
| `POST /auth/login` | Exchange the password for a session token |
| `GET, POST /elders`, `GET, PUT, DELETE /elders/{id}` | Manage people, contacts and medicines |
| `GET /elders/{id}/checkins`, `GET /elders/{id}/summary` | Timeline and statistics |
| `POST /elders/{id}/trigger-checkin` | Start a check-in, or record a missed one |
| `GET /alerts`, `POST /alerts/{id}/acknowledge` | Alerts |
| `GET /simulator/{token}`, `POST .../start`, `.../reply`, `.../opt-out` | The elder's page, no login |
| `GET, POST /webhook/whatsapp` | WhatsApp verification and incoming messages |
| `GET /internal/tick?key=...` | One scheduler pass, for the cron job |
| `GET /health` | Health check |