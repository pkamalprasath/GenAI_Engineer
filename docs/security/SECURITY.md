# Security Implementation Guide

## Overview

This document details the security implementation of the Slack Bot Assistant, following industry best practices and OWASP guidelines.

## Authentication & Authorization

### Request Verification
**Implementation**: `src/slack/middleware/auth.py`

```python
# Slack Bolt automatically verifies:
- HMAC-SHA256 request signatures
- Timestamp freshness (5-minute window)
- Signing secret validation
```

**Manual Verification** (if needed):
```python
from src.utils.security import verify_slack_signature

is_valid = verify_slack_signature(
    signing_secret=settings.slack_signing_secret,
    timestamp=headers['X-Slack-Request-Timestamp'],
    body=raw_body,
    signature=headers['X-Slack-Signature']
)
```

### Bot Loop Prevention
```python
# In auth middleware
if event.get("bot_id"):
    logger.debug("Ignoring message from bot")
    return BoltResponse(status=200)
```

## Rate Limiting

### Implementation
**File**: `src/slack/middleware/rate_limit.py`

**Configuration**:
- User-level: 10 requests/minute
- Channel-level: 30 requests/minute
- Algorithm: Token bucket

**Development**: In-memory storage
**Production**: Redis-backed distributed rate limiting

### Usage
```python
from src.slack.middleware.rate_limit import reset_user_rate_limit

# Manually reset if needed
reset_user_rate_limit("U123ABC456")
```

## Input Validation

### Validation Functions
**File**: `src/utils/validators.py`

```python
from src.utils.validators import (
    validate_channel_id,  # Format: C1234567890
    validate_user_id,     # Format: U1234567890
    validate_text_length, # Max: 4000 chars
    sanitize_text,        # Remove HTML, control chars
    detect_injection_attempt  # SQL, XSS, command injection
)
```

### Injection Prevention
```python
# Always sanitize user input
sanitized = sanitize_text(user_input)

# Detect injection attempts
if detect_injection_attempt(user_input):
    logger.warning(f"Injection attempt detected: {user_id}")
    # Log and reject
```

## Token Management

### Storage
**Development**: `.env` file (gitignored)
```bash
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
ANTHROPIC_API_KEY=sk-ant-...
```

**Production**: Secrets Manager
- AWS Secrets Manager
- HashiCorp Vault
- Azure Key Vault

### Token Security
```python
from src.utils.security import mask_token, validate_token_format

# Always mask tokens in logs
logger.info(f"Using token: {mask_token(token)}")

# Validate format before use
if not validate_token_format(token, "bot"):
    raise TokenError("Invalid token format")
```

### Token Rotation
**File**: `scripts/rotate_tokens.py`

```python
from src.utils.security import check_token_expiry

should_rotate, days_left = check_token_expiry(
    token_created_at=datetime(2026, 1, 1),
    rotation_days=7
)

if should_rotate:
    # Rotate token with zero-downtime
    # 1. Generate new token
    # 2. Update configuration
    # 3. Gracefully restart
    # 4. Revoke old token
```

## Data Protection

### Sensitive Data Handling
```python
from src.utils.security import sanitize_for_logging

# Never log sensitive data
log_data = sanitize_for_logging({
    "user_id": "U123",
    "token": "xoxb-secret",  # Will be masked
    "message": "Hello"
})

logger.info("Request processed", extra=log_data)
```

### PII Protection
- User IDs: Logged but hashed in analytics
- Messages: Stored encrypted at rest
- Tokens: Never logged in plaintext
- Memory files: Gitignored, encrypted in production

## Network Security

### TLS/SSL
**Development**: Socket Mode (WebSocket over TLS)
**Production**: HTTPS with TLS 1.3

### Security Headers
```python
from src.utils.security import get_security_headers

headers = get_security_headers()
# X-Frame-Options: DENY
# X-Content-Type-Options: nosniff
# Strict-Transport-Security: ...
```

## Error Handling

### Secure Error Responses
```python
# Never expose internal errors to users
try:
    result = dangerous_operation()
except Exception as e:
    logger.exception(f"Internal error: {e}")  # Log details
    return "An error occurred. Please try again."  # Generic message
```

### Error Logging
- Technical details: Server logs only
- User-facing: Generic, helpful messages
- Stack traces: Never sent to client

## Access Control

### OAuth Scopes
**Minimum Required Scopes**:
```yaml
bot_scopes:
  - chat:write          # Post messages
  - channels:read       # Read channel info
  - channels:history    # Read message history
  - users:read          # Read user info
  - reactions:write     # Add reactions
  - commands            # Slash commands
```

**Avoid**:
- `admin` - Too broad
- `users:write` - Can modify users
- `files:write` - Unnecessary for most bots

### User Authorization
```python
# In middleware or listeners
def is_admin(user_id: str) -> bool:
    """Check if user has admin privileges."""
    admin_users = settings.admin_user_ids.split(",")
    return user_id in admin_users

# Use for sensitive commands
if not is_admin(user_id):
    return "This command requires admin privileges."
```

## Monitoring & Incident Response

### Security Monitoring
```python
# Log security events
logger.warning(
    "Security event detected",
    extra={
        "event_type": "rate_limit_exceeded",
        "user_id": user_id,
        "ip_address": request_ip,
        "timestamp": datetime.now()
    }
)
```

### Alert Thresholds
- Rate limit violations: >10/hour from single user
- Authentication failures: >5/minute
- Injection attempts: Any detected
- Unusual patterns: Sudden traffic spikes

### Incident Response
1. **Detect**: Automated monitoring alerts
2. **Contain**: Rate limiting, IP blocking
3. **Investigate**: Review logs, identify scope
4. **Remediate**: Patch vulnerability, rotate tokens
5. **Document**: Post-mortem, lessons learned

## Security Checklist

### Pre-Deployment
- [ ] All tokens stored securely (not in code)
- [ ] Rate limiting configured
- [ ] Input validation on all endpoints
- [ ] Error messages don't leak information
- [ ] Security headers configured
- [ ] TLS/HTTPS enabled
- [ ] Logging excludes sensitive data
- [ ] OAuth scopes minimized

### Regular Maintenance
- [ ] Update dependencies monthly
- [ ] Rotate tokens weekly
- [ ] Review access logs weekly
- [ ] Security audit quarterly
- [ ] Penetration testing annually

## Vulnerability Reporting

If you discover a security vulnerability:
1. **Do NOT** open a public issue
2. Email: security@yourcompany.com
3. Include:
   - Vulnerability description
   - Steps to reproduce
   - Impact assessment
4. We will respond within 48 hours

## Compliance

### GDPR
- User data: Stored with consent
- Right to deletion: Implemented via API
- Data portability: Export via `/export` command
- Privacy policy: Available at /privacy

### SOC 2
- Audit logging: All operations logged
- Access control: Role-based
- Encryption: At rest and in transit
- Monitoring: 24/7 automated

---

**Security is a continuous process, not a one-time implementation.**
