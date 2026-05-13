"""
Test Data Setup Script
=======================

WHY THIS FILE IS REQUIRED:
    After deploying the bot and initializing the vector store, developers need
    a way to verify that every subsystem (heartbeat, memory, RAG, summarization,
    rate limiting, cron jobs, agent orchestration) is working correctly.  Manual
    testing is tedious and error-prone because it requires:
      - Typing dozens of messages in the correct format.
      - Remembering to cover edge cases (empty mentions, rapid-fire rate-limit
        triggers, multi-topic threads for summarization).
      - Reproducing the same test scenario every time the environment is reset.

    This script automates the creation of realistic test data by posting
    structured threaded conversations to a designated Slack channel.  Each
    thread targets a specific bot subsystem, providing a comprehensive smoke
    test that can be run after any deployment.

    Without this script:
      - Developers would spend 30+ minutes manually typing test messages.
      - Test coverage would be inconsistent (some subsystems might be
        accidentally skipped).
      - There would be no reproducible baseline for verifying end-to-end bot
        behavior.

PROGRAM LOGIC:
    1. Add the project root to ``sys.path`` and load environment variables
       from ``.env`` so that ``SLACK_BOT_TOKEN`` is available.
    2. Authenticate with the Slack API using a synchronous ``WebClient``
       and retrieve the bot's own user ID via ``auth_test()``.
    3. Define the target channel ID (``#new-channel``) where all test data
       will be posted.
    4. Define a helper function ``post()`` that wraps ``chat_postMessage``
       with a 0.4-second delay between calls (rate-limit courtesy).
    5. Create 7 test threads, each targeting a specific subsystem:
       a. **Thread 1 -- Heartbeat & Slash Commands**: Tests basic bot
          connectivity, ``/bot-help``, and ``/bot-status``.
       b. **Thread 2 -- Memory System**: Posts facts for short-term and
          long-term memory, then asks recall questions.
       c. **Thread 3 -- RAG Knowledge Base**: Posts topical messages across
          4 domains (auth, DB schema, CI/CD, monitoring), then asks semantic
          search questions.
       d. **Thread 4 -- Summarization**: Simulates a realistic team discussion
          with decisions, action items, and a bug report, then asks for a
          summary.
       e. **Thread 5 -- Rate Limiting**: Posts rapid @mentions to trigger
          per-user rate limiting.
       f. **Thread 6 -- Cron & Scheduler**: Documents cron configurations and
          manual testing instructions.
       g. **Thread 7 -- Agent Orchestrator**: Tests the Claude-powered agent
          with tool-calling and context-building questions.
    6. Print a summary of all created threads (with timestamps) and a quick
       test guide.

WHY THIS APPROACH:
    - **Synchronous ``WebClient``** (not ``AsyncWebClient``): This is a simple
      sequential script that posts messages one at a time with deliberate delays.
      Async would add complexity (event loop setup, ``await`` everywhere) with
      no benefit because the 0.4-second delay between messages is the bottleneck,
      not I/O latency.
    - **Threaded conversations**: Each test area gets its own parent message
      with replies in a thread.  This keeps the channel organized and mirrors
      how real teams use Slack.  It also tests the bot's thread-awareness
      (``thread_ts`` handling in listeners).
    - **Hard-coded channel ID**: The channel ID (``C0AEAH3PHDF``) is hard-coded
      because this is a developer-specific setup script, not production code.
      The channel must already exist and the bot must be a member.  A more
      robust version could accept the channel as a CLI argument.
    - **``time.sleep(0.4)``**: Slack's Web API has a rate limit of roughly 1
      request per second for ``chat_postMessage`` (with burst allowance).  The
      0.4-second delay is aggressive enough to be fast but respectful enough
      to avoid 429 errors during the roughly 85 messages this script posts.
    - **Direct ``os.environ`` access**: This script uses ``os.environ``
      directly (instead of ``config/settings.py``) because it is a standalone
      developer tool that should work even if the full settings validation
      fails (e.g., if ``ANTHROPIC_API_KEY`` is not set yet).  The ``.env``
      file is loaded via ``python-dotenv`` for convenience.
    - **Bot mentions (``<@{BOT_USER_ID}>``)**: Several messages deliberately
      @mention the bot to trigger the ``app_mention`` event listener.  This
      tests the full end-to-end flow: Slack dispatches the event, the
      middleware chain processes it, and the agent generates a response.

RELATIONSHIP TO OTHER FILES:
    - ``src/main.py`` (prerequisite)
        The bot must be running (``python src/main.py``) for the @mention and
        slash-command tests to produce bot responses.
    - ``src/slack/listeners/messages.py`` (tested by Thread 2)
        DM-style messages test the message event listener.
    - ``src/slack/listeners/mentions.py`` (tested by Threads 1, 2, 3, 7)
        @mention messages test the app_mention event listener.
    - ``src/slack/listeners/commands.py`` (tested by Thread 1)
        Instructions to run ``/bot-help`` and ``/bot-status`` test the
        slash command listeners.
    - ``src/memory/manager.py`` (tested by Thread 2)
        Memory recall questions test the short-term and long-term memory
        subsystems.
    - ``src/rag/indexer.py`` and ``src/rag/retriever.py`` (tested by Thread 3)
        After running ``scripts/index_channels.py`` on the test channel, the
        RAG queries in Thread 3 test semantic search.
    - ``src/services/summarization.py`` (tested by Thread 4)
        The ``/bot-summarize`` command and in-thread summary request test the
        summarization service.
    - ``src/slack/middleware/rate_limit.py`` (tested by Thread 5)
        Rapid @mentions test the per-user rate limiter.
    - ``src/agent/orchestrator.py`` (tested by Thread 7)
        Agent-directed questions test the full Claude-powered pipeline.
    - ``config/settings.py`` (indirect)
        Rate-limit thresholds, cron schedules, and RAG indexing frequency
        referenced in the test messages come from settings.

Usage:
    python scripts/setup_test_channels.py
"""

