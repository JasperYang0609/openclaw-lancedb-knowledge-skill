# Gemini Keychain Human Gate Implementation Plan

Date: 2026-09-08
Status: approved for implementation

## Objective

Prepare the Gemini embedding edition up to the API-key human gate without calling Google, changing the active search provider, or stopping Qwen.

## Steps

1. Add a fixed-identity macOS Keychain utility that stores the secret through the native hidden prompt, checks only item presence, and injects the secret into a fixed Gemini CLI child process in memory.
2. Remove the legacy OpenClaw provider-config fallback so this project can use only the dedicated embedding key supplied by the Keychain wrapper.
3. Route the packaged search and incremental scripts through the wrapper.
4. Add negative tests for secret arguments, malformed keys, command allowlisting, environment replacement, and redacted failures.
5. Update the executable-surface allowlist, operator documentation, deterministic skill archive, task record, and OWASP closeout.
6. Run the complete repository tests and security checks, commit, and push the reviewed candidate.
7. Stop at the human gate and give Jasper the one-line hidden-input command from the reviewed repository. Install into the managed Gemini project only after the key canary passes, so this phase cannot disturb Qwen or live routing.

## Non-goals

- No Gemini API call before Jasper enters the key.
- No full index rebuild, cron enablement, Qwen stop, or provider cutover in this phase.
- No secret value in argv, Git, logs, configuration files, or chat.

## Completion gate

The phase is complete only when the reviewed tool is committed and pushed, its metadata-only check reports the key as absent/present without revealing it, and Qwen remains the active provider. Managed installation belongs to the post-key cutover phase.
