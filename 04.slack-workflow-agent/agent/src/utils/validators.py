"""
Input Validation Utilities for the Slack Bot Assistant
========================================================

WHY THIS FILE IS REQUIRED:
    Every piece of data that enters the application -- Slack channel IDs, user
    IDs, message timestamps, free-text input, numeric parameters, URLs -- must
    be validated before it is passed to the Slack API, stored in memory, or
    used in RAG queries.  Without centralized validation:
      - Malformed IDs would produce cryptic Slack API errors deep in the call
        stack instead of clear, early error messages.
      - Unvalidated text could carry injection payloads (XSS, SQL, command
        injection) that compromise the bot or its infrastructure.
      - Unchecked numeric parameters could trigger resource-exhaustion attacks
        (e.g., requesting 10 million messages).
      - Stale or future timestamps could enable replay attacks against the
        Slack request-signature verification flow.
    This module provides a single, importable library of validation functions
    so that every entry point validates input the same way.

PROGRAM LOGIC:
    1. Slack ID validators (validate_channel_id, validate_user_id,
       validate_message_ts) use regex patterns that mirror the documented
       Slack ID formats.  They raise InvalidInputError on mismatch.
    2. Text validators (validate_text_length, sanitize_text,
       detect_injection_attempt) enforce length limits, strip dangerous
       control characters, and pattern-match against known injection
       signatures.
    3. Parameter validators (validate_positive_integer, validate_hours_param,
       validate_limit_param) enforce type and range constraints on numeric
       API parameters.
    4. Timestamp validation (validate_timestamp) compares a Unix timestamp
       against the current UTC time to reject requests older than a
       configurable threshold (default: 5 minutes), preventing replay attacks.
    5. URL validation (validate_url) checks format via regex and optionally
       restricts to a domain whitelist to prevent SSRF.
    6. Batch validation (validate_batch) applies any single-item validator
       across a list, enforcing a maximum batch size to prevent abuse.

WHY THIS APPROACH:
    - Regex for Slack IDs: Slack publishes the format of its identifiers
      (e.g., channel IDs start with C/D/G/W followed by 8-12 alphanumeric
      characters).  Regex validation is O(n) in the ID length, requires no
      network call, and catches typos and injection attempts instantly.
    - Separate sanitize vs. validate: sanitization transforms input to make
      it safe (removing control characters), while validation rejects input
      that cannot be made safe (wrong format).  Both are needed -- sanitize
      first, then validate -- following the "defense in depth" principle.
    - Pattern-based injection detection: this is a heuristic, not a guarantee.
      It catches the most common attack signatures (script tags, SQL keywords,
      shell metacharacters) and serves as a defense-in-depth layer behind
      parameterized queries and output escaping.
    - Centralized parameter bounds: hardcoding max_hours=168 and max_limit=1000
      in dedicated functions prevents every caller from re-inventing these
      limits, ensuring consistency and making future policy changes trivial.

SECURITY CONSIDERATIONS:
    - validate_timestamp prevents replay attacks by rejecting requests whose
      timestamp is more than 5 minutes old (Slack's recommended window).
    - detect_injection_attempt catches obvious SQL, XSS, command injection,
      and path-traversal patterns.  It is NOT a replacement for parameterized
      queries or output escaping; it is a defense-in-depth layer.
    - sanitize_text deliberately does NOT html.escape() because Slack's
      mention syntax (<@U123>) uses angle brackets that would be corrupted.
    - validate_url with allowed_domains mitigates SSRF by restricting
      outbound requests to known-good hosts.

RELATIONSHIP TO OTHER FILES:
    USED BY:
        - src/slack/listeners/mentions.py  (validates channel_id, user_id)
        - src/slack/listeners/messages.py  (validates message text)
        - src/slack/services/message_service.py (validates IDs and params)
    USES:
        - src/utils/exceptions.py  (InvalidInputError, SecurityValidationError)
        - Python stdlib: re, html, datetime
    RELATED:
        - src/utils/security.py  (verify_slack_signature also validates
          timestamps, but at the HTTP layer; this module validates at the
          application/business-logic layer)
"""

import re
from typing import Any, Callable, Optional
from datetime import datetime, timezone
import html

from src.utils.exceptions import InvalidInputError, SecurityValidationError

