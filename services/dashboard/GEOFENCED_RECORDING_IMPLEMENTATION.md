# Geofenced Auto-Recording & Ghost Mode Implementation

## Overview

This document summarizes the implementation of two key features for Sales Reps:
1. **Geofenced Auto-Recording**: Automatic recording when reps enter appointment geofences
2. **Ghost Mode**: Privacy-focused recording with no raw audio retention

## Implementation Summary

### ✅ Completed Components

#### 1. Data Models

**New Models:**
- `RepShift` (`app/models/rep_shift.py`): Tracks clock-in/out and shift state
- `RecordingSession` (`app/models/recording_session.py`): Tracks geofenced recording sessions

**Updated Models:**
- `SalesRep`: Added `recording_mode`, `allow_location_tracking`, `allow_recording`, shift configuration fields
- `Appointment`: Added `geo_lat`, `geo_lng`, `geofence_radius_start`, `geofence_radius_stop`
- `Company`: Added relationships to `RepShift` and `RecordingSession`

**Enums:**
- `ShiftStatus`: `off`, `planned`, `active`, `completed`, `skipped`
- `RecordingMode`: `normal`, `ghost`, `off`
- `AudioStorageMode`: `persistent`, `ephemeral`, `not_stored`
- `TranscriptionStatus`: `not_started`, `in_progress`, `completed`, `failed`
- `AnalysisStatus`: `not_started`, `in_progress`, `completed`, `failed`
- `ShiftConfigSource`: `tenant_default`, `custom`

#### 2. API Endpoints

**Shift Management** (`/api/v1/reps/{rep_id}/shifts/`):
- `POST /clock-in`: Clock in for a shift
- `POST /clock-out`: Clock out from current shift
- `GET /today`: Get today's shift status

**Recording Sessions** (`/api/v1/recording-sessions/`):
- `POST /start`: Start a geofenced recording session
- `POST /{session_id}/stop`: Stop a recording session
- `GET /{session_id}`: Get recording session details (with Ghost Mode restrictions)

#### 3. Services

**RecordingSessionService** (`app/services/recording_session_service.py`):
- `get_audio_storage_mode()`: Determines storage mode based on recording mode
- `apply_ghost_mode_restrictions()`: Applies privacy restrictions to API responses
- `should_retain_transcript()`: Determines transcript retention policy
- `should_retain_audio()`: Determines audio retention policy
- `cleanup_ephemeral_sessions()`: Cleans up expired ephemeral sessions

#### 4. Background Tasks

**Recording Session Tasks** (`app/tasks/recording_session_tasks.py`):
- `process_recording_session()`: Processes recording sessions (transcription + analysis)
- `cleanup_ephemeral_sessions()`: Periodic cleanup of expired ephemeral sessions

**Features:**
- Handles Ghost Mode (NOT_STORED) by skipping transcription
- Integrates with Shunya/UWC for ASR and analysis
- Emits domain events for transcription/analysis completion
- Automatic retry with exponential backoff

#### 5. Domain Events

Events emitted:
- `rep.shift.started`: When rep clocks in
- `rep.shift.ended`: When rep clocks out
- `recording_session.started`: When recording session starts
- `recording_session.ended`: When recording session stops
- `recording_session.transcription.completed`: When transcription completes
- `recording_session.transcription.failed`: When transcription fails
- `recording_session.analysis.completed`: When analysis completes

#### 6. Database Migration

**Migration File**: `migrations/versions/20251115000000_add_rep_shifts_and_recording_sessions.py`

Creates:
- `rep_shifts` table with indexes
- `recording_sessions` table with indexes
- Adds columns to `sales_reps` table
- Adds columns to `appointments` table
- Creates all necessary enums

### 🔄 Ghost Mode Implementation

#### Storage Policies

**Option A - NOT_STORED (Implemented)**:
- Audio is never stored in backend
- Mobile app streams directly to Shunya (if supported)
- Only aggregated results are retained
- No `audio_url` in database

**Option B - EPHEMERAL (Supported)**:
- Audio stored temporarily with TTL (default: 60 minutes)
- Automatic cleanup via Celery Beat task
- `expires_at` field tracks expiration
- No UI exposure of audio/transcript

#### Retention Policies

Configurable per tenant (TODO: Add to Company model):
- `aggregates_only`: Only aggregated metrics (outcome, scores, tags)
- `minimal`: Aggregates + summary transcript
- `none`: No data retention (only real-time analysis)

#### API Restrictions

In Ghost Mode:
- `audio_url` is always `None` in API responses
- Full transcript may be restricted based on tenant config
- Only aggregated metrics are exposed to managers/reps

### 📋 Example Flows

#### Normal Mode Flow