import sys
import time
from pathlib import Path

# WHY sys.path manipulation: Same reason as all other scripts in this directory.
# Enables ``from config.*`` and ``from src.*`` imports when run directly.
# Not strictly needed by this script (it uses ``os.environ`` directly), but
# included for consistency and in case future modifications add project imports.
sys.path.insert(0, str(Path(__file__).parent.parent))

# WHY load_dotenv before os.environ access: The bot token lives in the ``.env``
# file.  ``load_dotenv`` reads that file and injects its key-value pairs into
# ``os.environ`` so that ``os.environ["SLACK_BOT_TOKEN"]`` resolves correctly.
# Without this, the script would crash with a ``KeyError`` unless the variable
# was exported in the shell environment.
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import os

# WHY synchronous WebClient: This script posts messages sequentially with
# deliberate delays between each call.  There is no concurrency benefit from
# using the async client, and the sync client keeps the code simpler (no
# ``async/await``, no event loop setup).
client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])

# WHY auth_test(): Retrieves the bot's own user ID, which is needed to
# construct @mention tokens (``<@U...>``) in test messages.  This also serves
# as an early connectivity check -- if the token is invalid or Slack is
# unreachable, the script fails here with a clear error.
auth = client.auth_test()
BOT_USER_ID = auth["user_id"]
print(f"Bot: @{auth['user']} ({BOT_USER_ID})")

# WHY hard-coded channel ID: This is a developer-local setup script, not
# production code.  The channel (#new-channel) is a known test channel in the
# development workspace.  Hard-coding avoids the overhead of channel lookup
# by name (which would require additional API calls and error handling).
# For use in a different workspace, change this constant.
CHANNEL_ID = "C0AEAH3PHDF"
print(f"Target channel: #new-channel ({CHANNEL_ID})")


