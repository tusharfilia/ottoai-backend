# CSR API Quickstart

**Date**: 2025-11-24  
**Status**: ✅ **Ready for Frontend Development**

---

## 📋 Purpose

This is a short, practical guide to get the CSR frontend team started calling Otto backend APIs within minutes. For full endpoint-by-endpoint details, see [CSR_APP_INTEGRATION.md](./CSR_APP_INTEGRATION.md).

---

## 1. Base URLs

### Staging / Production (Current)

```typescript
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://ottoai-backend-production.up.railway.app';
```

**Note**: The current backend is hosted on Railway. A dedicated staging environment URL will be provided later.

**Environment Variable**:
- `NEXT_PUBLIC_API_URL` - Set this in your `.env.local` file for local development or override the default Railway URL.

### Local Development

For local backend development:
```typescript
const LOCAL_API_BASE_URL = 'http://localhost:8000';
```

Set in `.env.local`:
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## 2. Authentication Pattern

### JWT from Clerk

The CSR Next.js app uses Clerk for authentication. The JWT token from Clerk must be included in all API requests.

**Getting the JWT**:

In your Next.js app, use Clerk's hooks to get the token:

```typescript
import { useAuth } from '@clerk/nextjs';

function MyComponent() {
  const { getToken } = useAuth();
  
  const fetchData = async () => {
    const token = await getToken();
    // Use token in API calls
  };
}
```

**Or in API routes/middleware**:

```typescript
import { auth } from '@clerk/nextjs';

export async function GET(request: Request) {
  const { getToken } = auth();
  const token = await getToken();
  // Use token in API calls
}
```

### Request Headers

All API requests must include:

```typescript
{
  'Authorization': `Bearer ${jwtToken}`,
  'Content-Type': 'application/json',
}
```

**Important**:
- The `company_id` and `role` are extracted from the JWT claims by the backend
- Frontend should **NOT** manually pass `X-Company-Id` header unless explicitly required by a specific endpoint
- The backend's `TenantContextMiddleware` automatically enforces tenant isolation using JWT claims

---

## 3. Example API Client

Here's a minimal TypeScript example showing how to make authenticated API calls:

```typescript
// lib/api/client.ts

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'https://ottoai-backend-production.up.railway.app';

interface ApiError {
  status: number;
  message: string;
  error_code?: string;
}

class ApiError extends Error {
  constructor(message: string, public status: number, public error_code?: string) {
    super(message);
    this.name = 'ApiError';
  }
}

/**
 * Get JWT token from Clerk
 */
async function getAuthToken(): Promise<string | null> {
  // In client components, use useAuth hook
  // In server components/API routes, use auth() from @clerk/nextjs/server
  if (typeof window !== 'undefined') {
    // Client-side: use Clerk React hooks
    const { useAuth } = await import('@clerk/nextjs');
    // Implementation depends on your setup
    return null; // Replace with actual token retrieval
  } else {
    // Server-side: use Clerk server SDK
    const { auth } = await import('@clerk/nextjs/server');
    const { getToken } = auth();
    return await getToken();
  }
}

/**
 * Make an authenticated GET request
 */
export async function apiGet<T>(
  path: string,
  params?: Record<string, any>
): Promise<T> {
  const token = await getAuthToken();
  
  if (!token) {
    throw new ApiError('Authentication required', 401);
  }
  
  // Build URL with query params
  const url = new URL(`${API_BASE_URL}${path}`);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        url.searchParams.append(key, String(value));
      }
    });
  }
  
  const response = await fetch(url.toString(), {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });
  
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ message: 'Unknown error' }));
    throw new ApiError(
      errorData.message || `Request failed: ${response.status}`,
      response.status,
      errorData.error_code
    );
  }
  
  const json = await response.json();
  // Handle APIResponse wrapper
  return json.data !== undefined ? json.data : json;
}

/**
 * Make an authenticated POST request
 */
export async function apiPost<T>(
  path: string,
  body?: any
): Promise<T> {
  const token = await getAuthToken();
  
  if (!token) {
    throw new ApiError('Authentication required', 401);
  }
  
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ message: 'Unknown error' }));
    throw new ApiError(
      errorData.message || `Request failed: ${response.status}`,
      response.status,
      errorData.error_code
    );
  }
  
  const json = await response.json();
  return json.data !== undefined ? json.data : json;
}

// Similar for PATCH, PUT, DELETE...
```

