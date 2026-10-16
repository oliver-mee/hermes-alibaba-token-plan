# Validation and release gates

Native media is implemented and opt-in. Catalogue discovery, registration,
static admission and mocked tests are different evidence from paid inference,
playable artifacts and actual platform delivery.

## Current integrated candidate

- Linux/Python3.11, pinned Hermes v0.22.0 (`e06df9c2`): complete offline suite
  **381 passed, 8 outer-suite native-video skips**, with those native cases run
  in the real-Hermes subprocess. Synthetic credentials, isolated homes and
  external socket connections blocked; loopback is permitted for WebSocket tests.
- Shell installer acceptance: **63 passed**, including package rollback,
  ownership and preview guards, source/path checks, backups and failure injection.
- Separate component admission/security/isolation checks pass on the inspected
  source tree. Real native package-manager dependency preparation and lifecycle,
  final archive checks and hosted integrated CI are still pending.
- Live gateway/inference, Token Plan credit deduction, rendered/playable vendor
  output and actual Telegram/Desktop delivery: **Not run**. No operator key was
  accessed by these checks. See [the proposed bounded live gate](live-acceptance.md).

A later candidate changes the evidence boundary: rerun checks affected by its
diff and update this record with the actual SHA/results. Do not copy a previous
branch's green checks onto a new integrated commit.

## Native contracts and compatibility

Chat retains existing provider aliases, credential precedence and older Hermes
compatibility points. Combined media is tested through native registration and
normal image/video/TTS/transcription dispatch on Hermes v0.22.0. Its metadata is
self-contained; media-only and chat-plus-media installations are both exercised.
Generated catalogue order is preserved. Personal/Team and Global/CN namespaces
remain isolated. ASR intentionally exposes only historically supported Global
Personal; exact-ID unlisted evidence is retained.

Static admission warns about some safety/conversion/cancellation helper imports
that Hermes classifies as private APIs. They are not runtime monkey patches;
keep the warnings in review evidence and test the pinned/current host again on
updates. ffmpeg/ffprobe subprocess use and file/network behaviour are disclosed
in the media component README. A scanner's static host-ready verdict does not
prove dispatched execution under plugin-host isolation.

## Release acceptance

The release requires independent critical reviews of design, integration and
the final candidate; all combined CI lanes; current-Hermes advisory; component
admission with dependencies prepared successfully; archive installation and
native package lifecycle; and approved live/device acceptance. Native packs use
normal consent and are not an atomic multi-component transaction. Explicit
repository pins have custom provenance until installed through accepted catalog
entries. Unverified accounts/modes stay experimental rather than being labelled
working from `/models` alone. No claim of direct realtime calling or PCM streaming.