def post(text: str, thread_ts: str = None) -> str | None:
    """
    Post a message to the test channel, optionally in a thread.

    HOW IT WORKS:
        Calls ``chat_postMessage`` to send the given text to the target channel.
        If ``thread_ts`` is provided, the message is posted as a reply in that
        thread.  A 0.4-second sleep follows each successful post to stay within
        Slack's rate limits.

    WHY IMPLEMENTED THIS WAY:
        - **Returns the message timestamp**: Slack uses timestamps (``ts``) as
          unique message identifiers.  Returning the ``ts`` of the parent
          message allows subsequent calls to thread replies under it.
        - **0.4-second delay**: Slack's ``chat.postMessage`` rate limit is
          approximately 1 request/second (with short burst allowance).  A
          0.4-second delay keeps the script fast while respecting the limit.
          If 429 errors occur, increase this delay.
        - **Returns None on error**: Instead of raising an exception, errors
          are printed and None is returned.  This allows the script to continue
          posting to other threads even if one message fails (e.g., if the bot
          is temporarily rate-limited).

    Args:
        text: The message text to post (supports Slack mrkdwn formatting).
        thread_ts: If provided, post as a threaded reply under this timestamp.

    Returns:
        The ``ts`` (timestamp/ID) of the posted message, or None if the post
        failed.
    """
    try:
        resp = client.chat_postMessage(
            channel=CHANNEL_ID,
            text=text,
            thread_ts=thread_ts,
        )
        # WHY sleep after posting: Slack enforces rate limits on the
        # chat.postMessage endpoint.  Posting too quickly (especially in a
        # loop of ~85 messages) would trigger HTTP 429 responses, causing
        # messages to be silently dropped.
        time.sleep(0.4)  # Rate limit courtesy
        return resp["ts"]
    except SlackApiError as e:
        # WHY catch and print instead of raising: This script is a best-effort
        # test data generator.  A single failed message should not abort the
        # remaining 80+ messages.  The error is printed so the developer can
        # investigate (most common cause: bot not a member of the channel).
        print(f"  Error: {e.response['error']}")
        return None


# ============================================================================
# 1. HEARTBEAT & GENERAL TESTING THREAD
# ============================================================================
# WHY this thread: Verifies the most fundamental bot capability -- that it is
# online, responsive, and that the middleware chain (auth -> rate-limit ->
# error-handler) is functioning.  If this thread produces no bot responses,
# all other tests are moot.
print("\n=== 1. Heartbeat & General Testing ===")
ts1 = post(":test_tube: *TEST AREA 1: Heartbeat & Slash Commands*\nUse this thread to test `/bot-help`, `/bot-status`, and basic bot connectivity.")
if ts1:
    post("The bot should respond to mentions and slash commands in this channel.", thread_ts=ts1)
    post(f"<@{BOT_USER_ID}> are you online? This is a heartbeat check.", thread_ts=ts1)
    post("Try running `/bot-help` to see available commands.", thread_ts=ts1)
    post("Try running `/bot-status` to see bot health.", thread_ts=ts1)
    post(f"<@{BOT_USER_ID}> what's your current status?", thread_ts=ts1)
    post("If you see responses above, the middleware chain (auth -> rate-limit -> error-handler) is working!", thread_ts=ts1)
    print(f"  Posted 7 messages (thread: {ts1})")

