# OTTO Backend ↔ Shunya Audit

## 1. Scope & Intent
This doc is an internal integration audit of the Otto backend against Shunya’s current contracts. It is based on (a) actual Otto backend code (clients, services, routes, jobs, webhooks) and (b) the Shunya-authored markdown attachments (`webhook-and-other-payload-ask-otto.md`, `enums-inventory-by-service.md`, `Target_Role_Header.md`, `Integration-Status.md`) plus existing repo docs (e.g., `docs/frontend/SHUNYA_INTEGRATION_OVERVIEW.md`, CSR/Sales Rep integration guides). Where there is conflict, the attached Shunya docs are treated as the source of truth.

## 2. Current Integration Map

| Feature Area | Shunya endpoints used (Otto) | Otto modules / functions | Target Role behavior | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| Transcription | `POST /api/v1/transcription/transcribe`, `GET /api/v1/transcription/transcript/{call_id}` | `app/services/uwc_client.py::transcribe_audio`, `_make_request`; `shunya_integration_service.process_csr_call/process_sales_visit`; `shunya_job_polling_tasks`, `shunya_webhook` | None | OK | Matches contract; no `X-Target-Role` required. |
| Summarization | `POST /api/v1/summarization/summarize` | `uwc_client.summarize_call` | None | Partial | Client method exists; not invoked in integration flow. |
| Qualification | `GET /api/v1/analysis/qualification/{call_id}` (also via `analysis/complete`) | `uwc_client.qualify_lead`, `get_complete_analysis`; processing in `shunya_integration_service._process_shunya_analysis_for_call` | None | OK | Delivered via complete analysis; no target_role requirement. |
| Objections | `GET /api/v1/analysis/complete/{call_id}` | Same as above | None | OK | Parsed via normalizer/adapter. |
| Compliance | `GET /api/v1/analysis/compliance/{call_id}` | `uwc_client.check_compliance` | None | Partial | Shunya contract: POST `/api/v1/sop/compliance/check?target_role=` for new runs. Otto only calls GET (no target_role), so initiating fresh checks per contract is missing. |
| Meeting Segmentation | (expected) `POST /api/v1/meeting-segmentation/analyze`, `GET /api/v1/analysis/meeting-segmentation/{call_id}` | `uwc_client.get_meeting_segmentation_status/get_meeting_segmentation_analysis`; `shunya_integration_service.process_sales_visit` | None | Partial | Client methods exist; end-to-end use not confirmed; no target_role path. |
| Complete Analysis | `GET /api/v1/analysis/complete/{call_id}` | `uwc_client.get_complete_analysis`; webhook + polling paths | None | OK | Actively used in CSR call pipeline. |
| Ask Otto | (Otto uses) `POST /api/v1/search/` | `uwc_client.query_rag`; `routes/rag.py::query_ask_otto` | None (not sent) | Missing/Mismatch | Shunya contract expects `/api/v1/ask-otto/query` with optional `X-Target-Role`; Otto sends search payload, no target_role, different shape. |
| Personal Otto | None invoked | No Otto calls; client has `submit_training_job` but unused | None | Missing | Shunya endpoints (`/api/v1/personal-otto/*`) require `X-Target-Role`; Otto does not call or set header. |
| Follow-up Recommendations | None | No Otto calls to `/api/v1/analysis/followup-recommendations/{call_id}` | None | Missing | Not wired; target_role header absent. |
| SOP Management & Document Ingestion | `POST /api/v1/ingestion/documents/upload`, `GET /api/v1/ingestion/{id}/status` | `uwc_client.ingest_document/get_document_status` | None | Partial | Shunya requires `?target_role=` on SOP/document ingestion; Otto does not send it. No SOP actions/endpoints implemented. |

## 3. Target Role Handling – Reality vs Contract

**Contract (Target_Role_Header.md & Integration-Status.md):**
- Ask Otto: `X-Target-Role` optional (defaults to `sales_rep`) → should be set explicitly.
- Personal Otto: `X-Target-Role` **required**.
- SOP/Compliance actions: `?target_role=` **required** for POST compliance checks and SOP/document ingestion.
- Follow-up recommendations: `X-Target-Role` optional; should be sent.

**Compliant today:** None of the Otto→Shunya calls set `X-Target-Role` or `?target_role=`.

