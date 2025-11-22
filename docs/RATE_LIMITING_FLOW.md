# Rate Limiting Flow Diagram

## Request Processing Flow with Rate Limiting

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Client Request                                │
│                              ↓                                       │
│                    FastAPI Application                               │
└─────────────────────────────────────────────────────────────────────┘
                               ↓
                    ┌──────────────────────┐
                    │  slowapi Middleware   │
                    │  (get_remote_address) │
                    └──────────────────────┘
                               ↓
                    ┌──────────────────────┐
                    │   Check Rate Limit    │
                    │   Based on Client IP  │
                    └──────────────────────┘
                               ↓
                    ┌──────────────────────┐
                    │  Within Limit?       │
                    └──────────────────────┘
                          /          \
                        YES           NO
                        /              \
                       ↓                ↓
        ┌─────────────────────┐   ┌──────────────────────────┐
        │  Increment Counter   │   │ Raise RateLimitExceeded  │
        └─────────────────────┘   └──────────────────────────┘
                   ↓                          ↓
        ┌─────────────────────┐   ┌──────────────────────────┐
        │ Process Request      │   │ Custom Exception Handler │
        │ (Execute Endpoint)   │   │ Returns 429 Response     │
        └─────────────────────┘   └──────────────────────────┘
                   ↓                          ↓
        ┌─────────────────────┐   ┌──────────────────────────┐
        │ Add Rate Limit       │   │ {                        │
        │ Headers to Response: │   │   "error": "Rate limit   │
        │                      │   │     exceeded",           │
        │ X-RateLimit-Limit    │   │   "message": "Too many   │
        │ X-RateLimit-Remaining│   │     requests...",        │
        │ X-RateLimit-Reset    │   │   "detail": "..."        │
        └─────────────────────┘   │ }                        │
                   ↓                │ Retry-After: 3600        │
        ┌─────────────────────┐   └──────────────────────────┘
        │ Return Response      │                ↓
        │ (200/404/etc)        │   ┌──────────────────────────┐
        └─────────────────────┘   │ Return 429 Response      │
                   ↓                └──────────────────────────┘
                   ↓                          ↓
        ┌──────────────────────────────────────────────────┐
        │              Client Receives Response             │
        └──────────────────────────────────────────────────┘
```

## Rate Limit Configuration by Endpoint

```
┌─────────────────────────────────────────────────────────────────┐
│                    Endpoint Rate Limits                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  GET /                             200 requests/hour             │
│  ├── Index page listing forecasts                               │
│  └── Generous limit for browsing                                │
│                                                                  │
│  GET /forecasts/{id}               60 requests/hour              │
│  ├── HTML forecast viewer                                       │
│  └── Moderate limit for viewing                                 │
│                                                                  │
│  GET /api/forecasts/latest         100 requests/hour            │
│  ├── Latest forecast JSON API                                   │
│  └── Moderate limit for API consumers                           │
│                                                                  │
│  GET /api/forecasts/{id}           60 requests/hour             │
│  ├── Specific forecast JSON API                                 │
│  └── Moderate limit for details                                 │
│                                                                  │
│  GET /assets/{id}/{path}           200 requests/hour            │
│  ├── Static assets (images, CSS, etc.)                          │
│  └── Higher limit for page resources                            │
│                                                                  │
│  GET /health                       UNLIMITED                     │
│  ├── Health check endpoint                                      │
│  └── No limit for monitoring systems                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Storage Architecture

### Development (Current)
```
┌────────────────────────────────────────────────────┐
│              In-Memory Storage                     │
│                                                     │
│  ┌──────────────────────────────────────────┐     │
│  │  IP Address → Request Count Map          │     │
│  │                                           │     │
│  │  192.168.1.100 → {                       │     │
│  │    "/api/forecasts": {                   │     │
│  │      count: 45,                          │     │
│  │      reset_time: 1728691200              │     │
│  │    },                                     │     │
│  │    "/forecasts/{id}": {                  │     │
│  │      count: 12,                          │     │
│  │      reset_time: 1728691200              │     │
│  │    }                                      │     │
│  │  }                                        │     │
│  └──────────────────────────────────────────┘     │
│                                                     │
│  Note: Per-process storage                         │
│        Not suitable for multiple workers           │
└────────────────────────────────────────────────────┘
```

### Production (Recommended)
```
┌────────────────────────────────────────────────────┐
│         Redis-Based Shared Storage                 │
│                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │
│  │  Worker 1    │  │  Worker 2    │  │  Worker N   │ │
│  │              │  │              │  │             │ │
│  │  slowapi     │  │  slowapi     │  │  slowapi    │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬─────┘ │
│         │                 │                  │       │
│         └─────────────────┼──────────────────┘       │
│                           ↓                          │
│              ┌─────────────────────────┐             │
│              │     Redis Server        │             │
│              │  (Shared Rate Limits)   │             │
│              │                         │             │
│              │  Key: IP:endpoint       │             │
│              │  Value: count, TTL      │             │
│              └─────────────────────────┘             │
│                                                       │
│  Benefits:                                            │
│  ✓ Shared state across all workers                   │
│  ✓ Consistent rate limiting                          │
│  ✓ Automatic TTL/expiration                          │
│  ✓ Production-ready scalability                      │
└────────────────────────────────────────────────────┘
```