# ============================================================================
# 2. MEMORY SYSTEM TESTING THREAD
# ============================================================================
# WHY this thread: The memory system has two tiers -- short-term (in-memory,
# for conversation context) and long-term (file-backed, for persistent facts).
# This thread posts facts in both categories, then asks recall questions to
# verify that the bot can store and retrieve information across messages.
print("\n=== 2. Memory System Testing ===")
ts2 = post(":brain: *TEST AREA 2: Memory System*\nTest short-term (in-memory) and long-term (file-backed) memory storage and retrieval.")
if ts2:
    # WHY short-term memory tests first: Short-term memory is simpler (pure
    # in-memory dict) and should work even if the file system has issues.
    # If these fail, long-term memory tests are likely to fail too.
    post("My name is Alice and I'm the frontend lead on Project Phoenix.", thread_ts=ts2)
    post(f"<@{BOT_USER_ID}> remember that our sprint ends this Friday, Feb 14.", thread_ts=ts2)
    post("We decided to use React 19 with server components for the dashboard.", thread_ts=ts2)
    post("The API endpoint for user profiles is POST /api/v2/users/:id", thread_ts=ts2)
    post(f"<@{BOT_USER_ID}> what did we decide about the dashboard framework?", thread_ts=ts2)

    # WHY long-term memory tests: These messages contain "important" facts
    # (production database, standup schedule, deploy pipeline) that should
    # persist across bot restarts via the file-backed memory store.
    post("IMPORTANT: Our production database is PostgreSQL 16 on AWS RDS us-east-1.", thread_ts=ts2)
    post("Team standup is at 10:00 AM EST every weekday in #standup.", thread_ts=ts2)
    post("Deploy pipeline: GitHub Actions -> Docker build -> ECS staging -> manual approve -> prod.", thread_ts=ts2)
    post(f"<@{BOT_USER_ID}> can you recall what we discussed about deployments?", thread_ts=ts2)

    # WHY explicit recall questions: These @mentions trigger the agent
    # orchestrator, which should use the memory retriever to find relevant
    # facts.  The questions are phrased differently from the original facts
    # to test semantic recall (not just keyword matching).
    post(f"<@{BOT_USER_ID}> what do you remember about Alice?", thread_ts=ts2)
    post(f"<@{BOT_USER_ID}> what is the production database?", thread_ts=ts2)
    print(f"  Posted 12 messages (thread: {ts2})")

# ============================================================================
# 3. RAG SYSTEM TESTING THREAD
# ============================================================================
# WHY this thread: The RAG pipeline indexes messages into ChromaDB and
# retrieves semantically similar documents when the bot needs context.  This
# thread posts messages across 4 distinct knowledge domains to test that:
#   - Messages are correctly indexed (run index_channels.py after this script).
#   - Semantic search retrieves the right documents for a given query.
#   - The bot can synthesize information from retrieved documents into answers.
print("\n=== 3. RAG System Testing ===")
ts3 = post(":mag: *TEST AREA 3: RAG Knowledge Base*\nTopical messages for vector indexing and semantic search retrieval.")
if ts3:
    # WHY 4 separate topics (auth, DB, CI/CD, monitoring): Testing with
    # multiple distinct knowledge domains verifies that the embedding model
    # and cosine-similarity search can distinguish between unrelated topics
    # and return only the relevant documents for a given query.
    post("AUTH ARCHITECTURE: We use JWT tokens with RS256 signing algorithm.", thread_ts=ts3)
    post("Access tokens expire after 15 minutes, refresh tokens after 7 days.", thread_ts=ts3)
    post("Refresh tokens are stored in HttpOnly cookies, never localStorage.", thread_ts=ts3)
    post("Auth middleware validates the Authorization: Bearer <token> header on every request.", thread_ts=ts3)

    # WHY database schema as a separate topic: Ensures the retriever does not
    # confuse "auth architecture" results with "database schema" results when
    # the user asks about one or the other.
    post("DB SCHEMA: Users table has id, email, password_hash, created_at, role columns.", thread_ts=ts3)
    post("Separate user_preferences table linked by user_id foreign key.", thread_ts=ts3)
    post("Orders join to users and products via order_items (many-to-many).", thread_ts=ts3)
    post("All tables implement soft-delete with a deleted_at timestamp column.", thread_ts=ts3)

    # WHY deployment pipeline as a separate topic: CI/CD is a common knowledge
    # domain that teams discuss frequently.  Testing it verifies RAG can handle
    # technical jargon (Terraform, Ansible, ECS Fargate, etc.).
    post("CI/CD: Push to main -> pytest + lint -> Docker build -> deploy to ECS Fargate.", thread_ts=ts3)
    post("Staging auto-deploys nightly from develop branch at midnight UTC.", thread_ts=ts3)
    post("Production requires manual approval in GitHub Actions workflow.", thread_ts=ts3)
    post("Infrastructure managed by Terraform, server config by Ansible playbooks.", thread_ts=ts3)

    # WHY monitoring & alerting as a separate topic: Tests retrieval of
    # numerical thresholds (CPU > 80%, p99 > 500ms) and proper nouns
    # (DataDog, PagerDuty), which can be challenging for embedding models.
    post("MONITORING: DataDog for APM traces, Grafana for infrastructure dashboards.", thread_ts=ts3)
    post("Alert thresholds: CPU > 80%, memory > 85%, error rate > 1%, p99 latency > 500ms.", thread_ts=ts3)
    post("Escalation: PagerDuty -> first responder (5min) -> team lead (15min) -> EM (30min).", thread_ts=ts3)
    post("Logs: CloudWatch -> Elasticsearch -> Kibana, 30-day retention.", thread_ts=ts3)

    # WHY these specific RAG queries: They are intentionally phrased
    # differently from the indexed messages to test semantic (not keyword)
    # retrieval.  "How does our authentication system work?" should retrieve
    # the JWT/RS256 messages, not the monitoring messages.
    post(f"<@{BOT_USER_ID}> how does our authentication system work?", thread_ts=ts3)
    post(f"<@{BOT_USER_ID}> what are our monitoring alert thresholds?", thread_ts=ts3)
    print(f"  Posted 19 messages (thread: {ts3})")

