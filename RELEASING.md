# Releasing Fencewalk

Nothing in the packaging slice publishes anything. Every step below
is Nate's hands, run from a checkout of this repo. Do not run any
step here as part of a build or a review.

## 1. One-time setup

- Create a PyPI account at https://pypi.org/account/register/ (if
  there is not one already).
- Enable two-factor authentication on the PyPI account. PyPI
  requires 2FA for uploading.
- Create an API token (PyPI account settings → API tokens).
  For the FIRST upload it must be account-scoped (scope: Entire
  account): PyPI can only scope a token to a project that already
  exists, and the project is created by the first upload. After
  the first successful publish, replace it with a project-scoped
  token for `fencewalk` (scope: Project: fencewalk) and delete
  the account-scoped token. The same rule holds on TestPyPI: the
  first TestPyPI token is account-scoped, then project-scoped
  after the first TestPyPI upload. Keep token values in the
  password manager; no credential value goes in this file or
  anywhere in the repo.

## 2. Version bump

Edit exactly one place: `src/fencewalk/__init__.py`, `__version__`.
The version is typed nowhere else — `pyproject.toml` reads it from
there (`version = {attr = "fencewalk.__version__"}`), and
`fencewalk --version` prints it. Follow semver afterwards. First
public release is `0.1.0`.

## 3. Build and verify

From the repo root, in a throwaway venv used only for building:

```sh
python3 -m venv /tmp/fw-build-venv
/tmp/fw-build-venv/bin/pip install build
/tmp/fw-build-venv/bin/python -m build
```

Inspect what was built before it goes anywhere:

```sh
python3 -m zipfile -l dist/*.whl
python3 -c "import zipfile, glob; z = zipfile.ZipFile(glob.glob('dist/*.whl')[0]); print(z.read([n for n in z.namelist() if n.endswith('METADATA')][0]).decode())"
```

Check: the wheel contains all five pack JSONs, all nine fixture
files, and the run-brief template; METADATA names `fencewalk`
version `0.1.0` and carries no `Requires-Dist` lines (zero runtime
dependencies).

Then install the wheel into a fresh venv with no repo on the path
and no PYTHONPATH, and run the stranger loop:

```sh
python3 -m venv /tmp/fw-install-venv
/tmp/fw-install-venv/bin/pip install dist/*.whl
/tmp/fw-install-venv/bin/fencewalk --version        # fencewalk 0.1.0
mkdir -p /tmp/fw-stranger && cd /tmp/fw-stranger
/tmp/fw-install-venv/bin/fencewalk packs            # all five packs listed
/tmp/fw-install-venv/bin/fencewalk load-fixture reference-case eng.db
/tmp/fw-install-venv/bin/fencewalk load-pack eng.db scuba-m365-v2.0.0
/tmp/fw-install-venv/bin/fencewalk report eng.db > report.md
# report.md must be byte-identical to the bundled EXPECTED-REPORT.md
# (FLASH sorts first alphabetically, so the added SCuBA pack changes nothing)
/tmp/fw-install-venv/bin/fencewalk packet eng.db --out packet.md
/tmp/fw-install-venv/bin/fencewalk pdf eng.db --out report.pdf
pdfinfo report.pdf
```

The packet step is the proof the run-brief template resolves when
installed. If any step fails, stop: fix it in a new slice, do not
publish around it.

## 4. TestPyPI first

Install `twine` into the build venv (it is an upload tool, not a
project dependency, and it is never installed by the project):

```sh
/tmp/fw-build-venv/bin/pip install twine
/tmp/fw-build-venv/bin/twine upload --repository testpypi dist/*
```

Then install from TestPyPI in a fresh venv and run the stranger
loop once (step 3, with `pip install --index-url
https://test.pypi.org/simple/ fencewalk` instead of the wheel
file).

## 5. Publish

```sh
/tmp/fw-build-venv/bin/twine upload dist/*
```

## 6. Post-publish check

Fresh venv, install the published package the way a stranger
would, and run the stranger loop once more against it:

```sh
python3 -m venv /tmp/fw-published-venv
/tmp/fw-published-venv/bin/pip install pipx   # only if pipx is not installed
pipx install fencewalk
fencewalk --version
# stranger loop from step 3, with `fencewalk` on PATH
```

## 7. Tag the release

Create the GitHub tag `vX.Y.Z` matching `__version__` on the merge
commit (the repo has no tags yet; this establishes the convention):

```sh
git tag v0.1.0 <merge-commit-sha>
git push origin v0.1.0
```