---

## 4. Quick Example: Fetch Contact Card

```typescript
import { apiGet } from '@/lib/api/client';

async function loadContactCard(contactCardId: string) {
  try {
    const contactCard = await apiGet<ContactCardDetail>(
      `/api/v1/contact-cards/${contactCardId}`
    );
    
    console.log('Contact name:', contactCard.first_name, contactCard.last_name);
    console.log('Lead status:', contactCard.lead_status);
    console.log('Open tasks:', contactCard.open_tasks);
    
    return contactCard;
  } catch (error) {
    if (error instanceof ApiError) {
      if (error.status === 404) {
        console.error('Contact card not found');
      } else if (error.status === 403) {
        console.error('Permission denied');
      } else {
        console.error('API error:', error.message);
      }
    } else {
      console.error('Network error:', error);
    }
    throw error;
  }
}
```

---

## 5. Error Handling

### Common Status Codes

- **200 OK** - Success
- **400 Bad Request** - Invalid input (check request body/params)
- **401 Unauthorized** - Missing/invalid JWT (re-authenticate)
- **403 Forbidden** - Insufficient permissions (check user role)
- **404 Not Found** - Resource doesn't exist or belongs to another company
- **409 Conflict** - Resource conflict (e.g., duplicate task)
- **429 Too Many Requests** - Rate limit exceeded (implement exponential backoff)
- **500 Internal Server Error** - Server error (retry or report)

### Example Error Handling

```typescript
try {
  const result = await apiGet('/api/v1/contact-cards/123');
} catch (error) {
  if (error instanceof ApiError) {
    switch (error.status) {
      case 401:
        // Redirect to login or refresh token
        redirectToLogin();
        break;
      case 403:
        // Show permission denied message
        showError('You don\'t have permission to access this resource');
        break;
      case 404:
        // Show not found message
        showError('Resource not found');
        break;
      case 409:
        // Handle conflict (e.g., duplicate)
        showError('This action conflicts with existing data');
        break;
      case 429:
        // Rate limited - retry after delay
        await delay(1000);
        // Retry logic...
        break;
      case 500:
        // Server error - show retry option
        showError('Server error. Please try again.');
        break;
      default:
        showError('An unexpected error occurred');
    }
  }
}
```

---

## 6. Response Format

All endpoints return responses wrapped in `APIResponse<T>`:

```typescript
interface APIResponse<T> {
  success: boolean;
  data: T;
  message?: string;
}
```

**Example Response**:

```json
{
  "success": true,
  "data": {
    "id": "contact_123",
    "first_name": "John",
    "last_name": "Doe",
    "primary_phone": "+12025551234"
  }
}
```

**Extract Data**:

```typescript
const response = await apiGet('/api/v1/contact-cards/123');
// response is already the unwrapped data (T), not the full APIResponse
console.log(response.id); // "contact_123"
console.log(response.first_name); // "John"
```

---

## 7. Common Endpoints

### Dashboard

```typescript
// Get dashboard metrics
const metrics = await apiGet('/api/v1/dashboard/metrics?company_id=YOUR_COMPANY_ID');

// Get booking rate chart data
const bookingRate = await apiGet('/api/v1/dashboard/booking-rate?start_date=2025-11-01&end_date=2025-11-30');

// Get top objections
const objections = await apiGet('/api/v1/dashboard/top-objections?limit=5');
```

### Contact Cards

```typescript
// Get contact card detail
const contactCard = await apiGet(`/api/v1/contact-cards/${contactCardId}`);
```

### Calls

```typescript
// Get missed calls
const calls = await apiGet(
  `/api/v1/dashboard/calls?status=missed&company_id=${companyId}`
);
```

### Tasks

```typescript
// List tasks
const tasks = await apiGet('/api/v1/tasks?contact_card_id=123&status=open');

// Complete task
await apiPost(`/api/v1/tasks/${taskId}/complete`);
```

---

## 8. Testing Your Setup

### 1. Test Authentication

```typescript
// Try fetching your company's data
const metrics = await apiGet('/api/v1/dashboard/metrics?company_id=YOUR_COMPANY_ID');
console.log('✅ Authentication working!', metrics);
```

### 2. Test Tenant Isolation

