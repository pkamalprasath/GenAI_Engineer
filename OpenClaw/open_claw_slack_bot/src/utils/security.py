"""
Security Utilities -- HMAC Verification, Token Management, and Rate Limiting
==============================================================================

WHY THIS FILE IS REQUIRED:
    A Slack bot is an internet-facing service that receives HTTP requests from
    Slack's servers and processes commands from potentially untrusted users.
    Without dedicated security utilities:
      - Any HTTP client could impersonate Slack and inject malicious payloads,
        because the bot would have no way to verify request authenticity.
      - Developers would inevitably log full API tokens during debugging,
        creating a credential-leakage risk in log files and monitoring systems.
      - There would be no rate limiting, allowing a single user or automated
        script to overwhelm the bot with requests and exhaust API quotas.
      - Random identifiers would be generated with Python's `random` module
        (which is NOT cryptographically secure), making session tokens and
        API keys guessable.
    This module centralizes all security-sensitive operations so they are
    implemented correctly once and reused everywhere, following the principle
    of "don't roll your own crypto."

PROGRAM LOGIC:
    1. verify_slack_signature() re-implements Slack's request verification
       protocol: it validates the timestamp (anti-replay), constructs the
       HMAC-SHA256 base string, computes the signature, and compares it in
       constant time.
    2. mask_token() and validate_token_format() provide safe token handling
       for logging and configuration validation.
    3. check_token_expiry() monitors token age to trigger proactive rotation
       before tokens expire.
    4. RateLimiter implements a fixed-window rate limiter using an in-memory
       dictionary, suitable for single-process deployments.
    5. generate_secure_id() and generate_api_key() produce cryptographically
       random strings using the `secrets` module.
    6. sanitize_for_logging() recursively redacts sensitive fields from
       dictionaries before they are written to log files.
    7. get_security_headers() returns OWASP-recommended HTTP response headers.
    8. validate_secret_strength() checks that secrets meet minimum entropy
       requirements.

WHY THIS APPROACH:
    - HMAC-SHA256 for signature verification: this is Slack's documented
      protocol.  HMAC provides both integrity (the request body has not been
      tampered with) and authenticity (only someone who knows the signing
      secret could have produced the signature).
    - Constant-time comparison (hmac.compare_digest): prevents timing attacks
      where an attacker measures response latency to deduce the correct
      signature byte by byte.
    - In-memory rate limiter: Redis-backed rate limiting would be more robust
      for multi-instance deployments, but adds an infrastructure dependency.
      The in-memory approach is chosen for simplicity and zero-dependency
      operation, with a clear upgrade path documented in the class docstring.
    - secrets module for randomness: Python's `random` module uses a
      Mersenne Twister PRNG that is predictable after observing 624 outputs.
      The `secrets` module delegates to the OS CSPRNG (e.g., /dev/urandom),
      which is suitable for security-sensitive use.

SECURITY CONSIDERATIONS:
    - verify_slack_signature uses hmac.compare_digest (constant-time) to
      prevent timing side-channel attacks.
    - mask_token ensures that full tokens never appear in logs, even if a
      developer accidentally passes one to a logging call.
    - sanitize_for_logging recursively redacts any dict key containing
      "token", "password", "secret", "api_key", "authorization",
      "credential", or "private_key" (case-insensitive substring match).
    - generate_secure_id and generate_api_key use secrets.token_urlsafe,
      which draws from the OS CSPRNG.
    - RateLimiter logs all rate-limit violations at WARNING level for
      security monitoring.

RELATIONSHIP TO OTHER FILES:
    USED BY:
        - src/slack/middleware/auth.py       (verify_slack_signature)
        - src/slack/middleware/rate_limit.py  (RateLimiter)
    USES:
        - src/utils/exceptions.py  (SecurityValidationError)
        - src/utils/logger.py      (get_logger for security event logging)
        - Python stdlib: hmac, hashlib, time, secrets, datetime
    RELATED:
        - src/utils/validators.py  (validate_timestamp provides similar
          anti-replay logic at the application layer; this module provides
          it at the HTTP/transport layer)
"""

import hmac
import hashlib
import time
import secrets
from typing import Optional
from datetime import datetime

from src.utils.exceptions import SecurityValidationError
from src.utils.logger import get_logger

