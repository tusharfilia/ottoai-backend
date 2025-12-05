# Geofenced Recording & Ghost Mode - Completion Checklist

## 🔴 Critical Missing Components

### 1. Company-Level Configuration Model
**Status**: ❌ Not implemented  
**Priority**: CRITICAL

Add to `Company` model:
```python
# Recording & Privacy Configuration
require_recording_consent: bool = True
allow_ghost_mode: bool = True
ghost_mode_retention: enum (aggregates_only, minimal, none)
ghost_mode_storage: enum (not_stored, ephemeral)
ghost_mode_ephemeral_ttl_minutes: int = 60

# Shift Configuration
default_shift_start: Time = time(7, 0)  # 7am
default_shift_end: Time = time(20, 0)  # 8pm
require_clock_in: bool = True

# Geofence Defaults
default_geofence_radius_start: float = 200.0  # feet
default_geofence_radius_stop: float = 500.0  # feet
```

**Why Critical**: Without this, Ghost Mode policies and shift defaults can't be configured per tenant.

### 2. Transcript Storage Model
**Status**: ❌ Not implemented  
**Priority**: CRITICAL

Create `RecordingTranscript` model (similar to `CallTranscript`):
- Links to `RecordingSession`
- Stores full transcript with speaker diarization
- Applies Ghost Mode restrictions (hide transcript if retention policy disallows)
- Stores Shunya job metadata

**Why Critical**: Currently transcripts aren't stored properly. Need separate model for Ghost Mode restrictions.

### 3. Analysis Result Storage Model
**Status**: ❌ Not implemented  
**Priority**: CRITICAL

Create `RecordingAnalysis` model (or extend existing `CallAnalysis`):
- Links to `RecordingSession` and `Appointment`
- Stores: outcome classification, objections, SOP compliance scores, coaching recommendations
- Always retained in Ghost Mode (aggregated data)
- Links results to `Lead` for pipeline updates

**Why Critical**: Analysis results aren't persisted. Need to store and link to Lead/Appointment.

### 4. Audio Upload Handling
**Status**: ❌ Not implemented  
**Priority**: CRITICAL

**Missing:**
- `POST /api/v1/recording-sessions/{id}/upload-audio`: Endpoint for mobile to upload audio
- S3 presigned URL generation in `start_recording_session`
- Audio file validation (format, size limits)
- Audio metadata update (duration, size) after upload

**Why Critical**: Mobile app needs a way to upload audio. Currently `audio_upload_url` is always None.

### 5. Geocoding Service
**Status**: ❌ Not implemented  
**Priority**: HIGH

**Missing:**
- Auto-geocode appointment addresses when created/updated
- Background job to geocode existing appointments without coordinates
- Integration with geocoding service (Google Maps API, Mapbox, etc.)

**Why Critical**: Without geo coordinates, geofencing can't work. Appointments need `geo_lat`/`geo_lng`.

## 🟡 High Priority Missing Features

### 6. Manager APIs
**Status**: ❌ Not implemented  
**Priority**: HIGH

**Missing endpoints:**
- `POST /api/v1/reps/{rep_id}/shifts/mark-off`: Manager marks rep as off (holiday/PTO)
- `GET /api/v1/reps/{rep_id}/shifts`: List all shifts for a rep (history)
- `GET /api/v1/recording-sessions`: List recording sessions (with Ghost Mode restrictions)
- `PUT /api/v1/companies/{id}/shift-config`: Configure company default shift times
- `PUT /api/v1/companies/{id}/recording-config`: Configure company recording/Ghost Mode settings

**Why Important**: Managers need visibility and control over shifts and recordings.

### 7. Holiday/PTO Support
**Status**: ❌ Not implemented  
**Priority**: HIGH

**Missing:**
- Bulk shift creation for holidays
- PTO request tracking
- Manager approval workflow
- Automatic shift status "off" for PTO/holidays
- Shift exemption reasons stored in `RepShift.notes`

**Why Important**: Required for real-world shift management.

### 8. Concurrent Session Prevention
**Status**: ❌ Not implemented  
**Priority**: HIGH

**Missing:**
- Validation in `start_recording_session` to check for existing active session
- Auto-stop previous session if starting new one
- Prevent multiple concurrent recordings per rep

**Why Important**: Prevents data corruption and ensures clean state.

### 9. Enhanced Validation
**Status**: ⚠️ Partially implemented  
**Priority**: HIGH