```typescript
// Try accessing another company's data (should fail with 403)
try {
  const otherCompanyData = await apiGet('/api/v1/dashboard/metrics?company_id=OTHER_COMPANY_ID');
} catch (error) {
  if (error.status === 403) {
    console.log('✅ Tenant isolation working!');
  }
}
```

### 3. Test Error Handling

```typescript
// Try accessing non-existent resource (should fail with 404)
try {
  const missing = await apiGet('/api/v1/contact-cards/non-existent-id');
} catch (error) {
  if (error.status === 404) {
    console.log('✅ Error handling working!');
  }
}
```

---

## 9. Next Steps

1. **Set up environment variables**:
   ```env
   NEXT_PUBLIC_API_BASE_URL=https://ottoai-backend-production.up.railway.app
   ```

2. **Implement API client** using the patterns above

3. **Start with a simple endpoint** (e.g., `GET /api/v1/dashboard/metrics`) to verify auth works

4. **Read the full integration spec**: [CSR_APP_INTEGRATION.md](./CSR_APP_INTEGRATION.md) for complete endpoint details

---

## 10. Quick Reference

| Item | Value |
|------|-------|
| **Base URL** | `process.env.NEXT_PUBLIC_API_BASE_URL` or Railway URL |
| **Auth Header** | `Authorization: Bearer <JWT_FROM_CLERK>` |
| **Content-Type** | `application/json` |
| **Response Format** | `{ success: boolean, data: T }` |
| **Error Format** | `{ error_code: string, message: string }` |

---

**For full endpoint-by-endpoint details, see [CSR_APP_INTEGRATION.md](./CSR_APP_INTEGRATION.md)**


**Date**: 2025-11-24  
**Status**: ✅ **Ready for Frontend Development**

---

## 📋 Purpose

This is a short, practical guide to get the CSR frontend team started calling Otto backend APIs within minutes. For full endpoint-by-endpoint details, see [CSR_APP_INTEGRATION.md](./CSR_APP_INTEGRATION.md).

---

## 1. Base URLs

### Staging / Production (Current)

```typescript
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://ottoai-backend-production.up.railway.app';
```

**Note**: The current backend is hosted on Railway. A dedicated staging environment URL will be provided later.

**Environment Variable**:
- `NEXT_PUBLIC_API_URL` - Set this in your `.env.local` file for local development or override the default Railway URL.

### Local Development

For local backend development:
```typescript
const LOCAL_API_BASE_URL = 'http://localhost:8000';
```

Set in `.env.local`:
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## 2. Authentication Pattern

### JWT from Clerk

The CSR Next.js app uses Clerk for authentication. The JWT token from Clerk must be included in all API requests.

**Getting the JWT**:

In your Next.js app, use Clerk's hooks to get the token:

```typescript
import { useAuth } from '@clerk/nextjs';

function MyComponent() {
  const { getToken } = useAuth();
  
  const fetchData = async () => {
    const token = await getToken();
    // Use token in API calls
  };
}
```

**Or in API routes/middleware**:

```typescript
import { auth } from '@clerk/nextjs';

export async function GET(request: Request) {
  const { getToken } = auth();
  const token = await getToken();
  // Use token in API calls
}
```

### Request Headers

All API requests must include:

```typescript
{
  'Authorization': `Bearer ${jwtToken}`,
  'Content-Type': 'application/json',
}
```

**Important**:
- The `company_id` and `role` are extracted from the JWT claims by the backend
- Frontend should **NOT** manually pass `X-Company-Id` header unless explicitly required by a specific endpoint
- The backend's `TenantContextMiddleware` automatically enforces tenant isolation using JWT claims

---

## 3. Example API Client

Here's a minimal TypeScript example showing how to make authenticated API calls:

```typescript
// lib/api/client.ts

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'https://ottoai-backend-production.up.railway.app';

interface ApiError {
  status: number;
  message: string;
  error_code?: string;
}

class ApiError extends Error {
  constructor(message: string, public status: number, public error_code?: string) {
    super(message);
    this.name = 'ApiError';
  }
}

/**
 * Get JWT token from Clerk
 */
async function getAuthToken(): Promise<string | null> {
  // In client components, use useAuth hook
  // In server components/API routes, use auth() from @clerk/nextjs/server
  if (typeof window !== 'undefined') {
    // Client-side: use Clerk React hooks
    const { useAuth } = await import('@clerk/nextjs');
    // Implementation depends on your setup
    return null; // Replace with actual token retrieval
  } else {
    // Server-side: use Clerk server SDK
    const { auth } = await import('@clerk/nextjs/server');
    const { getToken } = auth();
    return await getToken();
  }
}

/**
 * Make an authenticated GET request
 */
export async function apiGet<T>(
  path: string,
  params?: Record<string, any>
): Promise<T> {
  const token = await getAuthToken();
  
  if (!token) {
    throw new ApiError('Authentication required', 401);
  }
  
  // Build URL with query params
  const url = new URL(`${API_BASE_URL}${path}`);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        url.searchParams.append(key, String(value));
      }
    });
  }
  
  const response = await fetch(url.toString(), {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });
  
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ message: 'Unknown error' }));
    throw new ApiError(
      errorData.message || `Request failed: ${response.status}`,
      response.status,
      errorData.error_code
    );
  }
  
  const json = await response.json();
  // Handle APIResponse wrapper
  return json.data !== undefined ? json.data : json;
}

/**
 * Make an authenticated POST request
 */
export async function apiPost<T>(
  path: string,
  body?: any
): Promise<T> {
  const token = await getAuthToken();
  
  if (!token) {
    throw new ApiError('Authentication required', 401);
  }
  
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ message: 'Unknown error' }));
    throw new ApiError(
      errorData.message || `Request failed: ${response.status}`,
      response.status,
      errorData.error_code
    );
  }
  
  const json = await response.json();
  return json.data !== undefined ? json.data : json;
}

// Similar for PATCH, PUT, DELETE...
```

---

## 4. Quick Example: Fetch Contact Card

```typescript
import { apiGet } from '@/lib/api/client';

async function loadContactCard(contactCardId: string) {
  try {
    const contactCard = await apiGet<ContactCardDetail>(
      `/api/v1/contact-cards/${contactCardId}`
    );
    
    console.log('Contact name:', contactCard.first_name, contactCard.last_name);
    console.log('Lead status:', contactCard.lead_status);
    console.log('Open tasks:', contactCard.open_tasks);
    
    return contactCard;
  } catch (error) {
    if (error instanceof ApiError) {
      if (error.status === 404) {
        console.error('Contact card not found');
      } else if (error.status === 403) {
        console.error('Permission denied');
      } else {
        console.error('API error:', error.message);
      }
    } else {
      console.error('Network error:', error);
    }
    throw error;
  }
}
```

---

## 5. Error Handling

### Common Status Codes

- **200 OK** - Success
- **400 Bad Request** - Invalid input (check request body/params)
- **401 Unauthorized** - Missing/invalid JWT (re-authenticate)
- **403 Forbidden** - Insufficient permissions (check user role)
- **404 Not Found** - Resource doesn't exist or belongs to another company
- **409 Conflict** - Resource conflict (e.g., duplicate task)
- **429 Too Many Requests** - Rate limit exceeded (implement exponential backoff)
- **500 Internal Server Error** - Server error (retry or report)

### Example Error Handling

```typescript
try {
  const result = await apiGet('/api/v1/contact-cards/123');
} catch (error) {
  if (error instanceof ApiError) {
    switch (error.status) {
      case 401:
        // Redirect to login or refresh token
        redirectToLogin();
        break;
      case 403:
        // Show permission denied message
        showError('You don\'t have permission to access this resource');
        break;
      case 404:
        // Show not found message
        showError('Resource not found');
        break;
      case 409:
        // Handle conflict (e.g., duplicate)
        showError('This action conflicts with existing data');
        break;
      case 429:
        // Rate limited - retry after delay
        await delay(1000);
        // Retry logic...
        break;
      case 500:
        // Server error - show retry option
        showError('Server error. Please try again.');
        break;
      default:
        showError('An unexpected error occurred');
    }
  }
}
```

---

## 6. Response Format

All endpoints return responses wrapped in `APIResponse<T>`:

```typescript
interface APIResponse<T> {
  success: boolean;
  data: T;
  message?: string;
}
```

**Example Response**:

```json
{
  "success": true,
  "data": {
    "id": "contact_123",
    "first_name": "John",
    "last_name": "Doe",
    "primary_phone": "+12025551234"
  }
}
```

**Extract Data**:

```typescript
const response = await apiGet('/api/v1/contact-cards/123');
// response is already the unwrapped data (T), not the full APIResponse
console.log(response.id); // "contact_123"
console.log(response.first_name); // "John"
```

---

## 7. Common Endpoints