# ==============================================================================
# Slack ID Validators
# ==============================================================================
# WHY validate Slack IDs at all: the Slack API will return generic "invalid
# arguments" errors if given a malformed ID, but those errors arrive after a
# network round-trip and contain no guidance on the correct format.  Validating
# locally is instantaneous and produces precise, actionable error messages.
# ==============================================================================


def validate_channel_id(channel_id: str) -> str:
    """
    Validate that a string conforms to the Slack channel ID format.

    HOW it works:
        Checks for emptiness, then matches against a regex that encodes
        Slack's documented channel-ID structure: a single uppercase letter
        prefix (C for public channels, D for DMs, G for private groups,
        W for enterprise-grid channels) followed by 8-12 uppercase
        alphanumeric characters.

    WHY it is implemented this way:
        - Regex is the standard tool for fixed-format string validation:
          it is fast (compiled once, reused), expressive, and well-understood.
        - The prefix set {C, D, G, W} covers all known Slack channel-type
          prefixes as of the current API version.  If Slack adds a new
          prefix, only this one regex needs updating.
        - Returning the validated string (pass-through) enables a fluent
          style: validated_id = validate_channel_id(raw_id).

    Args:
        channel_id: Raw channel ID string from user input or Slack event.

    Returns:
        The same channel_id string, guaranteed to match the expected format.

    Raises:
        InvalidInputError: If the channel ID is empty or does not match the
                           expected pattern.
    """
    if not channel_id:
        raise InvalidInputError("Channel ID cannot be empty")

    # WHY this specific pattern: Slack documents that channel IDs are a
    # single letter prefix followed by 8-12 alphanumeric characters.  The
    # character class [CDGW] covers public, DM, group, and enterprise
    # channel types respectively.
    pattern = r"^[CDGW][A-Z0-9]{8,12}$"
    if not re.match(pattern, channel_id):
        raise InvalidInputError(
            f"Invalid channel ID format: {channel_id}",
            details={"expected_format": "C1234567890, D1234567890, or G1234567890"},
        )

    return channel_id


def validate_user_id(user_id: str) -> str:
    """
    Validate that a string conforms to the Slack user ID format.

    HOW it works:
        Checks for emptiness, then matches against a regex encoding Slack's
        user-ID structure: prefix U (regular users) or W (enterprise-grid
        users) followed by 8-12 uppercase alphanumeric characters.

    WHY it is implemented this way:
        - Same rationale as validate_channel_id: local, fast, precise
          validation avoids a wasteful API round-trip and gives the user
          an immediately actionable error message.
        - Including W alongside U covers enterprise-grid deployments where
          user IDs start with W instead of U.

    Args:
        user_id: Raw user ID string from user input or Slack event.

    Returns:
        The same user_id string, guaranteed to match the expected format.

    Raises:
        InvalidInputError: If the user ID is empty or does not match.
    """
    if not user_id:
        raise InvalidInputError("User ID cannot be empty")

    # WHY include W: Slack Enterprise Grid uses W-prefixed IDs for users
    # that span multiple workspaces.  Omitting W would reject valid users
    # in enterprise environments.
    pattern = r"^[UW][A-Z0-9]{8,12}$"
    if not re.match(pattern, user_id):
        raise InvalidInputError(
            f"Invalid user ID format: {user_id}", details={"expected_format": "U1234567890"}
        )

    return user_id


def validate_message_ts(ts: str) -> str:
    """
    Validate that a string conforms to the Slack message timestamp format.

    HOW it works:
        Matches against a regex for Slack's timestamp format: exactly 10
        digits (Unix epoch seconds), a literal dot, then 1-6 digits
        (microsecond precision).

    WHY it is implemented this way:
        - Slack uses timestamps as unique message identifiers (not just
          for ordering).  A malformed timestamp would silently fail to
          locate a message rather than raising an obvious error.
        - The variable precision (1-6 digits after the dot) accommodates
          different Slack API endpoints that return varying precision.

    Args:
        ts: Raw timestamp string (e.g., "1234567890.123456").

    Returns:
        The same timestamp string, guaranteed to match the expected format.

    Raises:
        InvalidInputError: If the timestamp is empty or does not match.
    """
    if not ts:
        raise InvalidInputError("Timestamp cannot be empty")

    # WHY 10 digits before the dot: Unix timestamps have been 10 digits since
    # 2001-09-09 and will remain so until 2286-11-20.  Fewer digits indicate
    # truncated input; more digits indicate a millisecond timestamp (wrong
    # format for Slack).
    pattern = r"^\d{10}\.\d{1,6}$"
    if not re.match(pattern, ts):
        raise InvalidInputError(
            f"Invalid timestamp format: {ts}", details={"expected_format": "1234567890.123456"}
        )

    return ts