## Attack Mitigation Scenarios

### Scenario 1: Rapid API Scraping
```
Attacker: Automated script
Target: /api/forecasts/{id}
Rate Limit: 60 requests/hour

Request 1-60:  ✅ 200 OK (with rate limit headers)
Request 61:    ❌ 429 Too Many Requests
Request 62+:   ❌ 429 Too Many Requests
After 1 hour:  ✅ Rate limit resets, requests allowed again
```

### Scenario 2: Asset Flooding
```
Attacker: Download bot
Target: /assets/{id}/chart.png
Rate Limit: 200 requests/hour

Request 1-200:  ✅ 200 OK (images served)
Request 201:    ❌ 429 Too Many Requests
Request 202+:   ❌ 429 Too Many Requests
Retry-After:    3600 seconds (1 hour)
```

### Scenario 3: Legitimate User
```
User: Regular browser
Target: Multiple endpoints
Rate Limits: Various

GET /                        ✅ 200 OK (1/200)
GET /forecasts/{id}          ✅ 200 OK (1/60)
GET /assets/{id}/chart.png   ✅ 200 OK (1/200)
GET /assets/{id}/style.css   ✅ 200 OK (2/200)
GET /api/forecasts/{id}      ✅ 200 OK (1/60)

Normal usage stays well within limits
```

## Rate Limit Headers Example

### Successful Request
```http
HTTP/1.1 200 OK
Content-Type: application/json
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1728691200

{
  "generated_time": "2025-10-11T12:00:00Z",
  "location": "Oahu"
}
```

### Rate Limit Exceeded
```http
HTTP/1.1 429 Too Many Requests
Content-Type: application/json
Retry-After: 3600
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1728691200

{
  "error": "Rate limit exceeded",
  "message": "Too many requests. Please try again later.",
  "detail": "60 per 1 hour"
}
```

## Implementation Checklist

- [x] Install slowapi dependency
- [x] Initialize Limiter with IP-based key function
- [x] Configure in-memory storage for development
- [x] Add rate limiter to FastAPI app state
- [x] Register exception handler for RateLimitExceeded
- [x] Apply @limiter.limit decorators to endpoints
- [x] Add Request parameter to all rate-limited endpoints
- [x] Exclude health endpoint from rate limiting
- [x] Create custom 429 response handler
- [x] Add X-RateLimit headers to responses
- [x] Write comprehensive tests
- [x] Document production Redis configuration

## Testing Strategy

### Unit Tests
```python
# Test 1: Verify limiter is initialized
assert app.state.limiter is not None

# Test 2: Verify endpoints accept Request parameter
response = client.get("/api/forecasts/{id}")
assert response.status_code == 200

# Test 3: Verify health endpoint has no rate limit
for i in range(10):
    response = client.get("/health")
    assert response.status_code == 200

# Test 4: Verify exception handler is registered
assert RateLimitExceeded in app.exception_handlers
```

### Integration Tests (Manual)
```bash
# Start server
uvicorn src.web.app:app --reload

# Test rate limiting
for i in {1..70}; do
  curl -i http://localhost:8000/api/forecasts/forecast_20251011_120000
done

# Expected:
# Requests 1-60: 200 OK with decreasing X-RateLimit-Remaining
# Requests 61+:  429 Too Many Requests with Retry-After header
```

## Security Best Practices

1. **IP-Based Tracking**: Uses client IP address for rate limiting
2. **Per-Endpoint Limits**: Different limits for different endpoint types
3. **Clear Error Messages**: Returns actionable 429 responses
4. **Retry-After Headers**: Tells clients when to retry
5. **Health Check Exception**: Monitoring endpoints unrestricted
6. **Production Scalability**: Redis backend for multi-worker deployments
7. **Configurable Limits**: Easy to adjust via environment variables

## Monitoring Recommendations

### Metrics to Track
1. **Rate Limit Hit Rate**: % of requests hitting rate limits
2. **Top Limited IPs**: Identify repeat offenders
3. **Endpoint Hotspots**: Which endpoints hit limits most
4. **False Positives**: Legitimate users being rate limited
5. **Attack Patterns**: Coordinated attacks across IPs

### Alert Conditions
- High rate limit hit rate (>10% of requests)
- Single IP hitting limits repeatedly
- Sudden spike in 429 responses
- Legitimate services being blocked

### Log Examples
```python
# Log rate limit exceeded events
logger.warning(
    f"Rate limit exceeded: IP={client_ip} endpoint={endpoint} "
    f"limit={limit} window={window}"
)

# Log potential attacks
if hit_count > threshold:
    logger.critical(
        f"Potential DoS attack: IP={client_ip} hits={hit_count} "
        f"timeframe={timeframe}"
    )
```