### Dashboard

```typescript
// Get dashboard metrics
const metrics = await apiGet('/api/v1/dashboard/metrics?company_id=YOUR_COMPANY_ID');

// Get booking rate chart data
const bookingRate = await apiGet('/api/v1/dashboard/booking-rate?start_date=2025-11-01&end_date=2025-11-30');

// Get top objections
const objections = await apiGet('/api/v1/dashboard/top-objections?limit=5');
```

### Contact Cards

```typescript
// Get contact card detail
const contactCard = await apiGet(`/api/v1/contact-cards/${contactCardId}`);
```

### Calls

```typescript
// Get missed calls
const calls = await apiGet(
  `/api/v1/dashboard/calls?status=missed&company_id=${companyId}`
);
```

### Tasks

```typescript
// List tasks
const tasks = await apiGet('/api/v1/tasks?contact_card_id=123&status=open');

// Complete task
await apiPost(`/api/v1/tasks/${taskId}/complete`);
```

---

## 8. Testing Your Setup

### 1. Test Authentication

```typescript
// Try fetching your company's data
const metrics = await apiGet('/api/v1/dashboard/metrics?company_id=YOUR_COMPANY_ID');
console.log('✅ Authentication working!', metrics);
```

### 2. Test Tenant Isolation

```typescript
// Try accessing another company's data (should fail with 403)
try {
  const otherCompanyData = await apiGet('/api/v1/dashboard/metrics?company_id=OTHER_COMPANY_ID');
} catch (error) {
  if (error.status === 403) {
    console.log('✅ Tenant isolation working!');
  }
}
```

### 3. Test Error Handling

```typescript
// Try accessing non-existent resource (should fail with 404)
try {
  const missing = await apiGet('/api/v1/contact-cards/non-existent-id');
} catch (error) {
  if (error.status === 404) {
    console.log('✅ Error handling working!');
  }
}
```

---

## 9. Next Steps

1. **Set up environment variables**:
   ```env
   NEXT_PUBLIC_API_BASE_URL=https://ottoai-backend-production.up.railway.app
   ```

2. **Implement API client** using the patterns above

3. **Start with a simple endpoint** (e.g., `GET /api/v1/dashboard/metrics`) to verify auth works

4. **Read the full integration spec**: [CSR_APP_INTEGRATION.md](./CSR_APP_INTEGRATION.md) for complete endpoint details

---

## 10. Quick Reference

| Item | Value |
|------|-------|
| **Base URL** | `process.env.NEXT_PUBLIC_API_BASE_URL` or Railway URL |
| **Auth Header** | `Authorization: Bearer <JWT_FROM_CLERK>` |
| **Content-Type** | `application/json` |
| **Response Format** | `{ success: boolean, data: T }` |
| **Error Format** | `{ error_code: string, message: string }` |

---

**For full endpoint-by-endpoint details, see [CSR_APP_INTEGRATION.md](./CSR_APP_INTEGRATION.md)**


**Date**: 2025-11-24  
**Status**: ✅ **Ready for Frontend Development**

---

## 📋 Purpose

This is a short, practical guide to get the CSR frontend team started calling Otto backend APIs within minutes. For full endpoint-by-endpoint details, see [CSR_APP_INTEGRATION.md](./CSR_APP_INTEGRATION.md).

---

## 1. Base URLs

### Staging / Production (Current)

```typescript
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://ottoai-backend-production.up.railway.app';
```

**Note**: The current backend is hosted on Railway. A dedicated staging environment URL will be provided later.

**Environment Variable**:
- `NEXT_PUBLIC_API_URL` - Set this in your `.env.local` file for local development or override the default Railway URL.

### Local Development

For local backend development:
```typescript
const LOCAL_API_BASE_URL = 'http://localhost:8000';
```

Set in `.env.local`:
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## 2. Authentication Pattern

### JWT from Clerk

The CSR Next.js app uses Clerk for authentication. The JWT token from Clerk must be included in all API requests.

**Getting the JWT**:

In your Next.js app, use Clerk's hooks to get the token:

```typescript
import { useAuth } from '@clerk/nextjs';

function MyComponent() {
  const { getToken } = useAuth();
  
  const fetchData = async () => {
    const token = await getToken();
    // Use token in API calls
  };
}
```

**Or in API routes/middleware**:

```typescript
import { auth } from '@clerk/nextjs';

export async function GET(request: Request) {
  const { getToken } = auth();
  const token = await getToken();
  // Use token in API calls
}
```

### Request Headers

All API requests must include:

```typescript
{
  'Authorization': `Bearer ${jwtToken}`,
  'Content-Type': 'application/json',
}
```

**Important**:
- The `company_id` and `role` are extracted from the JWT claims by the backend
- Frontend should **NOT** manually pass `X-Company-Id` header unless explicitly required by a specific endpoint
- The backend's `TenantContextMiddleware` automatically enforces tenant isolation using JWT claims

---

## 3. Example API Client

Here's a minimal TypeScript example showing how to make authenticated API calls:

```typescript
// lib/api/client.ts

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'https://ottoai-backend-production.up.railway.app';

interface ApiError {
  status: number;
  message: string;
  error_code?: string;
}

class ApiError extends Error {
  constructor(message: string, public status: number, public error_code?: string) {
    super(message);
    this.name = 'ApiError';
  }
}

/**
 * Get JWT token from Clerk
 */
async function getAuthToken(): Promise<string | null> {
  // In client components, use useAuth hook
  // In server components/API routes, use auth() from @clerk/nextjs/server
  if (typeof window !== 'undefined') {
    // Client-side: use Clerk React hooks
    const { useAuth } = await import('@clerk/nextjs');
    // Implementation depends on your setup
    return null; // Replace with actual token retrieval
  } else {
    // Server-side: use Clerk server SDK
    const { auth } = await import('@clerk/nextjs/server');
    const { getToken } = auth();
    return await getToken();
  }
}

/**
 * Make an authenticated GET request
 */
export async function apiGet<T>(
  path: string,
  params?: Record<string, any>
): Promise<T> {
  const token = await getAuthToken();
  
  if (!token) {
    throw new ApiError('Authentication required', 401);
  }
  
  // Build URL with query params
  const url = new URL(`${API_BASE_URL}${path}`);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        url.searchParams.append(key, String(value));
      }
    });
  }
  
  const response = await fetch(url.toString(), {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });
  
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ message: 'Unknown error' }));
    throw new ApiError(
      errorData.message || `Request failed: ${response.status}`,
      response.status,
      errorData.error_code
    );
  }
  
  const json = await response.json();
  // Handle APIResponse wrapper
  return json.data !== undefined ? json.data : json;
}

/**
 * Make an authenticated POST request
 */
export async function apiPost<T>(
  path: string,
  body?: any
): Promise<T> {
  const token = await getAuthToken();
  
  if (!token) {
    throw new ApiError('Authentication required', 401);
  }
  
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ message: 'Unknown error' }));
    throw new ApiError(
      errorData.message || `Request failed: ${response.status}`,
      response.status,
      errorData.error_code
    );
  }
  
  const json = await response.json();
  return json.data !== undefined ? json.data : json;
}

// Similar for PATCH, PUT, DELETE...
```

---

## 4. Quick Example: Fetch Contact Card

```typescript
import { apiGet } from '@/lib/api/client';

async function loadContactCard(contactCardId: string) {
  try {
    const contactCard = await apiGet<ContactCardDetail>(
      `/api/v1/contact-cards/${contactCardId}`
    );
    
    console.log('Contact name:', contactCard.first_name, contactCard.last_name);
    console.log('Lead status:', contactCard.lead_status);
    console.log('Open tasks:', contactCard.open_tasks);
    
    return contactCard;
  } catch (error) {
    if (error instanceof ApiError) {
      if (error.status === 404) {
        console.error('Contact card not found');
      } else if (error.status === 403) {
        console.error('Permission denied');
      } else {
        console.error('API error:', error.message);
      }
    } else {
      console.error('Network error:', error);
    }
    throw error;
  }
}
```

---

## 5. Error Handling

### Common Status Codes

- **200 OK** - Success
- **400 Bad Request** - Invalid input (check request body/params)
- **401 Unauthorized** - Missing/invalid JWT (re-authenticate)
- **403 Forbidden** - Insufficient permissions (check user role)
- **404 Not Found** - Resource doesn't exist or belongs to another company
- **409 Conflict** - Resource conflict (e.g., duplicate task)
- **429 Too Many Requests** - Rate limit exceeded (implement exponential backoff)
- **500 Internal Server Error** - Server error (retry or report)

### Example Error Handling

