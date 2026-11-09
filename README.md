# Lder

Daily voice check-ins for elderly parents, built for families who live far from them.

Every day Lder asks an elderly person one simple question in their own language, listens to the spoken answer, works out whether they are fine, unwell or in trouble, and tells the family. If the person does not answer, or says something alarming, Lder escalates through the family's contact list until someone acknowledges the alert.

It was built for families in Kerala, so Malayalam came first. Tamil, Telugu, Hindi and Kannada are supported as well.

## What the family sees

- A dashboard with each person's recent check-ins, mood, medicine adherence, missed check-ins and open alerts.
- Alerts by email or WhatsApp when a reply sounds like an emergency, when a check-in is missed, when the medicine was not taken, or when several low days in a row suggest a pattern.
- A plain-English weekly summary written by a language model from the week's statistics.
- An "Ask about your parent" box. The family types a question such as "Has any medicine been missed?" and gets an answer drawn from the real check-in records.
- For every check-in: which AI model answered, whether a fallback model was used, and what the call cost.

## What the elderly person sees

One big button. They press it, hear the question in their own language, press again, speak, and are done. No app to install and no account. It works from a link, and through WhatsApp voice notes for people who already use WhatsApp.

## How a check-in works

1. A schedule creates a check-in at the person's local time (for example 08:30 and 19:00).
2. The question is sent as text and, where an audio file exists, as audio. If the person does not answer, Lder asks again after 15 and 30 minutes, then marks the check-in as missed.
3. The spoken reply is turned into text by Whisper.
4. Two things analyse the text at the same time:
   - A keyword layer that knows emergency, concern and mild-symptom words in all five languages, with negation handling ("no chest pain" is not an emergency, "I fell and cannot get up" is).
   - A language model that returns a structured judgement: status, medicine taken, distress, mood, confidence and a short summary for the family.
5. The two are combined. The model can raise the level of concern but can never lower an emergency that the keyword layer found.
6. Emergencies alert every contact at once. Warnings alert the first contact. A missed check-in escalates one contact at a time until someone acknowledges.

## How Otari is used

All language-model traffic goes through the Otari gateway, which is OpenAI-compatible. Each of the features below is actually called by the application.

| Otari feature | Where it is used | Where in the code |
| --- | --- | --- |
| Routing and fallbacks | Three named policies, `lder-classifier`, `lder-summary` and `lder-assistant`, each with a main open-weight model and a backup on another provider. The app also keeps its own retry and fallback chain, and records which model answered and whether a fallback was used. | `worker/src/otari.js`, `worker/src/classifier.js` |
| MCP | The family Q&A sends an inline MCP server entry. Otari runs the tool loop against Lder's own MCP endpoint, which exposes four read-only tools: profile, recent check-ins, summary and alerts. | `worker/src/assistant.js`, `worker/src/mcp.js` |
| Multiple models in distinct roles | Classifier (fast, strict JSON), weekly narrator (warm prose), family assistant (tool use) and Whisper for speech to text. | `classifier.js`, `narrator.js`, `assistant.js`, `stt.js` |
| Guardrails | An organisation-level guardrail in Otari points at Lder's own guardrail service (`/api/guardrail`), so no third-party key is needed. Questions to the assistant are also screened in code. | `worker/src/guardrails.js`, `worker/src/routes.js` |
| Budgets and per-user budgets | Every call carries the `user` field `lder-elder-<id>`, so each elderly person has their own budget. Budget and guardrail rejections are caught, stored on the check-in and shown on the dashboard. A project spend cap is set in the Otari dashboard. | `worker/src/otari.js`, `worker/src/checkins.js` |

Not used: web search and fetch, and code execution.

Models are chosen in the Otari dashboard, not in code, so they can be changed without a deploy. The app asks for the policy names above.

## Safety design

This is a check-in aid, not an emergency service, and the app says so in every alert.

- The keyword emergency layer does not depend on Otari. If the gateway is down, over budget or blocking requests, the keyword decision still alerts the family.
- Transcripts are given to the model as untrusted data, and the prompt says to ignore any instruction found inside them.
- Replies from the elderly person are never blocked by a guardrail, so an emergency cannot be dropped. They are only recorded.
- The family assistant refuses prompt-injection attempts, removes phone, email, Aadhaar, PAN and card numbers from questions before they reach the model, and never gives medical advice.
- The MCP endpoint accepts only short-lived tokens scoped to one person, and its tools take no person identifier, so one person's data cannot be read through another's session, even under prompt injection. These tokens are rejected by the dashboard API.
- Check-ins only start after the family records the person's consent. The person can reply STOP on WhatsApp, or use the opt-out on their page, to stop all check-ins.
- Transcripts, summaries and alert text are encrypted at rest with AES-GCM.