# ============================================================================
# 4. SUMMARIZATION TESTING THREAD
# ============================================================================
# WHY this thread: The ``/bot-summarize`` command and the summarization service
# need a realistic conversation to distill.  This thread simulates a team
# discussion with decisions, action items, and a separate bug report --
# challenging the summarizer to identify and organize multiple topics.
print("\n=== 4. Summarization Testing ===")
ts4 = post(":memo: *TEST AREA 4: Summarization*\nA realistic team discussion for testing `/bot-summarize`.")
if ts4:
    # WHY a multi-topic discussion: Real team conversations often contain
    # interleaved topics (feature discussion + bug report).  A good
    # summarizer should separate these and highlight decisions/actions.
    post("Hey team, let's discuss the new notification system design.", thread_ts=ts4)
    post("Proposal: Support email, SMS, and push notifications from day one.", thread_ts=ts4)
    post("Agreed. We also need a notification preferences page in user settings.", thread_ts=ts4)
    post("Backend: Should we use RabbitMQ or SQS for the message queue?", thread_ts=ts4)
    post("Let's go with SQS - we're already on AWS, less operational overhead.", thread_ts=ts4)
    post("Good call. We should implement retry logic with exponential backoff and jitter.", thread_ts=ts4)
    post("What about templates? Users should be able to customize notification text.", thread_ts=ts4)
    post("Handlebars templates stored in DB. Each notification type has a default template.", thread_ts=ts4)

    # WHY explicit DECISION and ACTION markers: These Slack-formatted markers
    # test whether the summarizer can identify key outcomes (decisions, action
    # items) from a longer discussion.
    post(":white_check_mark: *DECISION*: SQS for queuing, Handlebars for templates, 3 channels (email/SMS/push).", thread_ts=ts4)
    post(":point_right: *ACTION*: @alice - create DB schema for notification preferences by Thursday.", thread_ts=ts4)
    post(":point_right: *ACTION*: @bob - set up SQS queue and dead letter queue by Friday.", thread_ts=ts4)
    post(":point_right: *ACTION*: @carol - design notification preferences UI mockup by Wednesday.", thread_ts=ts4)

    # WHY a separate bug discussion in the same thread: Tests the summarizer's
    # ability to identify and separate multiple conversation topics, producing
    # a structured summary rather than a single blob.
    post("Separate topic: Users reporting session timeout even when actively using the app.", thread_ts=ts4)
    post("I've seen this too. Session expires mid-work, losing unsaved changes.", thread_ts=ts4)
    post("Root cause found: frontend isn't calling the session refresh endpoint on activity.", thread_ts=ts4)
    post("PR #234 adds an Axios interceptor to auto-refresh on 401 responses.", thread_ts=ts4)
    post(":white_check_mark: *RESOLVED*: Login timeout fix merged in PR #234, deployed to staging.", thread_ts=ts4)

    post("End of day: Notification system design finalized, login timeout bug fixed.", thread_ts=ts4)
    # WHY an in-thread summary request: Tests the bot's ability to summarize
    # the thread it is in, not just a whole channel.
    post(f"<@{BOT_USER_ID}> please summarize the discussion in this thread.", thread_ts=ts4)
    print(f"  Posted 20 messages (thread: {ts4})")