1. Rep clocks in → `POST /api/v1/reps/{rep_id}/shifts/clock-in`
2. Rep enters geofence (200ft) → Mobile app calls `POST /api/v1/recording-sessions/start`
3. Recording starts → Audio stored in S3, `audio_url` set
4. Rep exits geofence (500ft) → Mobile app calls `POST /api/v1/recording-sessions/{id}/stop`
5. Celery task processes → Shunya ASR → Transcription stored
6. Shunya analysis → Outcome, objections, SOP compliance stored
7. Results attached to Appointment/Lead

#### Ghost Mode Flow

1. Rep clocks in (with `recording_mode=ghost`)
2. Rep enters geofence → `POST /api/v1/recording-sessions/start`
3. Backend sets `audio_storage_mode=NOT_STORED`
4. Mobile app streams audio to Shunya (or uploads ephemerally)
5. Rep exits geofence → `POST /api/v1/recording-sessions/{id}/stop`
6. Celery task processes → Skips transcription (no audio_url)
7. Only aggregated results stored (if tenant config allows)
8. Audio never persisted, transcript not stored

### 🔒 Privacy & Compliance

#### Consent Management

- Reps must explicitly opt-in via clock-in toggle
- `allow_location_tracking` and `allow_recording` flags per rep
- Managers can mark reps as "off" (no recording expected)

#### Tenant Configuration (TODO)

Add to Company model:
- `require_recording_consent`: bool
- `allow_ghost_mode`: bool
- `default_shift_start`: time
- `default_shift_end`: time
- `ghost_mode_retention`: enum (aggregates_only, minimal, none)
- `ghost_mode_storage`: enum (not_stored, ephemeral)

### 🧪 Testing Status

**Pending Tests** (to be implemented):
- [ ] RepShift creation on clock-in
- [ ] Active shift validation before recording
- [ ] RecordingSession creation in Normal mode
- [ ] RecordingSession creation in Ghost mode
- [ ] Audio storage mode determination
- [ ] Ghost Mode API restrictions
- [ ] Transcription trigger on session stop
- [ ] Ephemeral session cleanup
- [ ] Event emission verification

### 📝 Next Steps

1. **Add Tests**: Comprehensive test suite for all features
2. **Tenant Configuration**: Add Company-level configuration for Ghost Mode policies
3. **Mobile App Integration**: 
   - Implement geofence detection
   - Implement audio recording/upload
   - Handle Ghost Mode streaming (if supported by Shunya)
4. **UI Updates**: 
   - Manager dashboard for shift management
   - Recording session visibility (with Ghost Mode restrictions)
5. **Geocoding**: Auto-geocode appointment addresses to populate `geo_lat`/`geo_lng`
6. **Monitoring**: Add metrics for recording sessions, Ghost Mode usage, transcription success rates

### 🔧 Configuration

**Environment Variables** (no new ones required):
- Uses existing `REDIS_URL` for Celery
- Uses existing `ENABLE_CELERY` flag
- Uses existing Shunya/UWC configuration

**Database Migration**:
```bash
alembic upgrade head
```

### 📚 API Documentation

All endpoints are documented with FastAPI's automatic OpenAPI schema:
- Visit `/docs` for interactive API documentation
- All endpoints require authentication (Clerk JWT)
- Role-based access control enforced

### 🎯 Key Design Decisions

1. **Mobile-First Geofencing**: Mobile app handles geofence detection; backend validates and stores
2. **Privacy by Default**: Ghost Mode uses NOT_STORED by default (most privacy-friendly)
3. **Flexible Configuration**: Tenant-level config allows compliance with different privacy laws
4. **Event-Driven**: All state changes emit events for real-time updates
5. **Graceful Degradation**: Ghost Mode still provides value (aggregated insights) without raw audio

### ⚠️ Known Limitations

1. **Geocoding**: Appointment addresses must be geocoded manually or via separate service
2. **Shunya Streaming**: Ghost Mode streaming endpoint not yet implemented (requires Shunya support)
3. **Tenant Config**: Company-level Ghost Mode configuration not yet in database (TODO)
4. **Transcript Storage**: Transcript storage model not yet created (currently stored in session notes)

### 📦 Files Created/Modified

**New Files:**
- `app/models/rep_shift.py`
- `app/models/recording_session.py`
- `app/routes/rep_shifts.py`
- `app/routes/recording_sessions.py`
- `app/services/recording_session_service.py`
- `app/tasks/recording_session_tasks.py`
- `migrations/versions/20251115000000_add_rep_shifts_and_recording_sessions.py`

**Modified Files:**
- `app/models/sales_rep.py`
- `app/models/appointment.py`
- `app/models/company.py`
- `app/schemas/domain.py`
- `app/database.py`
- `app/celery_app.py`
- `app/main.py`

---

**Implementation Date**: 2025-11-15
**Status**: ✅ Core implementation complete, tests pending



