# Shunya Adapter Layer Design

**Date**: 2025-11-24  
**Status**: ✅ **Design Complete - Ready for Shunya Confirmations**

---

## 📋 Overview

The Shunya adapter layer provides a clean, plug-and-play interface between Shunya's API responses and Otto's domain models. This document explains how adapters work, how contracts integrate, and how the system gracefully evolves as Shunya confirms schemas.

---

## 🏗️ Architecture

### Three-Layer Design

```
┌─────────────────────────────────────────────────────────────┐
│                    Shunya API Response                       │
│                  (Raw JSON/Dict)                            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  Contract Layer                              │
│  (Pydantic models defining expected shapes)                 │
│  • ShunyaCSRCallAnalysis                                     │
│  • ShunyaVisitAnalysis                                       │
│  • ShunyaMeetingSegmentation                                 │
│  • ShunyaWebhookPayload                                      │
│  • ShunyaErrorEnvelope                                       │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  Mapping Layer                               │
│  (Value transformations: Shunya → Otto)                     │
│  • Enum mappings (outcome → LeadStatus)                     │
│  • Category mappings (objection labels)                     │
│  • Type mappings (action → TaskAssignee)                    │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  Adapter Layer                               │
│  (Orchestration: Contract + Mapping → Otto format)          │
│  • ShunyaCSRCallAdapter                                      │
│  • ShunyaVisitAdapter                                        │
│  • ShunyaSegmentationAdapter                                 │
│  • ShunyaWebhookAdapter                                      │
│  • ShunyaErrorAdapter                                        │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  Otto Domain Models                          │
│  (SQLAlchemy models)                                        │
│  • Lead, Appointment, Task, KeySignal, etc.                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 📦 Components

### 1. Contract Stubs (`app/schemas/shunya_contracts.py`)

**Purpose**: Define expected Shunya response structures using Pydantic models.

**Key Features**:
- All fields are `Optional` to handle missing data gracefully
- Models serve as **contracts**, not strict validators
- `validate_shunya_response()` provides graceful validation (returns empty contract if validation fails)

**Contract Models**:
- `ShunyaCSRCallAnalysis`: Complete CSR call analysis structure
- `ShunyaVisitAnalysis`: Sales visit analysis structure
- `ShunyaMeetingSegmentation`: Meeting segmentation (Part1/Part2)
- `ShunyaWebhookPayload`: Webhook notification structure
- `ShunyaErrorEnvelope`: Standardized error format
- Supporting models: `ShunyaObjection`, `ShunyaQualificationResponse`, etc.

**Example**:
```python
class ShunyaCSRCallAnalysis(BaseModel):
    job_id: Optional[str]
    qualification: Optional[ShunyaQualificationResponse]
    objections: Optional[ShunyaObjectionsResponse]
    # ... all fields optional for graceful degradation