# ============================================================================
# 5. RATE LIMIT TESTING THREAD
# ============================================================================
# WHY this thread: The rate limiter (src/slack/middleware/rate_limit.py)
# enforces per-user (10/min) and per-channel (30/min) request limits.  This
# thread posts rapid @mentions to trigger the per-user limit and verify that
# the bot returns a 429 response after the threshold is crossed.
print("\n=== 5. Rate Limit Testing ===")
ts5 = post(":traffic_light: *TEST AREA 5: Rate Limiting*\nRapid messages to test per-user (10/min) and per-channel (30/min) rate limits.")
if ts5:
    post("Config: RATE_LIMIT_PER_USER=10, RATE_LIMIT_PER_CHANNEL=30 (from .env)", thread_ts=ts5)
    post("Send rapid @mentions to trigger rate limiting. Bot should return 429 after limit.", thread_ts=ts5)
    # WHY only 5 rapid messages here (not 10+): The script already posts many
    # @mentions across other threads.  Combined with these 5, the total may
    # approach or exceed the per-user limit, demonstrating rate limiting
    # without flooding the channel with 10+ identical messages.
    for i in range(1, 6):
        post(f"<@{BOT_USER_ID}> rate limit test message #{i}", thread_ts=ts5)
    post("After hitting limit, check error.log for 'Rate limit exceeded' entries.", thread_ts=ts5)
    post("Reset limits with: from src.slack.middleware.rate_limit import clear_all_rate_limits", thread_ts=ts5)
    print(f"  Posted 10 messages (thread: {ts5})")

# ============================================================================
# 6. CRON & SCHEDULER TESTING THREAD
# ============================================================================
# WHY this thread: The bot has two scheduled jobs -- memory distillation
# (weekly) and RAG re-indexing (every 2 hours).  This thread documents the
# cron configuration and provides manual testing commands so developers can
# trigger the jobs on-demand without waiting for the schedule.
print("\n=== 6. Cron & Scheduler Testing ===")
ts6 = post(":alarm_clock: *TEST AREA 6: Cron & Scheduled Jobs*\nTest memory distillation (weekly) and RAG re-indexing (every 2hrs).")
if ts6:
    # WHY document cron expressions here: Having the cron configuration
    # visible in the test channel lets developers verify it matches what is
    # in settings.py without switching context to the codebase.
    post("CRON CONFIG (from settings.py):", thread_ts=ts6)
    post("  memory_distillation_cron = '0 0 * * 0' (Sunday midnight)", thread_ts=ts6)
    post("  rag_indexing_frequency = 7200 seconds (every 2 hours)", thread_ts=ts6)
    post("To test memory distillation manually:", thread_ts=ts6)
    post("  from src.memory.manager import MemoryManager; mm = MemoryManager(); mm.recall_memory('test', 'user1', 'ch1')", thread_ts=ts6)
    post("To test RAG indexing manually:", thread_ts=ts6)
    post("  from src.rag.indexer import ConversationIndexer; indexer = ConversationIndexer(); await indexer.index_messages(messages)", thread_ts=ts6)
    # WHY check file-system artifacts: The memory and RAG subsystems write
    # files to ``memory_store/`` and ``memory_store/chroma_db/``.  Checking
    # for these files confirms that the scheduled jobs actually persisted data.
    post("Check memory_store/ directory for persisted files after interactions.", thread_ts=ts6)
    post("Check memory_store/chroma_db/ for vector store data after RAG indexing.", thread_ts=ts6)
    print(f"  Posted 10 messages (thread: {ts6})")

