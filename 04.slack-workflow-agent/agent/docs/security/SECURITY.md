# Security: What the Code Does

This page describes the security code as it is, including the parts that exist but are not wired in. The bot has only been run in a test workspace.

## Transport and request verification

- The bot connects through **Socket Mode** (`src/main.py`): an outbound WebSocket to Slack, so there is no public HTTP endpoint.
- `AsyncApp` is created with the signing secret (`src/app.py`), so **Slack Bolt** handles request verification for HTTP mode. In Socket Mode, HTTP request signing does not apply.
- `src/utils/security.py` contains `verify_slack_signature()`, an HMAC-SHA256 check with `hmac.compare_digest` and a 5-minute timestamp window. It is unit-tested but **not called by any runtime code**; it is kept as a reference implementation.

## Middleware chain (`src/app.py`)

Registered in this order:

1. `auth_middleware` (`src/slack/middleware/auth.py`): drops events that carry a `bot_id`, which stops bot-to-bot loops; logs request bodies through `sanitize_for_logging()`, which masks token-like keys.
2. `rate_limit_middleware` (`src/slack/middleware/rate_limit.py`): fixed-window, in-memory limits per user (`RATE_LIMIT_PER_USER`, default 10 a minute) and per channel (`RATE_LIMIT_PER_CHANNEL`, default 30 a minute). State lives in process memory, so it resets on restart and is not shared between instances.
3. `error_handler_middleware` (`src/slack/middleware/error_handler.py`): catches listener exceptions and returns a generic message; technical details are only included when asked for.

## Input handling

- `src/slack/listeners/messages.py` validates the channel ID and message length (4,000 characters) and passes text through `sanitize_text()`, which strips ASCII control characters. `mentions.py` also uses `sanitize_text()`.
- `src/utils/validators.py` also has `detect_injection_attempt()` (regex heuristics). It is unit-tested but not called by the listeners.

## Secrets

- All tokens come from environment variables via `config/settings.py` (Pydantic settings). Slack and Anthropic values are required at start-up; GitHub and Notion are optional, and their tools are only registered when a token is set.
- `.env` is gitignored. Start-up fails if the Slack tokens lack the `xoxb-` / `xapp-` prefixes; an unexpected GitHub token prefix gives a warning.

## Not implemented

- No OAuth installation flow (single workspace, bot token in `.env`).
- No shared rate-limit store (for example Redis), secrets manager, audit log or encryption of memory files.
- No HTTP mode with health endpoints: `register_health_endpoints()` in `src/app.py` is a placeholder.