```

**When Shunya confirms schemas**: Simply update the Pydantic models with final field names/types.

---

### 2. Mapping Tables (`app/services/shunya_mappings.py`)

**Purpose**: Translate Shunya enum values → Otto enum values.

**Key Mappings**:
- `SHUNYA_CSR_OUTCOME_TO_LEAD_STATUS`: Maps CSR outcomes → `LeadStatus`
- `SHUNYA_VISIT_OUTCOME_TO_APPOINTMENT_OUTCOME`: Maps visit outcomes → `AppointmentOutcome`
- `SHUNYA_OBJECTION_TO_OTTO_CATEGORY`: Maps objection labels (currently 1:1)
- `SHUNYA_ACTION_ASSIGNEE_TYPE_TO_TASK_ASSIGNEE`: Maps action types → `TaskAssignee`
- `SHUNYA_OPPORTUNITY_TYPE_TO_SIGNAL_TYPE`: Maps opportunities → `SignalType`

**Mapping Functions**:
- `map_shunya_csr_outcome_to_lead_status()`: Returns `LeadStatus` or `None` (unknown)
- `map_shunya_visit_outcome_to_appointment_outcome()`: Returns `AppointmentOutcome` (defaults to `PENDING` for unknown)
- `normalize_shunya_objection_label()`: Normalizes objection labels (pass-through if unknown)
- `map_shunya_action_to_task_assignee()`: Maps action assignees (defaults based on context)

**Idempotency**: All mapping functions are **idempotent** - same input → same output always.

**Graceful Degradation**:
- Unknown enums → `None` or safe defaults
- Missing values → handled by contract layer
- Type mismatches → attempted conversion, fallback to defaults

**When Shunya confirms enums**: Update mapping dictionaries with final enum values.

---

### 3. Adapter Layer (`app/services/shunya_adapters_v2.py`)

**Purpose**: Orchestrate contract validation + mapping → Otto format.

**Adapter Classes**:
- `ShunyaCSRCallAdapter`: Transforms CSR analysis → Otto format
- `ShunyaVisitAdapter`: Transforms visit analysis → Otto format
- `ShunyaSegmentationAdapter`: Transforms segmentation → Otto format
- `ShunyaWebhookAdapter`: Extracts and validates webhook payloads
- `ShunyaErrorAdapter`: Normalizes error responses

**Adapter Flow**:
1. **Validate**: Use `validate_shunya_response()` to parse raw response into contract
2. **Extract**: Pull values from contract (handles missing fields gracefully)
3. **Map**: Apply mapping functions to translate Shunya values → Otto enums
4. **Transform**: Build normalized dictionary ready for Otto domain models

**Example**:
```python
def adapt(raw_response: Dict[str, Any]) -> Dict[str, Any]:
    # 1. Validate against contract
    contract = validate_shunya_response(raw_response, ShunyaCSRCallAnalysis)
    
    # 2. Extract and map
    normalized = {
        "lead_status": map_shunya_csr_outcome_to_lead_status(
            contract.qualification.qualification_status
        ),
        # ... more mappings
    }
    
    return normalized
```

**Idempotency**: Adapters are idempotent - same input → same output always.

**When Shunya confirms schemas**: Update adapter methods to handle new fields, but structure stays the same.

---

## 🔄 Data Flow

### CSR Call Analysis Flow

```
1. Shunya API Response (raw JSON)
   ↓
2. Contract Validation (ShunyaCSRCallAnalysis)
   • Handles missing fields gracefully
   • Returns contract instance (may have None fields)
   ↓
3. Adapter (ShunyaCSRCallAdapter.adapt())
   • Extracts qualification.qualification_status
   • Maps via map_shunya_csr_outcome_to_lead_status()
   • Extracts objections, compliance, summary, etc.
   • Returns normalized dict
   ↓
4. Integration Service (_process_shunya_analysis_for_call)
   • Uses normalized dict to update Lead status
   • Creates Tasks from pending_actions
   • Creates KeySignals from missed_opportunities
   • Persists to domain models
```

### Visit Analysis Flow

```
1. Shunya API Response (raw JSON)
   ↓
2. Contract Validation (ShunyaVisitAnalysis)
   ↓
3. Adapter (ShunyaVisitAdapter.adapt())
   • Maps outcome → AppointmentOutcome
   • Maps outcome → AppointmentStatus (WON/LOST → COMPLETED)
   • Maps outcome → LeadStatus (WON → CLOSED_WON)
   • Extracts deal_size, visit_actions, etc.
   ↓
4. Integration Service (_process_shunya_analysis_for_visit)
   • Updates Appointment outcome/status
   • Updates Lead status
   • Creates Tasks from visit_actions
   • Creates KeySignals from missed_opportunities
```

### Webhook Flow

```
1. Shunya Webhook Payload (raw JSON)
   ↓
2. Signature Verification (shunya_webhook_security.py)
   • HMAC verification
   • Timestamp validation
   • Tenant isolation check
   ↓
3. Contract Validation (ShunyaWebhookPayload)
   ↓
4. Webhook Adapter (ShunyaWebhookAdapter.adapt())
   • Extracts shunya_job_id, status, company_id
   • Extracts result (may be CSR or Visit analysis)
   ↓
5. Route to Appropriate Adapter
   • If CSR analysis → ShunyaCSRCallAdapter
   • If Visit analysis → ShunyaVisitAdapter
   ↓
