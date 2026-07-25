# Contributing

Keep changes small and evidence-based.

1. Open an issue or describe the gateway behaviour the change addresses.
2. Preserve both provider slugs, endpoints, aliases, and credential namespaces.
3. Treat `DASHSCOPE_API_KEY` as out of scope for Token Plan.
4. Update catalogue constants only from the parent project's generated `build/hermes/fallback_models.py`, preserving order.
5. Add or update the smallest regression test that proves the behaviour.
6. Run:

   ```bash
   python3 -m pytest -q
   bash -n install.sh
   python3 -m compileall -q alibaba-token-plan tests
   git diff --check
   ```

Do not include credentials, private endpoints, account identifiers, or local filesystem paths in commits or test output. Live checks must be bounded, interactive, and must never print keys.
