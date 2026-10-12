# Google Cloud Platform (GCP) Setup Guide: HarnessX

This guide explains how to configure Google Cloud Platform services for the HarnessX agent infrastructure, spanning local prototyping (Google AI Studio) through enterprise production (Vertex AI, Cloud Run, Firestore, BigQuery).

---

## 1. Authentication & Credentials Architecture

HarnessX implements a clean provider abstraction designed for seamless transitions between local prototyping and enterprise GCP deployments:

```
                  ┌──────────────────────┐
                  │    ProviderFactory   │
                  └──────────┬───────────┘
                             │
            ┌────────────────┴────────────────┐
            ▼                                 ▼
   [USE_VERTEX = false]              [USE_VERTEX = true]
   Gemini API (AI Studio)            Vertex AI (Enterprise)
   - Requires GEMINI_API_KEY         - Uses Application Default Credentials
   - Zero GCP setup needed           - Project & Region configured
```

### 1.1 Local Prototyping (Google AI Studio)
1. Obtain an API key from [Google AI Studio](https://aistudio.google.com/).
2. Set the key in your `.env` file:
   ```bash
   GEMINI_API_KEY="your-gemini-api-key"
   USE_VERTEX="false"
   ```
3. No Google Cloud project or billing is required for local testing.

### 1.2 Enterprise / Production (Vertex AI)
1. Install the Google Cloud SDK:
   ```bash
   gcloud init
   ```
2. Log in using Application Default Credentials (ADC) without downloading raw JSON service keys:
   ```bash
   gcloud auth application-default login
   ```
3. Set your project ID and region:
   ```bash
   gcloud config set project YOUR_PROJECT_ID
   ```
4. Set the corresponding environment variables:
   ```bash
   USE_VERTEX="true"
   GOOGLE_CLOUD_PROJECT="YOUR_PROJECT_ID"
   GCP_REGION="us-central1"
   ```

---

## 2. Required GCP APIs

Enable the following APIs in your GCP project console or via `gcloud`:

```bash
gcloud services enable \
    aiplatform.googleapis.com \
    run.googleapis.com \
    firestore.googleapis.com \
    bigquery.googleapis.com \
    artifactregistry.googleapis.com
```

---

## 3. Service Roles & IAM Permissions

When deploying the backend (Person 2) to Cloud Run, assign the runtime service account the following least-privilege roles:

| GCP Role | Service Purpose |
|---|---|
| `roles/aiplatform.user` | Invoking Gemini models via Vertex AI |
| `roles/datastore.user` | Session persistence and history in Firestore |
| `roles/bigquery.dataEditor` | Ingesting execution telemetry and benchmarks |
| `roles/run.invoker` | Cloud Run service-to-service communication |

---

## 4. Security Policy & Best Practices

1. **Never Commit Secrets**: Never commit `.env` files or Google service account credentials (`*.json`).
2. **Zero Hardcoded Keys**: The `harness_core` package retrieves credentials exclusively via environment variables or ADC.
3. **Restricted Workspace Sandbox**: The agent is restricted from reading or executing outside designated `WORKSPACE_BASE_DIR` paths.
4. **Sanitized Telemetry**: Logging and metrics collectors sanitize all prompts, outputs, and environment variables before publishing events.