# ==============================================================================
# Text Input Validators
# ==============================================================================
# WHY separate text validators: free-text input is the most dangerous attack
# surface.  Length limits prevent memory exhaustion, sanitization removes
# control characters that could exploit terminal emulators, and injection
# detection provides a heuristic early-warning layer.
# ==============================================================================


def validate_text_length(text: str, max_length: int = 4000, field_name: str = "text") -> str:
    """
    Enforce a maximum character length on a text field.

    HOW it works:
        Returns empty string for falsy input (None, empty).  Otherwise,
        compares len(text) against max_length and raises if exceeded.

    WHY it is implemented this way:
        - 4000 characters is Slack's maximum message length.  Enforcing it
          here avoids a Slack API "msg_too_long" error that would be harder
          to debug.
        - The field_name parameter lets callers produce contextual error
          messages (e.g., "summary exceeds maximum length") without writing
          custom validation logic.
        - Returning empty string for falsy input is a deliberate design
          choice: many callers treat absent text as an empty string, so
          this avoids None-propagation bugs.

    Args:
        text: The text to validate.
        max_length: Maximum allowed character count (default: 4000).
        field_name: Human-readable field name for error messages.

    Returns:
        The original text if within limits, or empty string if input is falsy.

    Raises:
        InvalidInputError: If the text exceeds max_length.
    """
    if not text:
        return ""

    if len(text) > max_length:
        raise InvalidInputError(
            f"{field_name} exceeds maximum length of {max_length} characters",
            details={"current_length": len(text), "max_length": max_length},
        )

    return text


def sanitize_text(text: str) -> str:
    """
    Remove dangerous characters from text input while preserving Slack formatting.

    HOW it works:
        1. Returns early for falsy input to avoid NoneType errors.
        2. Uses a regex character class to strip ASCII control characters
           (0x00-0x08, 0x0B, 0x0C, 0x0E-0x1F, 0x7F) while explicitly
           preserving newline (0x0A), carriage return (0x0D), and tab (0x09).
        3. Strips leading/trailing whitespace but leaves internal whitespace
           intact to preserve user formatting.

    WHY it is implemented this way:
        - Control characters can exploit terminal emulators and log viewers
          (terminal injection attacks).  Stripping them is a pure safety
          measure with no user-visible downside.
        - We deliberately do NOT call html.escape() because Slack's native
          mention syntax uses angle brackets (<@U123>, <#C123|channel-name>).
          HTML-escaping would corrupt these into &lt;@U123&gt;, breaking
          mentions in Slack messages.
        - Preserving newlines and tabs is necessary because users legitimately
          paste code snippets and multi-line text into Slack.

    Args:
        text: Raw user input text.

    Returns:
        Sanitized text with control characters removed and whitespace trimmed.
    """
    if not text:
        return ""

    # WHY this specific character class: it targets only the dangerous control
    # characters while explicitly excluding \n (0x0A), \r (0x0D), and \t (0x09)
    # which are legitimate formatting characters in user input.
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)

    # WHY strip only edges: internal whitespace is part of the user's intended
    # formatting.  Collapsing it would mangle code snippets and lists.
    text = text.strip()

    return text