**Missing:**
- Distance validation in `start_recording_session` (verify rep is actually in geofence)
- Shift window validation (prevent clock-in outside configured hours)
- Geofence radius validation (ensure reasonable values)
- Appointment date/time validation (can't record past appointments)

**Why Important**: Data integrity and preventing invalid recordings.

### 10. Shunya Integration Enhancements
**Status**: ⚠️ Partially implemented  
**Priority**: HIGH

**Missing:**
- Proper transcript storage (currently TODO comment)
- Analysis result parsing and storage (currently TODO comment)
- Webhook handler for recording session transcription (`/webhooks/uwc/recording-transcription`)
- Error handling for Shunya failures
- Retry logic for failed transcriptions

**Why Important**: Without this, transcripts and analysis aren't persisted.

## 🟢 Medium Priority Enhancements

### 11. Audio Metadata Update Endpoint
**Status**: ❌ Not implemented  
**Priority**: MEDIUM

**Missing:**
- `POST /api/v1/recording-sessions/{id}/metadata`: Update `audio_duration_seconds`, `audio_size_bytes` after upload
- Validation of metadata values

**Why Important**: Accurate tracking of recording duration and size.

### 12. Shift History & Reporting
**Status**: ❌ Not implemented  
**Priority**: MEDIUM

**Missing:**
- `GET /api/v1/reps/{rep_id}/shifts`: Paginated shift history
- `GET /api/v1/companies/{id}/shifts/report`: Aggregated shift reporting (total hours, attendance, etc.)
- Filtering by date range, status, rep

**Why Important**: Manager visibility and compliance reporting.

### 13. Recording Session Query APIs
**Status**: ⚠️ Partially implemented (only GET by ID)  
**Priority**: MEDIUM

**Missing:**
- `GET /api/v1/recording-sessions`: List all sessions with filtering
- `GET /api/v1/appointments/{id}/recording-sessions`: Get sessions for an appointment
- `GET /api/v1/reps/{rep_id}/recording-sessions`: Get sessions for a rep
- Apply Ghost Mode restrictions in list endpoints

**Why Important**: Full query capabilities for dashboards and reporting.

### 14. Shift Configuration Management
**Status**: ⚠️ Partially implemented (per-rep only)  
**Priority**: MEDIUM

**Missing:**
- Company-level default shift configuration API
- Rep override of company defaults
- Bulk shift schedule import (CSV/JSON)

**Why Important**: Scalable shift management for large teams.

### 15. Ghost Mode Retention Policy Enforcement
**Status**: ⚠️ Partially implemented  
**Priority**: MEDIUM

**Missing:**
- Full implementation of retention policies based on Company config
- Transcript visibility enforcement in all query endpoints
- Aggregated data extraction and storage
- Periodic cleanup of data that shouldn't be retained

**Why Important**: Privacy compliance and tenant-specific policies.

## 🔵 Testing & Quality

### 16. Comprehensive Test Suite
**Status**: ❌ Not implemented  
**Priority**: CRITICAL

**Missing tests for:**
- RepShift creation and state transitions
- RecordingSession lifecycle (start, stop, process)
- Ghost Mode restrictions (API responses, data retention)
- Manager APIs (if implemented)
- Shift validation and window enforcement
- Concurrent session prevention
- Geofence validation
- Audio upload flow
- Shunya integration (mocked)
- Event emission verification
- Cleanup tasks

**Why Critical**: Without tests, can't verify correctness or prevent regressions.

### 17. Integration Tests
**Status**: ❌ Not implemented  
**Priority**: HIGH

**Missing:**
- End-to-end flow: clock-in → geofence → record → stop → transcription
- Ghost Mode end-to-end flow
- Manager workflow tests
- Multi-tenant isolation tests

**Why Important**: Verify complete workflows work correctly.

## 📋 Summary by Priority

### 🔴 Must-Have for Production

1. ✅ Data models (RepShift, RecordingSession)
2. ✅ Basic APIs (shift clock-in/out, recording start/stop)
3. ❌ **Company-level configuration**
4. ❌ **Transcript storage model**
5. ❌ **Analysis result storage model**
6. ❌ **Audio upload endpoint**
7. ❌ **Geocoding service**
8. ❌ **Comprehensive test suite**

### 🟡 Should-Have for Robustness

9. ❌ Manager APIs
10. ❌ Holiday/PTO support
11. ❌ Concurrent session prevention
12. ❌ Enhanced validation
13. ❌ Shunya integration completion

### 🟢 Nice-to-Have for Polish

14. Audio metadata endpoint
15. Shift history & reporting
16. Recording session queries
17. Shift configuration management
18. Integration tests

## 🎯 Recommended Implementation Order

1. **Company Configuration** (enables everything else)
2. **Transcript & Analysis Models** (critical data persistence)
3. **Audio Upload Endpoint** (enables actual recording)
4. **Geocoding Service** (enables geofencing)
5. **Shunya Integration Completion** (enables transcription/analysis)
6. **Enhanced Validation** (data integrity)
7. **Manager APIs** (visibility/control)
8. **Test Suite** (quality assurance)
9. **Holiday/PTO Support** (real-world needs)
10. **Remaining enhancements**

## 📊 Completion Estimate

- **Core Foundation**: ✅ 60% complete
- **Critical Missing**: ❌ 40% remaining
- **Total Completion**: ~60% complete

**Time Estimate for Remaining Critical Items**: 2-3 days of focused development

---

**Next Steps**: Start with Company configuration, then transcript/analysis models, then audio upload. These are blockers for everything else.