**Will fail without fixes:**
- Personal Otto endpoints (`/api/v1/personal-otto/*`) – Otto does not call them and has no header plumbing.
- SOP ingestion/actions (`/api/v1/ingestion/documents/upload`, `/api/v1/sop/*` POSTs) – header/query absent.
- Compliance POST (`/api/v1/sop/compliance/check?target_role=`) – not used; would 400 without query param.

**Work but semantically wrong / defaulting:**
- Ask Otto: `routes/rag.py` → `uwc_client.query_rag` calls `/api/v1/search/` with no target_role; Shunya defaults to `sales_rep`, so CSR/Exec contexts are mis-scoped.
- Follow-up recommendations: not called; if added without header, would default to `sales_rep`.

References:
- Shunya docs: Target_Role_Header.md (issues 1–5), Integration-Status.md (Ask Otto / Personal Otto / SOP handling).
- Otto code: `app/services/uwc_client.py::_get_headers` (no target_role), `routes/rag.py::query_ask_otto`, `app/services/uwc_client.py::ingest_document`, `::check_compliance`.

## 4. Ask Otto & Personal Otto – Payloads and Headers

### Ask Otto
- **Otto sends (today):** `uwc_client.query_rag` payload → `{ "query": <string>, "document_types": ?, "limit": 10, "score_threshold": 0, "filters": ... }` to `/api/v1/search/`. No conversation_id, no context, no `X-Target-Role`.
- **Shunya expects (webhook-and-other-payload-ask-otto.md):** `POST /api/v1/ask-otto/query` (or `/query-stream`) with payload `{ question, conversation_id?, context, scope?, ... }`, headers include optional `X-Target-Role` (defaults to `sales_rep`).
- **Streaming/webhook handling:** Otto has no Ask Otto streaming handler; only Shunya job webhook for analysis (`/api/v1/shunya/webhook`). No handling of Ask Otto SSE events.
- **UI contexts:** CSR Ask Otto panel, Exec CSR tab, Exec Sales tab all route through `routes/rag.py` → Shunya call without target_role; scoping passed only as local `context` but not forwarded to Shunya.

### Personal Otto
- **Otto calls:** None. Client has `submit_training_job` / `generate_followup_draft` but never invoked; no `X-Target-Role` support.
- **Shunya requires:** `X-Target-Role` header (required) per Target_Role_Header.md & Integration-Status.md.

### Follow-up Recommendations
- **Otto calls:** None to `/api/v1/analysis/followup-recommendations/{call_id}`.
- **Header:** Would need `X-Target-Role`; currently not supported in client.

## 5. Enums Alignment (Shunya canonical vs Otto docs)

| Enum | Shunya canonical values (attached) | Otto-documented values (SHUNYA_INTEGRATION_OVERVIEW / CSR & Sales Rep docs) | Status |
| --- | --- | --- | --- |
| QualificationStatus | hot, warm, cold, unqualified | Same values mentioned in integration overview (qualification hot/warm/cold/unqualified) | Match |
| BookingStatus | booked, not_booked, service_not_offered | Otto docs reference booked / not booked (service_not_offered not consistently documented) | Mismatch (missing service_not_offered) |
| AppointmentType | in-person, virtual, phone | Not explicitly enumerated in Otto docs | Missing |
| CallOutcomeCategory | qualified_and_booked, qualified_service_not_offered, qualified_but_unbooked | Not enumerated in Otto docs | Missing |
| ActionType (Pending Actions) | 30 canonical values (Target_Role_Header.md / enums file) | Otto docs treat pending actions as free-form tasks; no canonical list | Mismatch |
| MeetingPhase | rapport_agenda, proposal_close | Not enumerated in Otto docs | Missing |
| MissedOpportunityType | discovery, cross_sell, upsell, qualification | Not enumerated in Otto docs | Missing |
| CallType (Transcription) | sales_call, csr_call | Otto code uses `call_type` string but not enum; UI docs mention CSR vs sales | Partial (no enum) |

## 6. Gaps & Required Code Changes