def detect_injection_attempt(text: str) -> bool:
    """
    Heuristically detect common injection attack patterns in user input.

    HOW it works:
        Iterates over a list of regex patterns representing known attack
        signatures (script tags, SQL keywords, shell metacharacters, path
        traversal).  Returns True on the first match, False if none match.

    WHY it is implemented this way:
        - This is a DEFENSE-IN-DEPTH measure, not a primary defense.  The
          primary defenses are parameterized queries (for SQL), output
          escaping (for XSS), and subprocess argument lists (for command
          injection).  This function adds an extra layer that catches
          obvious, unsophisticated attacks early and logs them for security
          monitoring.
        - Pattern matching is fast and stateless, making it suitable for
          inline validation on every incoming message.
        - Using re.IGNORECASE ensures case-insensitive matching because
          attackers commonly use mixed case to evade naive filters
          (e.g., "SeLeCt" instead of "SELECT").
        - Returning a boolean (rather than raising) gives callers the
          flexibility to decide the response: log and continue, reject,
          or alert.

    Args:
        text: User input text to scan.

    Returns:
        True if a known injection pattern is detected, False otherwise.

    Important caveats:
        - This function catches OBVIOUS attacks only.  Sophisticated
          obfuscation (e.g., Unicode homoglyphs, encoded payloads) will
          bypass it.  Never rely on this as the sole defense.
    """
    # WHY these specific patterns: they cover the OWASP Top 10 injection
    # categories most relevant to a Slack bot that processes user text and
    # may interact with databases, shells, or web services.
    dangerous_patterns = [
        r"<script[^>]*>.*?</script>",  # WHY: XSS via inline script injection
        r"javascript:",  # WHY: XSS via javascript: protocol in URLs
        r"on\w+\s*=",  # WHY: XSS via event-handler attributes (onclick=, onerror=, etc.)
        r"(union|select|insert|update|delete|drop|create|alter|exec|execute)\s+",  # WHY: SQL injection keywords
        r"(&&|\|\||;|`|\$\()",  # WHY: shell command chaining and substitution operators
        r"\.\./",  # WHY: path traversal to escape intended directory
    ]

    for pattern in dangerous_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True

    return False


# ==============================================================================
# Parameter Validators
# ==============================================================================
# WHY dedicated parameter validators: numeric parameters like "hours" and
# "limit" are used to control how many Slack API calls the bot makes.
# Unchecked values could trigger thousands of API calls (resource exhaustion)
# or negative values that produce nonsensical results.  Centralizing the
# bounds here ensures every caller enforces the same policy.
# ==============================================================================


def validate_positive_integer(
    value: int, field_name: str = "value", min_value: int = 1, max_value: Optional[int] = None
) -> int:
    """
    Validate that a value is an integer within an acceptable range.

    HOW it works:
        1. Type-checks with isinstance to reject floats, strings, etc.
        2. Checks against min_value (default: 1, ensuring positivity).
        3. Checks against max_value if provided.

    WHY it is implemented this way:
        - isinstance check catches subtle bugs where a float (e.g., 3.0)
          is passed instead of an int.  In Python, 3.0 > 1 is True, so
          without the type check the float would silently pass through.
        - min_value defaults to 1 (not 0) because most use cases in this
          project are "fetch at least 1 item" -- zero would be a no-op.
        - max_value is optional because some parameters have natural upper
          bounds (hours, limit) while others do not.
        - Returning the validated value enables chaining:
          hours = validate_positive_integer(raw_hours, "hours", 1, 168).

    Args:
        value: The integer to validate.
        field_name: Human-readable name for error messages.
        min_value: Minimum acceptable value (inclusive, default: 1).
        max_value: Maximum acceptable value (inclusive, optional).

    Returns:
        The same integer, guaranteed to be within the specified range.

    Raises:
        InvalidInputError: If the value is not an int or is out of range.
    """
    if not isinstance(value, int):
        raise InvalidInputError(f"{field_name} must be an integer")

    if value < min_value:
        raise InvalidInputError(
            f"{field_name} must be at least {min_value}",
            details={"value": value, "min_value": min_value},
        )

    if max_value is not None and value > max_value:
        raise InvalidInputError(
            f"{field_name} must be at most {max_value}",
            details={"value": value, "max_value": max_value},
        )

    return value


def validate_hours_param(hours: int) -> int:
    """
    Validate the 'hours' parameter used for message history retrieval.

    HOW it works:
        Delegates to validate_positive_integer with min=1, max=168 (7 days).

    WHY it is implemented this way:
        - 168 hours (7 days) is the maximum lookback window for most Slack
          API methods on the free tier.  Even on paid tiers, going further
          back rarely provides useful context and would trigger excessive
          API pagination.
        - Wrapping validate_positive_integer in a domain-specific function
          documents the business rule (7-day max) in one place and keeps
          callers from having to remember the magic number 168.

    Args:
        hours: Number of hours to look back into message history.

    Returns:
        Validated hours value (1-168).

    Raises:
        InvalidInputError: If hours is not a positive integer or exceeds 168.
    """
    return validate_positive_integer(
        hours, field_name="hours", min_value=1, max_value=168  # WHY 168: 7 days * 24 hours
    )


