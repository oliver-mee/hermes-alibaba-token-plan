# Alibaba Token Plan chat

Four Hermes chat providers separate Global/China and Personal/Team subscriptions,
with canonical entitlement-aware catalogues, exact-ID unlisted exceptions,
reasoning controls and legacy credential aliases.

Published following [upstream's standalone-plugin direction](https://github.com/NousResearch/hermes-agent/pull/52915#issuecomment-4976935709),
this improves the bundled basic Personal profiles using Hermes's supported user-provider
overrides. It adds explicit Team profiles, current tier-aware discovery, scoped
credential/cache isolation, model-specific reasoning controls and a lower-cost
auxiliary model, while preserving existing provider identities and aliases.

This is the chat component of the [Token Plan integration](https://github.com/oliver-mee/hermes-alibaba-token-plan).
Install it independently or use the coordinated release pack to add native image,
video, speech and transcription. Native package installation does not run the
repository's shell installer. Migrate legacy shell installations first to avoid
simultaneous category and flat copies. No credentials or defaults are changed by
this component's import.

Chat discovery sends a selected account's scoped key to its Token Plan models
endpoint; inference uses the corresponding regional Chat Completions endpoint.
It does not use DashScope PAYG credentials. `/models` is not proof of inference
health. Configure only credentials for accounts you hold; the full repository
[README](https://github.com/oliver-mee/hermes-alibaba-token-plan#credentials)
lists the canonical keys and backward-compatible aliases.

Hermes v0.18.2/v0.19.0 compatibility points and native v0.22.0 are tested. Linux
and macOS, Python3.11/3.13. No telemetry, separate hosting, automatic provider
selection or self-updating code. MIT licence included.