6. Integration Service (process and persist)
```

---

## 🛡️ Idempotency Guarantees

### Adapter-Level Idempotency

- **Same input → same output**: Adapters produce identical outputs for identical inputs
- **No side effects**: Adapters are pure functions (no database access, no external calls)
- **Deterministic mappings**: Mapping functions are deterministic

### Integration-Level Idempotency

- **Natural keys**: Tasks and KeySignals use unique keys to prevent duplicates
- **State checks**: Lead status/appointment outcome only update if actually changed
- **Hash checks**: `ShunyaJob.processed_output_hash` prevents duplicate processing

**Combined Guarantee**: Even if adapter is called multiple times with same input, integration service checks ensure no duplicate domain mutations.

---

## 🏢 Multi-Tenancy

### Adapter Layer is Tenant-Agnostic

- **Adapters don't know about tenants**: They operate on data structures only
- **Tenant isolation handled upstream**: Webhook handler and integration service enforce `company_id`

### Tenant Context Flow

```
1. Webhook arrives with company_id in payload
   ↓
2. Webhook handler verifies company_id matches job.company_id
   ↓
3. Adapter processes payload (tenant-agnostic)
   ↓
4. Integration service receives company_id from job
   ↓
5. All DB operations filtered by company_id
```

**Design Decision**: Keep adapters pure (no tenant awareness) for better testability and reusability.

---

## 🔧 Evolution Strategy

### When Shunya Confirms Schemas

**Step 1: Update Contracts**
```python
# In shunya_contracts.py
class ShunyaCSRCallAnalysis(BaseModel):
    # Add new fields with correct types
    new_field: Optional[str] = Field(None, description="...")
```

**Step 2: Update Mappings (if enums changed)**
```python
# In shunya_mappings.py
SHUNYA_CSR_OUTCOME_TO_LEAD_STATUS = {
    "confirmed_value_1": LeadStatus.VALUE_1,  # Update with real values
    # ...
}
```

**Step 3: Update Adapters (if new fields need mapping)**
```python
# In shunya_adapters_v2.py
def adapt(...):
    # Extract new field
    new_field_value = contract.new_field
    # Map if needed
    # Add to normalized dict
```

**Step 4: Integration Service (if new fields affect domain models)**
```python
# In shunya_integration_service.py
# Use new fields from normalized dict
```

**No Breaking Changes**: All updates are additive - existing code continues to work.

---

## 🧪 Testing Strategy

### Simulation Tests (`test_adapter_simulation.py`)

- **Synthetic payloads**: Test with placeholder data (not real Shunya responses)
- **Coverage**: Test complete payloads, missing fields, unknown enums
- **Idempotency**: Verify same input → same output
- **Graceful degradation**: Verify adapters don't crash on malformed data

**Status**: All tests marked as `@pytest.mark.skip` until Shunya confirms schemas.

### When Schemas Confirmed

1. Remove `@pytest.mark.skip` markers
2. Update synthetic payloads with real Shunya structure
3. Add integration tests with real Shunya responses
4. Verify all adapters produce correct Otto domain model inputs

---

## 📊 Mapping Table Reference

### CSR Outcome → Lead Status

| Shunya Value | Otto LeadStatus | Notes |
|--------------|-----------------|-------|
| `qualified_and_booked` | `QUALIFIED_BOOKED` | Primary mapping |
| `qualified_not_booked` | `QUALIFIED_UNBOOKED` | Primary mapping |
| `qualified_service_not_offered` | `QUALIFIED_SERVICE_NOT_OFFERED` | Primary mapping |
| `not_qualified` | `CLOSED_LOST` | Primary mapping |
| `unknown` | `None` | Graceful degradation |

### Visit Outcome → Appointment Outcome

| Shunya Value | Otto AppointmentOutcome | Notes |
|--------------|-------------------------|-------|
| `won` | `WON` | Primary mapping |
| `lost` | `LOST` | Primary mapping |
| `pending_decision` | `PENDING` | Primary mapping |
| `no_show` | `NO_SHOW` | Primary mapping |
| `rescheduled` | `RESCHEDULED` | Primary mapping |
| `unknown` | `PENDING` | Safe default |

### Visit Outcome → Lead Status

| AppointmentOutcome | LeadStatus | Notes |
|-------------------|------------|-------|
| `WON` | `CLOSED_WON` | Only WON/LOST change lead status |
| `LOST` | `CLOSED_LOST` | Only WON/LOST change lead status |
| Other | `None` | No change to lead status |

### Action Assignee Type → Task Assignee

| Shunya Value | Otto TaskAssignee | Context |
|--------------|-------------------|---------|
| `csr` | `CSR` | CSR calls default to CSR |
| `rep` | `REP` | Visits default to REP |
| `manager` | `MANAGER` | Both contexts |
| `unknown` | Context-dependent | CSR → CSR, Visit → REP |

### Missed Opportunity → KeySignal

| Shunya Type | Otto SignalType | SignalSeverity |
|-------------|-----------------|----------------|
| `upsell` | `OPPORTUNITY` | From Shunya severity |
| `cross_sell` | `OPPORTUNITY` | From Shunya severity |
| `unknown` | `OPPORTUNITY` | Default MEDIUM |

---

## 🔍 Contract Stubs Reference

### CSR Call Analysis Contract

```python
ShunyaCSRCallAnalysis:
  - job_id: str
  - qualification: ShunyaQualificationResponse
    - qualification_status: str
    - bant_scores: ShunyaBANTScores
    - overall_score: float
    - confidence_score: float
  - objections: ShunyaObjectionsResponse
    - objections: List[ShunyaObjection]
    - total_objections: int
  - compliance: ShunyaComplianceResponse
    - stages_followed: List[str]
    - stages_missed: List[str]
    - compliance_score: float
  - summary: ShunyaSummaryResponse
  - sentiment_score: float
  - pending_actions: List[ShunyaPendingAction]
  - missed_opportunities: List[ShunyaMissedOpportunity]
  - entities: ShunyaEntities