def validate_limit_param(limit: int) -> int:
    """
    Validate the 'limit' parameter used for result pagination.

    HOW it works:
        Delegates to validate_positive_integer with min=1, max=1000.

    WHY it is implemented this way:
        - 1000 is a safe upper bound that prevents a single request from
          triggering hundreds of paginated Slack API calls (each page
          returns ~100 items, so 1000 items = ~10 API calls).
        - The Slack conversations.history endpoint itself caps at 1000
          messages per call, so allowing more would require custom
          pagination logic that is not currently implemented.

    Args:
        limit: Maximum number of results to return.

    Returns:
        Validated limit value (1-1000).

    Raises:
        InvalidInputError: If limit is not a positive integer or exceeds 1000.
    """
    return validate_positive_integer(
        limit, field_name="limit", min_value=1, max_value=1000  # WHY 1000: prevents excessive API calls
    )


# ==============================================================================
# Timestamp Validators
# ==============================================================================
# WHY validate timestamps: timestamps are the foundation of Slack's request
# signature verification.  An attacker who intercepts a valid signed request
# can replay it later.  By rejecting timestamps older than 5 minutes, we
# limit the replay window to an acceptably short duration.
# ==============================================================================


def validate_timestamp(timestamp: float | int, max_age_seconds: int = 300) -> float:
    """
    Validate that a Unix timestamp is recent enough to be trustworthy.

    HOW it works:
        1. Computes the current UTC time as a Unix timestamp.
        2. Calculates the age of the provided timestamp.
        3. Rejects timestamps older than max_age_seconds (default: 300s = 5 min).
        4. Rejects timestamps more than 60 seconds in the future (clock skew
           tolerance) to catch spoofed future timestamps.

    WHY it is implemented this way:
        - 300 seconds (5 minutes) is Slack's officially recommended maximum
          age for request verification.  It balances security (smaller window
          = less replay risk) against operational reality (network latency,
          clock drift between Slack's servers and ours).
        - The 60-second future tolerance accounts for minor clock skew between
          the client and server.  Without it, a server whose clock is a few
          seconds behind would reject legitimate requests.
        - Using datetime.now(timezone.utc) instead of time.time() ensures
          timezone-aware comparison and is the recommended approach in
          modern Python.

    Args:
        timestamp: Unix timestamp (seconds since epoch) to validate.
        max_age_seconds: Maximum acceptable age in seconds (default: 300).

    Returns:
        The timestamp as a float, guaranteed to be within the acceptable
        time window.

    Raises:
        SecurityValidationError: If the timestamp is too old or too far in
                                 the future.
    """
    current_time = datetime.now(timezone.utc).timestamp()
    age = current_time - timestamp

    # WHY reject old timestamps: prevents replay attacks where an attacker
    # captures a signed request and re-sends it minutes, hours, or days later.
    if age > max_age_seconds:
        raise SecurityValidationError(
            f"Request timestamp is too old: {age:.1f}s (max: {max_age_seconds}s)",
            details={"timestamp": timestamp, "age_seconds": age},
        )

    # WHY reject future timestamps: a timestamp significantly in the future
    # is either a clock-skew issue or an attempt to craft a request that will
    # be valid for an extended period.  The 60-second tolerance prevents
    # false positives from minor clock differences.
    if age < -60:
        raise SecurityValidationError(
            f"Request timestamp is in the future: {-age:.1f}s", details={"timestamp": timestamp}
        )

    return float(timestamp)


# ==============================================================================
# URL Validators
# ==============================================================================
# WHY validate URLs: the bot may fetch external resources (e.g., Notion pages,
# GitHub issues) on behalf of users.  Without validation, an attacker could
# supply a URL pointing to an internal service (SSRF) or a non-HTTP protocol
# (file://, gopher://) to exfiltrate data.
# ==============================================================================