# WHY a module-level logger: security events (signature failures, rate-limit
# violations, token rotation warnings) must always be logged, regardless of
# which caller triggers them.  A module-level logger scoped to this file's
# __name__ ensures consistent log output and makes it easy to route all
# security logs to a dedicated handler in the YAML config.
logger = get_logger(__name__)


# ==============================================================================
# Request Signature Verification
# ==============================================================================
# WHY verify signatures at all: without verification, any HTTP client on the
# internet could POST fake events to the bot's endpoint, impersonating Slack.
# Signature verification is the ONLY way to prove that a request genuinely
# originated from Slack's infrastructure.
# ==============================================================================


def verify_slack_signature(signing_secret: str, timestamp: str, body: str, signature: str) -> bool:
    """
    Verify that an incoming HTTP request was genuinely sent by Slack.

    HOW it works:
        1. Parses the timestamp string to an integer and checks that it is
           within a 5-minute window of the current server time (anti-replay).
        2. Constructs the HMAC base string in Slack's documented format:
           "v0:{timestamp}:{raw_request_body}".
        3. Computes HMAC-SHA256 of that base string using the app's signing
           secret as the key.
        4. Prepends "v0=" to the hex digest to match Slack's signature format.
        5. Compares the computed signature against the provided signature
           using hmac.compare_digest (constant-time comparison).

    WHY it is implemented this way:
        - The 5-minute timestamp window prevents replay attacks: even if an
          attacker captures a valid signed request, they cannot re-send it
          after the window closes.
        - HMAC-SHA256 provides both integrity (the body has not been modified)
          and authenticity (only the holder of the signing secret can produce
          a valid signature).
        - hmac.compare_digest is used instead of == because Python's ==
          operator on strings short-circuits on the first differing byte,
          leaking timing information that an attacker could exploit to
          reconstruct the correct signature incrementally.
        - Logging the failure (but NOT the expected signature) at WARNING
          level enables security monitoring without leaking sensitive data.
        - Although Slack Bolt handles this automatically, implementing it
          explicitly is valuable for custom middleware, webhook endpoints,
          and educational understanding.

    Args:
        signing_secret: The app's signing secret from the Slack dashboard
                        (Settings > Basic Information > App Credentials).
        timestamp: The value of the X-Slack-Request-Timestamp header.
        body: The raw (unparsed) HTTP request body as a string.
        signature: The value of the X-Slack-Signature header (e.g.,
                   "v0=abc123...").

    Returns:
        True if the signature is valid, False otherwise.

    Raises:
        SecurityValidationError: If the timestamp is malformed or too old.

    Reference:
        https://api.slack.com/authentication/verifying-requests-from-slack
    """
    # WHY validate timestamp first: if the timestamp is stale, there is no
    # point computing the HMAC (which is more expensive).  Early rejection
    # also defends against replay attacks before any crypto work is done.
    try:
        request_time = int(timestamp)
        current_time = int(time.time())

        # WHY 5 minutes (300 seconds): this is Slack's officially documented
        # maximum acceptable age.  A tighter window (e.g., 30 seconds) would
        # increase false rejections due to network latency and clock drift.
        if abs(current_time - request_time) > 60 * 5:
            raise SecurityValidationError(
                "Request timestamp is too old",
                details={"age_seconds": abs(current_time - request_time)},
            )
    except ValueError:
        # WHY catch ValueError specifically: int() raises ValueError for
        # non-numeric strings.  A malformed timestamp is a strong signal of
        # a forged request, so we raise SecurityValidationError.
        raise SecurityValidationError("Invalid timestamp format")

    # WHY this exact format: Slack's documentation specifies that the base
    # string is "v0:{timestamp}:{body}" with no additional separators or
    # encoding.  Any deviation produces a different HMAC output.
    sig_basestring = f"v0:{timestamp}:{body}"

    # WHY encode both key and message: HMAC operates on bytes, not strings.
    # Using .encode() produces UTF-8 bytes, matching Slack's implementation.
    computed_signature = (
        "v0="
        + hmac.new(
            key=signing_secret.encode(), msg=sig_basestring.encode(), digestmod=hashlib.sha256
        ).hexdigest()
    )

    # WHY hmac.compare_digest instead of ==: the == operator on strings
    # short-circuits on the first differing character, making the comparison
    # take less time for signatures that differ early.  An attacker can
    # measure this timing difference across many requests to reconstruct the
    # correct signature one byte at a time (a "timing attack").
    # hmac.compare_digest always takes the same amount of time regardless of
    # where the strings differ.
    if not hmac.compare_digest(computed_signature, signature):
        # WHY log at WARNING (not ERROR): a single invalid signature could be
        # a misconfigured integration, not necessarily an attack.  Sustained
        # failures at high volume would warrant escalation to ERROR via
        # monitoring alerts.
        logger.warning("Invalid request signature detected", extra={"timestamp": timestamp})
        return False

    return True


