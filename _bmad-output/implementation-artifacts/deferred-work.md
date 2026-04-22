# Deferred Work

- **Request timeout for sequential LLM calls** — 3 blocking Anthropic API calls with no timeout. Could hang ~180s under slow conditions. Consider `asyncio.wait_for` or async API calls with timeout. Low priority for single-user research rig.
