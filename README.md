# Predoc Partner API — Bruno collection

A [Bruno](https://www.usebruno.com/) collection for the [Predoc Partner API](https://docs.predoc.ai/).

- Every endpoint from the Predoc Postman collection, with its docs and example responses.
- Ready-to-run demo flows that use the sandbox test patients.
- A local mock server, to demo the full flow without credentials or waiting on Predoc.

## Structure

```
predoc-api/
├── collection.bru         # bearer auth + automatic token refresh
├── environments/
│   ├── sandbox.bru        # https://partner-api-stage.predoc.ai/api
│   └── local-mock.bru     # http://localhost:4010/api
├── demo/                  # end-to-end flows, run in order
│   ├── 1 Webhooks/
│   ├── 2 HIE request (Calvin Hills)/
│   ├── 3 Medications request (Juniper Williston)/
│   ├── 4 Previous-provider retrieval (Harriet Dare)/
│   └── 5 Anonymous fax upload/
├── sandbox-test-patients/ # one click = one test patient + HIE or medications request
├── v2/                    # current endpoints
├── v1/                    # endpoints with no v2 equivalent
│   └── legacy/            # superseded by v2, kept for reference
├── fixtures/
│   ├── sandbox-test-patients.json  # Predoc test patients, verbatim from the docs
│   └── sample-record.pdf           # synthetic record, no PHI
├── mock-server/           # local fake Predoc API
├── .env.sample
└── package.json
```

## Setup

1. Install dependencies:

   ```bash
   pnpm install
   ```

2. Create your `.env`:

   ```bash
   cp .env.sample .env
   ```

3. Fill in `.env`:

   | Variable | What |
   |---|---|
   | `PREDOC_CLIENT_ID` | Partner client id, from Predoc |
   | `PREDOC_SECRET_KEY` | Partner secret key, from Predoc |
   | `PREDOC_REQUESTING_PROVIDER_EMAIL` | Sent as `requestingProviderEmail` and webhook `notificationEmail` |
   | `PREDOC_WEBHOOK_URI` | Public URL receiving webhooks, e.g. a [webhook.site](https://webhook.site) URL |
   | `PREDOC_WEBHOOK_SECRET` | Sent in the `X-Partner-Auth` webhook header |

`.env` is git-ignored. Never commit credentials.

## Use it in the Bruno app

1. Install Bruno: `brew install bruno`.
2. **Open Collection** → select this folder.
3. Pick an environment in the top-right: `sandbox` or `local-mock`.
4. Send any request.

Things to know:

- **No manual login.** Tokens last 5 minutes. `collection.bru` fetches a new one before any request when needed.
- **IDs chain automatically.** Create requests store `patientId`, `requestId`, `retrievalId`, `recordUploadId` and `configurationId` as runtime variables. The next requests use them.
- **Docs live in each request.** Open the **Docs** tab for the field descriptions and an example response.
- **Run a whole flow.** Right-click a `demo/` folder → **Run**.

## Use it with the VS Code extension

The official [Bruno extension](https://marketplace.visualstudio.com/items?itemName=bruno-api-client.bruno) (`bruno-api-client.bruno`) sends requests without leaving VS Code.

1. Open this folder in VS Code: `code ~/CODE/predoc-api`.
2. Accept the **Install** prompt for the recommended extension. Or search "Bruno" in the Extensions panel.
3. Click the **Bruno** icon in the activity bar. The extension finds the collection in the folder.
4. Click **No Environment** → pick `sandbox` or `local-mock`.
5. Open a request and send it.

Things to know:

- **Two views.** **GUI mode** comes from the Bruno icon. **File mode** is the plain `.bru` text from the Explorer. Switch with the arrow icons, top-right.
- **Safe Mode should be enough.** The token refresh and ID chaining pass in the CLI's Safe Mode sandbox. If a script fails in the extension, switch to **Developer Mode** with the sandbox icon.
- **Desktop global environments aren't visible.** The extension can't see them, but this collection doesn't use any.
- **To run a whole flow,** use the CLI in the VS Code terminal, e.g. `pnpm demo:sandbox`. The extension docs don't describe a folder runner.

Docs: [overview](https://docs.usebruno.com/vs-code-extension/overview) · [install](https://docs.usebruno.com/vs-code-extension/install-config) · [send a request](https://docs.usebruno.com/v2/vs-code-extension/send-req)

## Use it from the CLI

| Command | What |
|---|---|
| `pnpm demo:sandbox` | Run all demo flows against the Predoc sandbox |
| `pnpm token:sandbox` | Check your credentials |
| `pnpm mock` | Start the local mock on port 4010 |
| `pnpm demo:local` | Run all demo flows against the local mock |

Run a single flow or request:

```bash
pnpm exec bru run "demo/2 HIE request (Calvin Hills)" --env sandbox
pnpm exec bru run "v1/patients/Get Patient Medications.bru" --env sandbox
```

> Runtime variables don't survive between CLI runs. Run a request on its own and `{{patientId}}` is empty. Run its folder instead, or pass `--env-var patientId=<id>`.

## Demo flows

| Flow | Patient | What it shows | Sandbox data |
|---|---|---|---|
| 1 Webhooks | — | Subscribes to `REQUEST_COMPLETE`. Skipped if the subscription already exists. | — |
| 2 HIE request | Calvin Hills | HIE request → request status → HIE documents → documents → curated allergies | ✅ |
| 3 Medications request | Juniper Williston | Medications request → request status → medications | ✅ |
| 4 Previous-provider retrieval | Harriet Dare | Retrieval on a fake provider → status → close (skipped until `canClose` is `true`) | ❌ mock only |
| 5 Anonymous fax upload | — | Uploads `fixtures/sample-record.pdf` → processing status | ❌ mock only |

- Results are asynchronous. Re-run the status requests until they reach a terminal state.
- ❌ The Predoc test patients only cover HIE and medications. Flows 4 and 5 will likely stall in the sandbox. Demo them on the local mock.

## Sandbox test patients

Only these patients return data in the sandbox. Send their demographics exactly as Predoc lists them.

- Source: https://docs.predoc.ai/reference/sandbox-test-patients
- Verbatim copy: `fixtures/sandbox-test-patients.json`
- One request per patient: the `sandbox-test-patients/` folder

To demo any patient in the Bruno app:

1. Open `sandbox-test-patients/` and send the patient's request. It stores `patientId`.
2. Send `v1/patients/Patient Requests` until the request is `COMPLETED`.
3. Send `v1/patients/Get Patient HIE documents` (HIE patients) or `v1/patients/Get Patient Medications` (Juniper).

| Patient | DOB | Postal code | Use for |
|---|---|---|---|
| Calvin Hills | 1989-08-16 | 53714 | HIE |
| Horacio Samaniego | 1936-03-31 | 53792 | HIE |
| Tammy Torp | 2000-04-14 | 53593 | HIE |
| Hugo Kilback | 1947-06-17 | 53707 | HIE |
| Óscar Rendón | 1936-03-31 | 53715 | HIE |
| Kelli Fritsch | 2007-01-01 | 53703 | HIE |
| Freddie Corkery | 1971-03-08 | 53703 | HIE |
| Harriet Dare | 1957-05-20 | 53715 | HIE |
| Juniper Williston | 2016-02-29 | 30236 | Medications |

⚠️ Never use these patients in production.

Choices made on top of the docs:

- **Juniper's phone number is a placeholder.** The docs give her none, but `phoneNumber` is required (10 digits). The requests send `5555555555`, the same placeholder the docs use for other patients. If the sandbox rejects it, ask Predoc.
- **Duplicates allowed.** Requests send `allowDuplicatePatient: true`. Without it, v2 rejects a second patient with the same demographics, so the demo could not be replayed.
- **No deprecated field.** `doNotKnowPreviousProvider` is deprecated. Requests send `previousProviders: []` instead.
- **Reason for request:** `reasonForRequest: 2` (information gathering). We have no upcoming appointment to declare.

## Local mock server

`mock-server/server.py` is a fake Predoc API. It uses only the Python standard library.

```bash
pnpm mock                           # status advances every 3s
MOCK_STEP_SECONDS=10 pnpm mock      # slower, for live demos
```

What it does:

- Accepts any credentials. Every other call needs the bearer token it issued.
- Rejects a record request missing a required field, or with a `phoneNumber` that isn't 10 digits. These rules come from the documented `POST /v2/requests` schema.
- Moves statuses forward over time:
  - record requests: `OPEN` → `IN_PROGRESS` → `COMPLETED`
  - retrievals: `Processing` → `Completed`
  - uploads: `IDENTIFYING` → … → `VALIDATED`
- Sends `REQUEST_COMPLETE`, `RETRIEVAL_COMPLETE` and `ANONYMOUS_RECORD_UPLOAD_COMPLETED` webhooks to subscribed URLs.
- Collects webhooks sent to `http://localhost:4010/_mock/webhook-sink`. `GET` that URL to see them.
- Answers every other endpoint with its Postman example response, from `mock-server/examples.json`.

⚠️ Some mock behaviour is invented. It is not Predoc behaviour:

- Webhook payload shape: Predoc doesn't document it.
- Retrieval statuses other than `Processing`.
- Timings.

Don't build integration code on these details. Check them against the sandbox.

## Known gaps in the Predoc sandbox

The Predoc docs don't say:

- whether a previous-provider retrieval can complete in the sandbox
- whether a test webhook can be sent or replayed
- the full list of retrieval statuses and which are terminal
- the webhook payload shape and how to verify a signature

Ask Predoc before relying on any of these.

## Origin

- Converted from the Predoc Postman collection export on 2026-10-01.
- This repo is now the source of truth. Edit the `.bru` files directly.