# ==============================================================================
# Token Management
# ==============================================================================
# WHY centralize token operations: tokens (bot tokens, app tokens, API keys)
# are the most sensitive data in the application.  Centralizing masking,
# format validation, and expiry checking ensures consistent handling and
# reduces the surface area for credential-leakage bugs.
# ==============================================================================


def mask_token(token: str, visible_chars: int = 4) -> str:
    """
    Mask a token so it can be safely included in log output.

    HOW it works:
        Shows only the first `visible_chars` characters of the token and
        replaces the rest with asterisks.  If the token is shorter than or
        equal to `visible_chars`, the entire token is replaced with asterisks
        to prevent full exposure.

    WHY it is implemented this way:
        - Showing the first few characters (e.g., "xoxb") helps developers
          identify the token type during debugging (bot token vs. app token
          vs. user token) without exposing the secret portion.
        - Replacing short tokens entirely with asterisks prevents accidental
          full exposure of tokens that are unusually short (e.g., during
          testing with stub values).
        - This function is used by sanitize_for_logging() to automatically
          redact tokens in structured log output.

    Args:
        token: The full token string.
        visible_chars: Number of leading characters to keep visible (default: 4).

    Returns:
        Masked token string (e.g., "xoxb****************************").
    """
    # WHY this guard: if the token is very short (e.g., a test stub like "abc"),
    # showing any characters would effectively expose the entire token.
    if len(token) <= visible_chars:
        return "*" * len(token)

    return token[:visible_chars] + "*" * (len(token) - visible_chars)


def validate_token_format(token: str, token_type: str) -> bool:
    """
    Check whether a Slack token has the expected prefix and minimum length.

    HOW it works:
        Checks the token string's prefix ("xoxb-" for bot tokens, "xapp-"
        for app-level tokens) and ensures minimum length > 10 characters.

    WHY it is implemented this way:
        - Slack assigns predictable prefixes to each token type.  Checking
          the prefix catches the most common misconfiguration: pasting a
          user token (xoxp-) where a bot token (xoxb-) is expected, or
          vice versa.
        - The minimum length of 10 is a heuristic to reject obviously
          truncated or placeholder tokens (e.g., "xoxb-test") while
          accepting real tokens which are ~50+ characters long.
        - Returning bool (not raising) lets callers decide the severity:
          src/app.py treats a format failure as a fatal ConfigurationError,
          while a health-check endpoint might treat it as a warning.

    Args:
        token: The token string to validate.
        token_type: One of "bot" or "app", indicating the expected token type.

    Returns:
        True if the token matches the expected format, False otherwise.
    """
    # WHY explicit prefix checks: Slack's token prefixes are stable and
    # documented.  A token with the wrong prefix will always fail
    # authentication, so catching it here saves an API round-trip and
    # produces a clear diagnostic message.
    if token_type == "bot":
        return token.startswith("xoxb-") and len(token) > 10
    elif token_type == "app":
        return token.startswith("xapp-") and len(token) > 10
    else:
        # WHY return False for unknown types: failing closed is safer than
        # failing open.  An unrecognized token_type is likely a caller bug.
        return False