```typescript
try {
  const result = await apiGet('/api/v1/contact-cards/123');
} catch (error) {
  if (error instanceof ApiError) {
    switch (error.status) {
      case 401:
        // Redirect to login or refresh token
        redirectToLogin();
        break;
      case 403:
        // Show permission denied message
        showError('You don\'t have permission to access this resource');
        break;
      case 404:
        // Show not found message
        showError('Resource not found');
        break;
      case 409:
        // Handle conflict (e.g., duplicate)
        showError('This action conflicts with existing data');
        break;
      case 429:
        // Rate limited - retry after delay
        await delay(1000);
        // Retry logic...
        break;
      case 500:
        // Server error - show retry option
        showError('Server error. Please try again.');
        break;
      default:
        showError('An unexpected error occurred');
    }
  }
}
```

---

## 6. Response Format

All endpoints return responses wrapped in `APIResponse<T>`:

```typescript
interface APIResponse<T> {
  success: boolean;
  data: T;
  message?: string;
}
```

**Example Response**:

```json
{
  "success": true,
  "data": {
    "id": "contact_123",
    "first_name": "John",
    "last_name": "Doe",
    "primary_phone": "+12025551234"
  }
}
```

**Extract Data**:

```typescript
const response = await apiGet('/api/v1/contact-cards/123');
// response is already the unwrapped data (T), not the full APIResponse
console.log(response.id); // "contact_123"
console.log(response.first_name); // "John"
```

---

## 7. Common Endpoints

### Dashboard

```typescript
// Get dashboard metrics
const metrics = await apiGet('/api/v1/dashboard/metrics?company_id=YOUR_COMPANY_ID');

// Get booking rate chart data
const bookingRate = await apiGet('/api/v1/dashboard/booking-rate?start_date=2025-11-01&end_date=2025-11-30');

// Get top objections
const objections = await apiGet('/api/v1/dashboard/top-objections?limit=5');
```

### Contact Cards

```typescript
// Get contact card detail
const contactCard = await apiGet(`/api/v1/contact-cards/${contactCardId}`);
```

### Calls

```typescript
// Get missed calls
const calls = await apiGet(
  `/api/v1/dashboard/calls?status=missed&company_id=${companyId}`
);
```

### Tasks

```typescript
// List tasks
const tasks = await apiGet('/api/v1/tasks?contact_card_id=123&status=open');

// Complete task
await apiPost(`/api/v1/tasks/${taskId}/complete`);
```

---

## 8. Testing Your Setup

### 1. Test Authentication

```typescript
// Try fetching your company's data
const metrics = await apiGet('/api/v1/dashboard/metrics?company_id=YOUR_COMPANY_ID');
console.log('✅ Authentication working!', metrics);
```

### 2. Test Tenant Isolation

```typescript
// Try accessing another company's data (should fail with 403)
try {
  const otherCompanyData = await apiGet('/api/v1/dashboard/metrics?company_id=OTHER_COMPANY_ID');
} catch (error) {
  if (error.status === 403) {
    console.log('✅ Tenant isolation working!');
  }
}
```

### 3. Test Error Handling

```typescript
// Try accessing non-existent resource (should fail with 404)
try {
  const missing = await apiGet('/api/v1/contact-cards/non-existent-id');
} catch (error) {
  if (error.status === 404) {
    console.log('✅ Error handling working!');
  }
}
```

---

## 9. Next Steps

1. **Set up environment variables**:
   ```env
   NEXT_PUBLIC_API_BASE_URL=https://ottoai-backend-production.up.railway.app
   ```

2. **Implement API client** using the patterns above

3. **Start with a simple endpoint** (e.g., `GET /api/v1/dashboard/metrics`) to verify auth works

4. **Read the full integration spec**: [CSR_APP_INTEGRATION.md](./CSR_APP_INTEGRATION.md) for complete endpoint details

---

## 10. Quick Reference

| Item | Value |
|------|-------|
| **Base URL** | `process.env.NEXT_PUBLIC_API_BASE_URL` or Railway URL |
| **Auth Header** | `Authorization: Bearer <JWT_FROM_CLERK>` |
| **Content-Type** | `application/json` |
| **Response Format** | `{ success: boolean, data: T }` |
| **Error Format** | `{ error_code: string, message: string }` |

---

**For full endpoint-by-endpoint details, see [CSR_APP_INTEGRATION.md](./CSR_APP_INTEGRATION.md)**

