# Releasing

Releases are performed by the repository owner after the recorded acceptance
gates. General implementation permission is not paid-inference permission.

1. Confirm independent integration and release-candidate reviews have no
   unresolved substantive findings, all required/native CI is green, and the
   current-Hermes advisory passed on the exact candidate.
2. Confirm canonical public catalogue provenance and generated exports match.
   Record actual offline, live and device results in `docs/validation.md`.
3. Prepare the versioned manifests, changelog, migration/rollback notes and the
   two component README/licence/disclosure surfaces. Both components use one
   release version. Validate each component alone with
   `hermes plugins validate <component> --install-deps` in isolated tooling.
   Dependency-preparation errors must be resolved even if a subsequent static
   report exits successfully.
4. Test a `git archive` of the candidate, including shell install/verify/remove,
   native install/update/remove and media without a chat sibling. Generate the
   pack using that exact candidate SHA and validate its native parser/contents.
5. After bounded live/provider and platform acceptance, merge the integration
   PR with a merge commit, preserving the feature histories. Recheck the exact
   main merge commit and its archive; do not infer its status from a PR head.
6. Tag that verified merge commit `vX.Y.Z`. Build the coordinated pack:

   ```bash
   python3 scripts/build-release-pack.py --sha <full-merge-sha> --output /tmp/hermes-pack.yaml
   ```

   The generated release asset pins both component subdirectories to the same
   reviewed commit. Do not try to commit a file containing its own commit SHA.
7. Publish the GitHub release with `hermes-pack.yaml`, concise compatibility and
   migration notes, evidence limits and rollback instructions. Verify the
   tag-triggered CI and download/install the published assets again.
8. Submit two coordinated **community** catalog entries in one upstream Hermes
   PR, each pinned to the full release SHA with the correct subdirectory,
   version, declared capabilities and disclosures. Catalog admission is a
   maintainer decision; publication to the official catalog does not confer
   `tier: official`. Before acceptance, the release pack remains a custom pinned
   install with explicit re-pin semantics.
9. Update the project tracker, Orca comments and linked feature PRs/issues with
   the release and catalog submission. Retain worktrees until release checks
   pass. Keep catalog CI/review follow-up distinct from completed local delivery.

Do not move or replace published tags. Correct a published problem in a new
version and a newly reviewed catalog SHA-bump PR. No silent self-updating code.