def check_token_expiry(token_created_at: datetime, rotation_days: int = 7) -> tuple[bool, int]:
    """
    Determine whether a token should be rotated based on its age.

    HOW it works:
        Computes the difference between now and the token's creation
        timestamp in days.  If the age meets or exceeds `rotation_days`,
        returns (True, negative_days_until_expiry) and logs a warning.

    WHY it is implemented this way:
        - Proactive rotation before a token expires avoids downtime caused
          by expired credentials.  The default of 7 days provides a generous
          rotation cadence for development; production deployments may use
          shorter intervals.
        - Returning a tuple (should_rotate, days_until_expiry) gives callers
          both the decision and the urgency.  A negative days_until_expiry
          indicates the token is already overdue for rotation.
        - Logging at WARNING level ensures that token-rotation reminders
          appear in standard log monitoring without requiring a separate
          alerting mechanism.

    Args:
        token_created_at: The datetime when the token was issued or last
                          rotated.
        rotation_days: Maximum age in days before rotation is recommended
                       (default: 7).

    Returns:
        A tuple of (should_rotate: bool, days_until_expiry: int).
        days_until_expiry is negative if the token is past due.
    """
    age = datetime.now() - token_created_at
    days_old = age.days

    should_rotate = days_old >= rotation_days
    # WHY compute days_until_expiry: gives callers a numeric urgency signal.
    # Positive means "you have N days left"; negative means "overdue by N days."
    days_until_expiry = rotation_days - days_old

    if should_rotate:
        # WHY log at WARNING: token rotation is not an error, but ignoring it
        # long enough will become one.  WARNING is the appropriate severity
        # for "action recommended but not yet critical."
        logger.warning(
            f"Token rotation recommended (age: {days_old} days)",
            extra={"days_old": days_old, "rotation_days": rotation_days},
        )

    return should_rotate, days_until_expiry


# ==============================================================================
# Rate Limiting Utilities
# ==============================================================================
# WHY rate limiting: without it, a single user (or automated script) could
# send hundreds of messages per second, exhausting the bot's Slack API quota,
# consuming LLM tokens, and degrading service for all other users.  Rate
# limiting is a fundamental availability control.
# ==============================================================================


class RateLimiter:
    """
    Fixed-window, in-memory rate limiter for single-process deployments.

    HOW it works:
        Maintains a dictionary mapping rate-limit keys (e.g., user IDs) to
        buckets containing a request count and a window-expiry timestamp.
        On each is_allowed() call, it either creates a new bucket, resets
        an expired bucket, increments the counter, or rejects the request
        if the counter has reached the maximum.

    WHY it is implemented this way:
        - Fixed-window algorithm: simpler to implement and reason about than
          sliding-window or token-bucket algorithms.  The tradeoff is that a
          burst of requests at the end of one window and the start of the
          next can temporarily exceed the intended rate, but this is
          acceptable for a Slack bot where precision is less critical than
          simplicity.
        - In-memory storage: eliminates the need for Redis or another external
          store, keeping the deployment footprint minimal.  The downside is
          that rate limits are not shared across multiple bot instances.  If
          the bot is scaled horizontally, this class should be replaced with
          a Redis-backed implementation.
        - Per-key granularity: rate limits are tracked per key (typically a
          user ID or channel ID), not globally.  This prevents one active
          user from consuming the entire quota and blocking others.
    """

    def __init__(self):
        """
        Initialize the rate limiter with an empty bucket storage.

        WHY an empty dict: buckets are created lazily on the first request
        for each key, avoiding the need to pre-configure known keys.
        """
        # WHY dict[str, dict]: the outer key is the rate-limit identifier
        # (e.g., user_id), and the inner dict holds {"count": int,
        # "reset_at": float}.  This flat structure is O(1) for lookup,
        # increment, and reset.
        self._storage: dict[str, dict] = {}

    def is_allowed(
        self, key: str, max_requests: int, window_seconds: int = 60
    ) -> tuple[bool, Optional[int]]:
        """
        Check whether a request from the given key is within the rate limit.

        HOW it works:
            1. If the key has no bucket, creates one with count=1 and a
               reset_at timestamp of now + window_seconds.
            2. If the existing bucket's window has expired, resets it.
            3. If the count is below max_requests, increments and allows.
            4. Otherwise, rejects and returns the number of seconds until
               the window resets.

        WHY it is implemented this way:
            - Lazy bucket creation means we do not need to know the set of
              users in advance.  Any new key is automatically tracked.
            - Resetting expired buckets rather than deleting them avoids
              unnecessary dict resize/rehash operations.
            - Returning (bool, Optional[int]) lets callers implement
              "retry after N seconds" messaging to the user, improving UX
              compared to a bare rejection.

        Args:
            key: Unique identifier for the rate-limit subject (e.g., user_id).
            max_requests: Maximum number of requests allowed per window.
            window_seconds: Duration of the rate-limit window in seconds
                            (default: 60).

        Returns:
            A tuple (allowed, retry_after).  If allowed is True, retry_after
            is None.  If allowed is False, retry_after is the number of
            seconds until the current window resets.
        """
        current_time = time.time()

        # WHY create-on-first-access: avoids requiring pre-registration of
        # rate-limit keys and handles the common case (new user) efficiently.
        if key not in self._storage:
            self._storage[key] = {"count": 1, "reset_at": current_time + window_seconds}
            return True, None

        bucket = self._storage[key]

        # WHY reset instead of delete: reusing the existing dict entry avoids
        # a delete + insert cycle, which is marginally more efficient for
        # high-throughput scenarios.
        if current_time >= bucket["reset_at"]:
            bucket["count"] = 1
            bucket["reset_at"] = current_time + window_seconds
            return True, None

        # WHY strict < (not <=): max_requests=10 means requests 1 through 10
        # are allowed; request 11 is the first to be rejected.  Using <=
        # would allow 11 requests.
        if bucket["count"] < max_requests:
            bucket["count"] += 1
            return True, None

        # WHY int() on retry_after: fractional seconds are confusing in user-
        # facing messages ("retry after 3.7 seconds").  Rounding down errs
        # on the side of the user retrying slightly early, which is preferable
        # to rounding up and making them wait longer than necessary.
        retry_after = int(bucket["reset_at"] - current_time)
        # WHY log at WARNING: rate-limit violations may indicate abuse or
        # misconfiguration.  Logging them enables security monitoring and
        # capacity planning.
        logger.warning(
            f"Rate limit exceeded for key: {key}", extra={"key": key, "retry_after": retry_after}
        )
        return False, retry_after

    def reset(self, key: str) -> None:
        """
        Remove the rate-limit bucket for a specific key.

        WHY this method exists: allows callers to manually clear a user's
        rate limit after, e.g., an admin override or a successful CAPTCHA
        verification.
        """
        if key in self._storage:
            del self._storage[key]

    def clear(self) -> None:
        """
        Remove all rate-limit buckets.

        WHY this method exists: useful during testing (reset state between
        test cases) and during graceful shutdown (free memory).
        """
        self._storage.clear()