def validate_url(url: str, allowed_domains: Optional[list[str]] = None) -> str:
    """
    Validate URL format and optionally restrict to a domain whitelist.

    HOW it works:
        1. Rejects empty URLs immediately.
        2. Matches against a regex that requires http:// or https:// scheme,
           a valid hostname with a TLD, and an optional path.
        3. If allowed_domains is provided, extracts the hostname from the URL
           and checks it against the whitelist.

    WHY it is implemented this way:
        - Requiring http(s):// scheme blocks file://, ftp://, gopher://, and
          other protocols that could be used for SSRF or data exfiltration.
        - The regex is intentionally simple and conservative.  It will reject
          some exotic but valid URLs (e.g., IDN domains with punycode).  In a
          security context, rejecting a few edge cases is preferable to
          allowing a dangerous URL through.
        - Domain whitelisting is the strongest SSRF mitigation: even if the
          URL passes format validation, it must point to a known-good domain.
          This prevents internal-network scanning via crafted URLs.

    Args:
        url: The URL string to validate.
        allowed_domains: Optional list of permitted hostnames.  When provided,
                         only URLs matching one of these domains are accepted.

    Returns:
        The validated URL string.

    Raises:
        InvalidInputError: If the URL is empty or does not match the format.
        SecurityValidationError: If the domain is not in the whitelist.
    """
    if not url:
        raise InvalidInputError("URL cannot be empty")

    # WHY this regex: it enforces HTTPS/HTTP scheme (blocking non-web protocols),
    # requires at least a two-character TLD (blocking "http://localhost" which
    # is a common SSRF target), and allows an optional path.
    url_pattern = r"^https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(/.*)?$"
    if not re.match(url_pattern, url):
        raise InvalidInputError(f"Invalid URL format: {url}")

    # WHY domain whitelist check: even a correctly-formatted URL could point
    # to an internal service (e.g., http://metadata.google.internal).
    # Whitelisting restricts requests to known-safe external services.
    if allowed_domains:
        domain = re.search(r"https?://([^/]+)", url)
        if not domain or domain.group(1) not in allowed_domains:
            raise SecurityValidationError(
                f"URL domain not in whitelist: {url}", details={"allowed_domains": allowed_domains}
            )

    return url


# ==============================================================================
# Batch Validation
# ==============================================================================
# WHY batch validation: several operations (e.g., bulk-indexing messages into
# the vector store) process lists of items.  Applying validation to each item
# individually while also enforcing a batch-size limit prevents both malformed
# input and resource exhaustion from a single oversized request.
# ==============================================================================


def validate_batch(items: list[Any], validator: Callable, max_batch_size: int = 100) -> list[Any]:
    """
    Apply a validator function to every item in a list, with batch-size limits.

    HOW it works:
        1. Rejects empty batches (a batch operation on zero items is likely
           a caller bug).
        2. Rejects batches exceeding max_batch_size to prevent resource
           exhaustion.
        3. Iterates over items, applying the validator to each one.
        4. On the first validation failure, raises immediately with the
           item index for easy debugging.

    WHY it is implemented this way:
        - Fail-fast on first error: in most use cases, a single bad item
          means the entire batch is suspect (e.g., a malformed CSV import).
          Collecting all errors would be more user-friendly but adds
          complexity that is not needed for the current use cases.
        - max_batch_size defaults to 100 because the Slack API's
          conversations.history endpoint returns at most 100 messages per
          page, making 100 a natural batch boundary.
        - Accepting any Callable as the validator makes this function
          composable with all the single-item validators defined above.

    Args:
        items: List of items to validate.
        validator: A callable that takes one item and returns the validated
                   item (or raises on failure).
        max_batch_size: Maximum number of items allowed (default: 100).

    Returns:
        List of validated items (same order as input).

    Raises:
        InvalidInputError: If the batch is empty, exceeds max_batch_size,
                           or any item fails validation.
    """
    if not items:
        raise InvalidInputError("Batch cannot be empty")

    # WHY enforce max_batch_size: prevents a single request from consuming
    # excessive memory or triggering thousands of downstream API calls.
    if len(items) > max_batch_size:
        raise InvalidInputError(
            f"Batch size {len(items)} exceeds maximum {max_batch_size}",
            details={"batch_size": len(items), "max_batch_size": max_batch_size},
        )

    # WHY enumerate: including the item index in the error message lets the
    # caller pinpoint which item in a large batch caused the failure, without
    # having to re-validate each item individually.
    validated_items = []
    for i, item in enumerate(items):
        try:
            validated_items.append(validator(item))
        except Exception as e:
            raise InvalidInputError(
                f"Validation failed for item {i}", details={"item_index": i, "error": str(e)}
            )

    return validated_items
