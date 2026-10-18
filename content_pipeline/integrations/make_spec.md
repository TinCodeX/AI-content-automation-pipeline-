# Make (Integromat) Webhook Integration Specification
## Multi-Channel AI Content Automation Pipeline

This guide outlines the step-by-step blueprint to connect **Make (formerly Integromat)** to your local or deployed FastAPI Content Automation Pipeline.

---

### Architecture Overview

```
[Trigger: Airtable / Notion / Form / Schedule]
                      │
                      ▼
          [Module 1: Custom Webhook]
                      │
                      ▼
     [Module 2: HTTP Request to Pipeline]
          POST /webhook/content-trigger
                      │
                      ▼
              [Module 3: Router]
             ╱                  ╲
    (status = completed)   (status = duplicate_rejected)
           ╱                              ╲
 [Module 4A: Notify Slack/Notion]   [Module 4B: Alert Editor]
```

---

### Module 1: Trigger (Custom Webhook or Scheduler)

- **Module**: `Custom Webhook` (Webhooks App)
- **Webhook Name**: `Inbound Content Request`
- **Payload Data Structure**:
  ```json
  {
    "topic": "Practical LLM Agents in Production",
    "target_audience": "Junior to mid-level backend developers",
    "tone": "insightful & authoritative",
    "channels": ["blog", "twitter", "linkedin"]
  }
  ```

---

### Module 2: HTTP Request to Content Pipeline

- **Module**: `HTTP -> Make a request`
- **URL**: `http://<YOUR_HOST_OR_TUNNEL>:8000/webhook/content-trigger`
  *(When testing locally, use ngrok or Cloudflare Tunnel: `https://your-domain.ngrok-free.app/webhook/content-trigger`)*
- **Method**: `POST`
- **Headers**:
  - `Content-Type`: `application/json`
  - `X-Webhook-Secret`: `{{your_webhook_secret_here}}`
- **Body Type**: `Raw`
- **Content Type**: `JSON (application/json)`
- **Request Content**:
  ```json
  {
    "topic": "{{1.topic}}",
    "target_audience": "{{1.target_audience}}",
    "tone": "{{1.tone}}",
    "channels": {{1.channels}}
  }
  ```
- **Parse Response**: `Yes`
- **Timeout**: `30` seconds

---

### Module 3: Router & Filter Setup

Add a **Router** module immediately following the HTTP Request.

#### **Route 1: Success / Content Generated**
- **Condition / Filter Label**: `Content Completed`
- **Operand**: `{{2.data.status}}`
- **Operator**: `Equal to`
- **Value**: `completed` (or HTTP response status `202`)

#### **Route 2: Deduplication Rejected**
- **Condition / Filter Label**: `Duplicate Topic Rejected`
- **Operand**: `{{2.data.status}}`
- **Operator**: `Equal to`
- **Value**: `duplicate_rejected`

---

### Module 4: Downstream Actions

#### **4A: Success Path (Deliverables Ready)**
- **Slack Module**: `Slack -> Create a Message`
  - **Channel**: `#content-publishing`
  - **Message**:
    ```text
    🎉 New Content Generated!
    Topic: {{2.data.topic}}
    Job ID: {{2.data.job_id}}
    Channels: {{join(2.data.channels; ", ")}}
    Word Count: {{2.data.word_count}} words
    ```
- **Notion Module**: `Notion -> Create a Database Item`
  - **Database**: `Editorial Content Calendar`
  - **Fields**: Title = `{{2.data.topic}}`, Status = `Ready for Review`

#### **4B: Duplicate Rejected Path**
- **Slack Module**: `Slack -> Create a Message`
  - **Channel**: `#content-review`
  - **Message**:
    ```text
    ⚠️ Topic Duplicate Warning
    Candidate: {{2.data.topic}}
    Reason: Semantically similar to existing article.
    Matched: {{2.data.match_data.matched_topic}} (Similarity: {{2.data.match_data.similarity}})
    ```

---

### Security & Production Best Practices

1. **Secret Storage**: Store `WEBHOOK_SECRET` in Make Environment Variables.
2. **Exponential Backoff**: Enable Make's automatic retry mechanism on network timeouts (503/504).
3. **Tunneling**: For local development, expose the FastAPI server via:
   ```bash
   ngrok http 8000
   ```