# ==============================================================================
# Secure Random Utilities
# ==============================================================================
# WHY use the secrets module: Python's built-in `random` module uses a
# Mersenne Twister PRNG that is NOT cryptographically secure -- an attacker
# who observes 624 consecutive outputs can predict all future outputs.  The
# `secrets` module delegates to the operating system's CSPRNG (/dev/urandom
# on Linux, CryptGenRandom on Windows), which is designed to resist
# prediction even by a computationally powerful adversary.
# ==============================================================================


def generate_secure_id(length: int = 32) -> str:
    """
    Generate a cryptographically secure, URL-safe random identifier.

    HOW it works:
        Delegates to secrets.token_urlsafe(length), which generates `length`
        random bytes, then base64url-encodes them into a string that is safe
        for use in URLs, filenames, and database keys.

    WHY it is implemented this way:
        - secrets.token_urlsafe uses the OS CSPRNG, making the output
          unpredictable even to an attacker who has observed previous IDs.
        - URL-safe encoding (A-Z, a-z, 0-9, -, _) avoids characters that
          require percent-encoding in URLs or escaping in shell commands.
        - 32 bytes provides 256 bits of entropy, which is considered
          sufficient for any current or foreseeable brute-force attack.

    Args:
        length: Number of random bytes to generate (the resulting string
                will be approximately 4/3 times this length due to base64
                encoding).  Default: 32.

    Returns:
        A URL-safe random string.
    """
    return secrets.token_urlsafe(length)


