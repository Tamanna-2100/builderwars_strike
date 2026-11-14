# Verity

Verity is a hackathon prototype for turning application security findings into reviewable evidence, proposed code changes, and regression tests. Its intended audience is developers and security reviewers who need to understand a finding before deciding whether to fix it.

**This is a prototype, not a production security product. Do not use real customer code, credentials, or data with the current setup.** The included Flask application is intentionally vulnerable and is for isolated local demonstrations with synthetic data only.

## Intended workflow

The project is intended to follow this sequence:

1. Inspect source code and produce candidate findings.
2. Review evidence and verify whether a finding is relevant.
3. Propose a patch for a confirmed finding.
4. Review the patch and check the behavior again.
5. Run regression tests and produce a report for a human reviewer.

The goal is to support review, not to promise that every issue is found or that an automatically proposed patch is safe. Findings, evidence, and patches need human judgment.

## What works today

- **Dashboard:** A React and Tailwind page displays mock run statistics, a five-stage timeline, and expandable findings with evidence, patch, and regression-test tabs. It refreshes `ui/public/state.json`; it is not connected to the API.
- **Run records:** The FastAPI service creates a pending run record with `POST /scan`, reads a record with `GET /runs/{run_id}`, and downloads stored finding diffs with `GET /runs/{run_id}/patch`. Creating a record does not start a scan or background worker.
- **State updates:** `state_manager.py` updates stage records using a per-run file lock and atomic file replacement. Records are stored under `runs/{run_id}/state.json`.
- **Source inspection:** `scanner.py` reads Python files directly under `target/`, sends their contents to the configured Amazon Bedrock model, and validates the returned list against the hypothesis fields.
- **Test review:** `verifier.py` contains a local HTTP test runner and a separate read-only review flow that displays a human-authored test and asks for approval. The lower-level `run_spec` function can also be called directly; the approval flow is not enforced for every caller.
- **Patch proposals:** `patcher.py` asks the model for a proposal, writes it separately under `runs/{finding_id}/patched/`, returns a diff, and creates a skipped regression-test scaffold. The scaffold needs a human to complete it; it does not prove a fix.
- **Artifact sharing:** `storage.py` provides explicitly invoked helpers to upload selected run artifacts to S3 and to create a draft GitHub PR containing review artifacts. They are not automatically invoked by the API or UI. A PR contains the patch as a file for review; it does not apply the proposed changes.

These pieces are not yet wired into an automated end-to-end pipeline. The UI's example counts and findings are mock data, not results from an actual run.

## How it is organized

| Path | Purpose |
| --- | --- |
| `target/` | Deliberately vulnerable Flask and SQLite sample application, seed data, and sample tests. |
| `ui/` | React dashboard and mock state. |
| `api.py` | Run-record and patch-download endpoints. |
| `state_manager.py` | Run-state creation and stage updates. |
| `scanner.py` | Source collection and model-response validation. |
| `bedrock_client.py` | Amazon Bedrock Converse client and local response cache. |
| `verifier.py` | Local HTTP test execution and the human approval flow. |
| `patcher.py` | Model-generated patch proposal and test scaffold. |
| `storage.py` | Optional S3 export and draft PR creation. |
| `tests/` | Tests for the Python helpers and API. |

`AGENTS.md` documents the intended finding, test, and run-state shapes.

## Local setup

Prerequisites: Python 3.12, Node.js and npm. AWS credentials and model configuration are needed only when calling Bedrock or S3. The default UI and API setup below does not require AWS.

From the repository root, create a Python environment and install dependencies:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -r target/requirements.txt
```

Start the API bound to the local machine:

```sh
.venv/bin/uvicorn api:app --host 127.0.0.1 --port 8000
```

In a second terminal, start the mock dashboard:

```sh
npm --prefix ui install
npm --prefix ui run dev -- --host 127.0.0.1
```

Open the URL printed by Vite. The page reads its own mock JSON, so starting the API does not change the dashboard. The API's CORS allowlist currently covers the default local Vite port, 5173.

To run the Python tests or build the frontend:

```sh
.venv/bin/python -m pytest -q tests
npm --prefix ui run build
```

Three review tests are currently expected to fail: they expose verifier pre-validation, partial patch-output cleanup, and diff formatting when files lack trailing newlines. Tests that mock model or network clients do not establish that live AWS or GitHub integration works.

## Configuration and data handling

`bedrock_client.py` loads `.env` and requires an agent-specific model ID, such as `SCANNER_MODEL_ID` for scanning or `PATCHER_MODEL_ID` for patch proposals. AWS region, profile, and credentials are supplied through the environment and AWS SDK configuration; no model, region, or profile is hard-coded. `USE_CACHE_ONLY=1` prevents a Bedrock call when a cached response is absent.

Source sent to the model leaves the local process. Model responses are cached in `.cache/`; run records, evidence, diffs, and patch proposals may also contain sensitive information. Review your AWS account's model access, logging, region, encryption, and retention settings before considering any real data.

For optional S3 export, set `S3_BUCKET` and call `storage.upload_run(run_id)` explicitly. For a draft PR, set `GITHUB_TOKEN` and `GITHUB_REPOSITORY`, optionally set `GITHUB_BASE_BRANCH`, and call `storage.open_review_pr(run_id)` explicitly. These operations transmit artifacts to external services; inspect them and obtain authorization before sharing. A failed PR operation returns the local patch-download path as a fallback.

Do not commit `.env`, credentials, generated run artifacts, or private evidence. The current repository ignore rules do not exclude `.env`; review them before committing.

## Current limitations

- The API does not authenticate users or isolate run records by client. CORS is not authentication.
- The sample target and its credentials are for synthetic local testing only. Do not expose it to untrusted networks.
- There is no integrated scan-to-report pipeline, and no claim of complete detection or verified remediation.
- S3 and GitHub integrations require explicit configuration and have only been exercised with mocked tests in this repository.
- The local review workflow, output handling, sandboxing, and data-retention controls need further hardening before use with customer code.