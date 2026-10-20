# Contributing

Thank you for improving the Hermes Alibaba Token Plan plugin. Bug fixes,
documentation, compatibility work, and new features are all welcome. You do
not need approval before implementing a feature, although maintainers decide
what is merged and released.

## Before you start

- Search existing issues and pull requests for related work.
- Open an issue for non-trivial work. A feature issue and its pull request may
  be submitted together.
- Keep each pull request focused on one concern.
- Never include credentials, account identifiers, private endpoints, internal
  hostnames, or local filesystem paths in commits, screenshots, or logs.
- Preserve both provider slugs, endpoints, aliases, and credential namespaces
  unless the change explicitly intends a documented breaking release.
- Keep `DASHSCOPE_API_KEY` outside Token Plan routing.

## Evidence and honest validation

Pull requests must say exactly what was tested, what was not tested, and why.
Missing access to a regional account or paid service is not a reason to invent
a result or mark a working integration as defunct. Use `Not run` and explain
the limitation. A maintainer can perform additional checks before merge.

Do not treat a successful `/models` response as proof that inference works. A
lapsed subscription can return a plausible catalogue while denying every
model call.

The pull request validation table uses four statuses:

- `Passed`
- `Failed`
- `Not run`
- `Not applicable`

Every row needs brief evidence or a reason. Do not use vague claims such as
“all tests pass” without naming the command or observation.

## AI-assisted contributions and live checks

Disclose whether an AI system helped create the change and name the model when
known. The human submitter remains responsible for reviewing the diff,
validation claims, and any external actions.

An AI system must not retrieve credentials or perform a live gateway,
inference, billing, or other token-consuming check unless the person directing
it has given express, informed permission for that check. Permission must cover
the service and endpoint, the models or operations, the maximum number of
calls or token budget, and the possible cost. General permission to “test the
change” is not enough.

Live checks must be:

- necessary for the change;
- bounded to the smallest useful request;
- interactive rather than unattended or batched;
- performed without printing credentials; and
- recorded in the pull request with the endpoint class, model, call count, and
  result, but never the key.

Offline tests and mocks should cover everything that does not require a live
subscription. Contributors are not expected to buy or possess Personal, Team,
Global, and China credentials.

## Catalogue changes

The public catalogue snapshot and evidence live in the
[Alibaba Token Plan Wiki](https://github.com/oliver-mee/alibaba-token-plan-wiki).
Do not hand-reorder the Personal or Team model constants. Preserve the
canonical public snapshot order and include evidence for additions, removals,
or capability changes.

The gateway is the final authority when current documentation and measured
behaviour disagree. Record the date and method of any live observation.

## Local checks

Install the pinned development dependency in a virtual environment:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

Run the checks relevant to your change:

```bash
python -m pytest -q
bash -n install.sh
python -m compileall -q alibaba-token-plan tests
git diff --check
```

The integration test requires a local Hermes checkout, but does not require a
live Token Plan key:

```bash
HERMES_AGENT_REPO=/path/to/hermes-agent \
  python -m pytest tests/test_current_hermes_integration.py -q
```

CI tests Linux and macOS, Python 3.11 and 3.13, and the supported Hermes
compatibility points. A weekly advisory job also checks current Hermes `main`.

## Pull requests

Choose the matching pull request template and keep its hidden template marker.
The policy check requires:

- a closing issue reference;
- a concise problem, solution, and scope;
- the complete validation table;
- honest evidence for every validation status; and
- an AI-assistance disclosure.

Maintainer approval is required before merge. Squash merge is the default;
merge commits may be used when preserving meaningful contributor history.

See [RELEASING.md](RELEASING.md) for the maintainer-only release process and
[SECURITY.md](SECURITY.md) for private vulnerability reporting.

## Combined media and native package checks

The default `python -m pytest -q` runs this repository's `tests/` only. Without
`HERMES_AGENT_REPO`, native-host checks skip and standalone contracts still run.
For the complete offline provider/dispatcher coverage:

```bash
HERMES_AGENT_REPO=/path/to/reviewed/hermes-agent \
  python -m pytest -q --ignore=tests/test_native_package.py
```

Native package-manager lifecycle checks additionally require Hermes's real PM
runtime and public dependency closure. Prepare it in a **new scratch directory**
from a clean pinned Hermes checkout, using a normal bootstrap Python:

```bash
python3 scripts/prepare-native-package-tests.py \
  --hermes-repo /path/to/reviewed/hermes-agent \
  --scratch-dir /tmp/token-plan-native-tests
```

Use the emitted scratch `HERMES_AGENT_REPO` and `HERMES_NATIVE_PACKAGE_SEED`
values when running `tests/test_native_package.py`. The preparer defaults to
Hermes v0.22.0's exact SHA; another reviewed SHA must be explicit. It archives
committed sources only, never the operator's untracked files or active runtime.

Set `HERMES_NATIVE_PACKAGE_DOWNLOADS=1` for lifecycle/pack tests when upstream PM
needs to revalidate public dependency metadata. That mode permits public PM
worker downloads in isolated test homes; it does not access account credentials
or invoke a provider. These are **no-inference lifecycle checks**, not entirely
offline tests. Admission/collision tests retain network denial (Linux requires
libseccomp; macOS uses sandbox-exec). Without the explicit download mode, PM
lifecycle tests keep the strict offline boundary and fail on missing/revalidated
metadata rather than pretending that installation was accepted.

Do not run admission `--install-deps` in the production Hermes environment.
Check that dependency preparation succeeded: a subsequent static validation
report alone does not prove that the native dependency transaction completed.