def generate_api_key() -> str:
    """
    Generate a prefixed, cryptographically secure API key.

    HOW it works:
        Generates 32 random bytes via secrets.token_urlsafe and prepends
        the prefix "sbk_" (Slack Bot Key).

    WHY it is implemented this way:
        - The "sbk_" prefix makes it immediately obvious what kind of
          credential a string is when it appears in configuration files,
          environment variables, or (accidentally) in logs.  This speeds
          up incident response: a leaked "sbk_..." string can be instantly
          identified and revoked.
        - 32 bytes of randomness provides 256 bits of entropy, which is
          far beyond what is needed to resist brute-force attacks.
        - In a production system, only the SHA-256 hash of the key should
          be stored in the database; the plaintext key is shown to the
          user once at creation time and never stored.

    Returns:
        A string in the format "sbk_{random_url_safe_string}".
    """
    random_part = secrets.token_urlsafe(32)
    # WHY the "sbk_" prefix: prefixed keys are a widely adopted convention
    # (e.g., Stripe's "sk_", GitHub's "ghp_") because they enable automated
    # secret scanners to identify leaked keys by pattern.
    return f"sbk_{random_part}"


# ==============================================================================
# Input Sanitization
# ==============================================================================
# WHY sanitize before logging: log files are often stored in plain text, sent
# to third-party aggregation services (Datadog, Splunk), and accessed by
# multiple team members.  If a full API token ends up in a log line, every
# system and person with log access now has that credential.  Sanitization
# ensures that sensitive fields are masked before they reach any log handler.
# ==============================================================================


def sanitize_for_logging(data: dict) -> dict:
    """
    Recursively redact sensitive fields from a dictionary for safe logging.

    HOW it works:
        1. Iterates over all key-value pairs in the dictionary.
        2. Checks if the key (case-insensitive) contains any of the known
           sensitive substrings ("token", "password", "secret", etc.).
        3. If sensitive and the value is a string, masks it via mask_token().
           If sensitive but not a string, replaces with "***REDACTED***".
        4. If the value is a nested dict, recurses to sanitize it too.
        5. Returns a new dict (does not mutate the original).

    WHY it is implemented this way:
        - Substring matching on keys (rather than exact matching) catches
          variations like "bot_token", "signing_secret", "api_key_v2" without
          needing to enumerate every possible key name.
        - Recursion handles arbitrarily nested dictionaries, which are common
          in Slack event payloads.
        - Creating a new dict (rather than mutating in place) is essential
          because the original data may still be needed by the caller for
          processing.  Mutating it would corrupt the application state.
        - The set of sensitive_keys covers the most common credential-related
          field names across Slack, AWS, and general web applications.

    Args:
        data: The dictionary to sanitize.

    Returns:
        A new dictionary with all sensitive values masked or redacted.
    """
    # WHY a set (not a list): membership testing in a set is O(1) on average,
    # compared to O(n) for a list.  With 7 elements the difference is
    # negligible, but using the correct data structure is good practice.
    sensitive_keys = {
        "token",
        "password",
        "secret",
        "api_key",
        "authorization",
        "credential",
        "private_key",
    }

    sanitized = {}
    for key, value in data.items():
        key_lower = key.lower()

        # WHY substring match ("any(... in key_lower ...)") instead of exact
        # match: field names vary across APIs.  "bot_token", "slack_token",
        # "SLACK_BOT_TOKEN" all contain "token" and should all be redacted.
        is_sensitive = any(sensitive in key_lower for sensitive in sensitive_keys)

        if is_sensitive:
            # WHY mask strings but redact non-strings: for string tokens,
            # mask_token reveals the prefix (helpful for debugging).  For
            # non-string values (e.g., a dict containing nested secrets),
            # a flat "***REDACTED***" is the safest approach.
            if isinstance(value, str):
                sanitized[key] = mask_token(value)
            else:
                sanitized[key] = "***REDACTED***"
        elif isinstance(value, dict):
            # WHY recurse: Slack event payloads can be deeply nested
            # (e.g., {"event": {"token": "xoxb-..."}}).  Without recursion,
            # the nested token would be logged in plaintext.
            sanitized[key] = sanitize_for_logging(value)
        else:
            sanitized[key] = value

    return sanitized


# ==============================================================================
# Security Headers
# ==============================================================================
# WHY return security headers from a utility function: if the bot exposes any
# HTTP endpoints (health checks, OAuth callbacks, webhook receivers), those
# responses should include standard security headers.  Centralizing them here
# ensures every endpoint gets the same protection and makes it easy to update
# policies project-wide.
# ==============================================================================