# ============================================================================
# 7. AGENT SYSTEM TESTING THREAD
# ============================================================================
# WHY this thread: The agent orchestrator (src/agent/orchestrator.py) is the
# brain of the bot -- it receives user messages, builds context from memory
# and RAG, calls the Claude LLM, and may invoke MCP tools (Slack, GitHub,
# Notion).  This thread tests the full end-to-end pipeline by asking
# questions that require the agent to use different tools and capabilities.
print("\n=== 7. Agent System Testing ===")
ts7 = post(":robot_face: *TEST AREA 7: Agent Orchestrator*\nTest the Claude-powered agent with tool calling and context building.")
if ts7:
    # WHY these specific questions: Each question is designed to exercise a
    # different agent capability:
    #   - "what channels are available" -> tests Slack MCP tool (list_channels)
    #   - "check recent messages" -> tests Slack MCP tool (get_channel_messages)
    #   - "create a summary" -> tests summarization integration
    #   - "what tools do you have" -> tests the agent's self-awareness of its
    #     tool inventory (useful for debugging tool registration issues)
    post(f"<@{BOT_USER_ID}> what channels are available in this workspace?", thread_ts=ts7)
    post(f"<@{BOT_USER_ID}> can you check the recent messages in this channel?", thread_ts=ts7)
    post(f"<@{BOT_USER_ID}> create a summary of what's been discussed today.", thread_ts=ts7)
    post(f"<@{BOT_USER_ID}> what tools do you have available?", thread_ts=ts7)
    post("Test tool calling: The agent should use Slack MCP tools (get_channel_messages, post_message).", thread_ts=ts7)
    post("Test context: The agent should build context from memory + RAG before responding.", thread_ts=ts7)
    print(f"  Posted 7 messages (thread: {ts7})")

# ============================================================================
# Summary
# ============================================================================
# WHY print a summary: After posting ~85 messages across 7 threads, the
# developer needs a quick reference to find each thread and know what to
# verify.  Printing the thread timestamps (``ts``) lets them construct
# deep-links to specific threads in Slack if needed.
print("\n" + "=" * 60)
print("TEST DATA SETUP COMPLETE")
print("=" * 60)
print(f"\nAll messages posted to: #new-channel ({CHANNEL_ID})")
print("\nTest threads created:")
threads = {
    "1. Heartbeat & Slash Cmds": ts1,
    "2. Memory System": ts2,
    "3. RAG Knowledge Base": ts3,
    "4. Summarization": ts4,
    "5. Rate Limiting": ts5,
    "6. Cron & Scheduler": ts6,
    "7. Agent Orchestrator": ts7,
}
for name, ts in threads.items():
    print(f"  {name}: ts={ts}")

# WHY a quick test guide: Saves the developer from having to re-read the
# script or documentation to remember what to check for each subsystem.
# Each line maps a test area to its expected behavior, making it easy to
# mark off pass/fail during manual verification.
print("\n--- Quick Test Guide ---")
print("1. HEARTBEAT:  Go to thread 1, check bot responded to mentions")
print("2. SLASH CMDS: Type /bot-help and /bot-status in #new-channel")
print("3. MEMORY:     Go to thread 2, check if bot recalls Alice, sprint, deployments")
print("4. RAG:        Run indexer on #new-channel, then query in thread 3")
print("5. SUMMARIZE:  Type /bot-summarize in #new-channel")
print("6. RATE LIMIT: Spam @mentions in thread 5, check error.log for 429s")
print("7. CRON:       Check memory_store/ for persisted data, chroma_db/ for vectors")
print("8. AGENT:      Go to thread 7, check if bot uses tools and builds context")
print("\nBot must be running: python src/main.py")