**Critical for production**
1) Add target_role plumbing to UWC client  
- Files: `app/services/uwc_client.py::_get_headers` and `_make_request` (add `custom_headers` or `target_role` param).  
- Change: Allow callers to set `X-Target-Role` header or `?target_role=` query; forward to Shunya.  
- Reason: Target_Role_Header.md – required for Personal Otto, SOP actions, proper Ask Otto scoping.

2) Ask Otto endpoint alignment  
- Files: `routes/rag.py`, `uwc_client.query_rag`.  
- Change: Call Shunya `/api/v1/ask-otto/query` (and `/query-stream` if streaming) with payload `{question, conversation_id?, context, scope}`; include `X-Target-Role`.  
- Reason: webhook-and-other-payload-ask-otto.md + Integration-Status.md – current `/search/` payload is incompatible.

3) Personal Otto support  
- Files: `uwc_client.py` (add target_role), new service/route to call `/api/v1/personal-otto/*`.  
- Change: Implement calls with required `X-Target-Role`; expose backend route(s).  
- Reason: Target_Role_Header.md – calls will fail without header.

4) SOP/compliance actions  
- Files: `uwc_client.py` (add POST `/api/v1/sop/compliance/check?target_role=`; SOP/document ingestion to include query param); any calling services.  
- Change: Support required `target_role` param; add endpoints if needed.  
- Reason: Target_Role_Header.md – current GET-only compliance and ingestion lack target_role.

5) Follow-up recommendations  
- Files: `uwc_client.py` (add method for `/api/v1/analysis/followup-recommendations/{call_id}`), integrate where needed; include `X-Target-Role`.  
- Reason: Integration-Status.md & Target_Role_Header.md – missing feature.

**Important**
6) Meeting segmentation verification  
- Files: `shunya_integration_service.process_sales_visit`, `uwc_client` segmentation methods.  
- Change: Confirm path usage; ensure pipeline calls analyze/analysis endpoints and persists results; document status.  
- Reason: Integration map currently uncertain.

7) Enum alignment in docs  
- Files: `docs/frontend/SHUNYA_INTEGRATION_OVERVIEW.md`, CSR/Sales Rep guides.  
- Change: Update documented enum values to match `enums-inventory-by-service.md` (add BookingStatus service_not_offered, ActionType list, MeetingPhase, MissedOpportunityType).  
- Reason: Keep FE and backend aligned with Shunya canon.

**Nice to have**
8) Add Ask Otto streaming handler (optional)  
- Files: new route/handler for SSE if needed; otherwise document non-support.  
- Reason: To match Shunya streaming option.

## 7. Testing Checklist (Backend ↔ Shunya)

**Ask Otto**
- CSR Ask Otto: Send question; ensure request hits `/api/v1/ask-otto/query` with `X-Target-Role: customer_rep` (or csr equivalent); response scoped to CSR data.
- Exec Ask Otto (CSR tab): Query CSR metrics; `X-Target-Role: customer_rep` or exec-equivalent; returns company-wide CSR slice.
- Exec Ask Otto (Sales tab): Query rep metrics; `X-Target-Role: sales_rep`; returns rep-scoped data.
- Streaming variant (if implemented): Verify SSE events per Shunya spec.

**Personal Otto**
- Train profile with `X-Target-Role` required; verify 400 is avoided.
- Fetch profile/status with header set.

**SOP / Compliance**
- POST `/api/v1/sop/compliance/check?target_role=` succeeds (no 400).
- SOP ingestion `/api/v1/ingestion/documents/upload?target_role=` succeeds.

**Follow-up Recommendations**
- POST `/api/v1/analysis/followup-recommendations/{call_id}` with `X-Target-Role` returns expected payload.

**Analysis Pipeline**
- Transcription + Complete Analysis end-to-end (webhook + polling) still succeed after header changes.
- Meeting segmentation (sales visit) returns segmentation payload and is persisted.

## Status Totals
- OK: 4 (Transcription, Qualification, Objections, Complete Analysis)
- Partial: 4 (Summarization, Compliance, Meeting Segmentation, SOP/Document Ingestion)
- Missing/Mismatch: 3 (Ask Otto, Personal Otto, Follow-up Recommendations)

**Critical to fix before production:** Target role plumbing (Ask Otto, Personal Otto, SOP/compliance/follow-ups), Ask Otto endpoint/payload alignment, and implementation of required endpoints (Personal Otto, follow-up recommendations).