def get_security_headers() -> dict[str, str]:
    """
    Return a dictionary of OWASP-recommended HTTP security headers.

    HOW it works:
        Returns a static dictionary of header name/value pairs that can be
        merged into any HTTP response.

    WHY it is implemented this way:
        - Each header addresses a specific class of web vulnerability:
          * X-Frame-Options: DENY -- prevents clickjacking by forbidding
            the page from being embedded in an iframe.
          * X-Content-Type-Options: nosniff -- prevents browsers from
            MIME-sniffing the Content-Type, which can lead to XSS.
          * X-XSS-Protection: 1; mode=block -- enables the browser's
            built-in XSS filter (defense in depth).
          * Strict-Transport-Security -- forces HTTPS for all future
            requests, preventing SSL-stripping attacks.
          * Content-Security-Policy: default-src 'self' -- restricts
            resource loading to the same origin, mitigating XSS.
          * Referrer-Policy -- limits the information leaked in the
            Referer header when navigating away from the page.
        - Returning a dict (rather than setting headers directly) decouples
          this utility from any specific web framework (Flask, FastAPI,
          Starlette, etc.).

    Returns:
        A dictionary of security header names to their values.

    Reference:
        https://owasp.org/www-project-secure-headers/
    """
    return {
        # WHY DENY (not SAMEORIGIN): the bot has no legitimate reason to be
        # framed, even by itself.  DENY is the most restrictive option.
        "X-Frame-Options": "DENY",
        # WHY nosniff: prevents the browser from interpreting a JSON API
        # response as HTML (which could execute embedded scripts).
        "X-Content-Type-Options": "nosniff",
        # WHY mode=block: if the browser detects reflected XSS, it blocks
        # the entire page rather than attempting to sanitize it (which can
        # be bypassed).
        "X-XSS-Protection": "1; mode=block",
        # WHY max-age=31536000 (1 year): once the browser sees this header,
        # it will refuse to connect over plain HTTP for a full year, even if
        # a user manually types "http://".
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        # WHY default-src 'self': restricts all resource loading (scripts,
        # images, fonts, etc.) to the same origin by default.  If specific
        # external resources are needed, they can be whitelisted individually.
        "Content-Security-Policy": "default-src 'self'",
        # WHY strict-origin-when-cross-origin: sends the full URL as the
        # Referer for same-origin requests (useful for analytics) but only
        # the origin (scheme + host) for cross-origin requests (privacy).
        "Referrer-Policy": "strict-origin-when-cross-origin",
    }


# ==============================================================================
# Password/Secret Validation
# ==============================================================================
# WHY validate secret strength: weak secrets (short, all-lowercase, dictionary
# words) are vulnerable to brute-force and dictionary attacks.  Validating
# at configuration time prevents the bot from running with dangerously weak
# credentials.
# ==============================================================================


def validate_secret_strength(secret: str, min_length: int = 32) -> tuple[bool, str]:
    """
    Check that a secret meets minimum entropy and complexity requirements.

    HOW it works:
        1. Checks that the secret is at least `min_length` characters.
        2. Checks for character variety: at least one uppercase letter,
           one lowercase letter, and one digit.

    WHY it is implemented this way:
        - Length is the most important factor in secret strength.  A
          32-character random string has ~190 bits of entropy (assuming
          alphanumeric + symbols), which is far beyond any brute-force
          capability.
        - Requiring mixed character classes (upper, lower, digit) is a
          secondary defense that catches manually-chosen secrets like
          "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" which meet the length
          requirement but have very low entropy.
        - Returning (bool, str) instead of raising lets callers decide
          whether to abort or merely warn, supporting both strict (startup)
          and lenient (health-check) usage patterns.

    Args:
        secret: The secret string to validate.
        min_length: Minimum required length (default: 32).

    Returns:
        A tuple (is_valid, message).  is_valid is True if all checks pass.
        message describes the first failed check, or a success confirmation.
    """
    if len(secret) < min_length:
        return False, f"Secret must be at least {min_length} characters"

    # WHY check for character variety: a long secret composed entirely of
    # one character class (e.g., all lowercase) has significantly less
    # entropy per character than a mixed-case alphanumeric secret.
    has_upper = any(c.isupper() for c in secret)
    has_lower = any(c.islower() for c in secret)
    has_digit = any(c.isdigit() for c in secret)

    if not (has_upper and has_lower and has_digit):
        return False, "Secret must contain uppercase, lowercase, and digits"

    return True, "Secret meets security requirements"