```

### Visit Analysis Contract

```python
ShunyaVisitAnalysis:
  - job_id: str
  - outcome: str (won, lost, pending, etc.)
  - qualification: ShunyaQualificationResponse
  - objections: ShunyaObjectionsResponse
  - visit_actions: List[ShunyaPendingAction]
  - missed_opportunities: List[ShunyaMissedOpportunity]
  - deal_size: float
  - deal_currency: str
```

### Meeting Segmentation Contract

```python
ShunyaMeetingSegmentation:
  - job_id: str
  - part1: ShunyaSegmentationPart
    - transcript: str
    - summary: str
    - sentiment_score: float
    - key_topics: List[str]
  - part2: ShunyaSegmentationPart
  - transition_point: float
  - segmentation_confidence: float
  - outcome: str
```

---

## ✅ Validation Checklist

When Shunya confirms schemas, verify:

- [ ] All contract fields match Shunya's actual response structure
- [ ] All enum values in mappings match Shunya's actual enums
- [ ] All adapters handle new fields gracefully
- [ ] All simulation tests pass with real Shunya payloads
- [ ] Integration service correctly uses new fields
- [ ] Multi-tenancy still enforced (adapter layer unchanged)
- [ ] Idempotency still guaranteed (mapping functions unchanged)

---

## 🚀 Plug-and-Play Integration

### Current State

1. ✅ Contracts defined (with placeholder structures)
2. ✅ Mappings defined (with placeholder enum values)
3. ✅ Adapters implemented (using contracts + mappings)
4. ✅ Tests scaffolded (marked as skip)
5. ✅ Documentation complete

### When Shunya Responds

**Step 1**: Update contracts with real field names/types
**Step 2**: Update mappings with real enum values
**Step 3**: Remove test skip markers
**Step 4**: Run tests to verify
**Step 5**: Deploy

**No architectural changes needed** - just update the data structures.

---

## 📚 Related Documentation

- **Gap Analysis**: `INTEGRATION_HARDENING_GAP_ANALYSIS.md`
- **Pending Confirmations**: `PENDING_CONFIRMATION.md`
- **Hardening Summary**: `INTEGRATION_HARDENING_SUMMARY.md`
- **Responsibility Matrix**: `RESPONSIBILITY_MATRIX.md`
- **Ask Otto Requirements**: `ASK_OTTO_REQUIREMENTS.md`

---

**Last Updated**: 2025-11-24  
**Status**: Ready for Shunya schema confirmations

