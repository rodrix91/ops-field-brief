# GitHub release integrity and historical v0.3.0 recovery

This repository publishes **GitHub Releases only**, not PyPI packages.
Publishing is a separate, deliberate action from merging pull requests.
Never tag the current `main` commit on behalf of an older version.

## Historical v0.3.0 release

The release commit, verified against its source version, is:

```text
v0.3.0  98e96160fc965bb382aca17301fb37da2ccec89f
```

No public `v0.3.0` release or tag was present at the most recent review
(2026-11-18). Check again before doing anything. The safest recovery path is
an **annotated tag on this exact commit**, created from a clean checkout:

```bash
git fetch origin --tags
git cat-file -e 98e96160fc965bb382aca17301fb37da2ccec89f^{commit}
git show 98e96160fc965bb382aca17301fb37da2ccec89f:src/ops_field_brief/__init__.py
git ls-remote --tags origin refs/tags/v0.3.0
```

Verify the module declares version `0.3.0`. The final command must return
**no existing tag**. If one exists, inspect it and **do not overwrite it**.
Then, only after intentional publication approval:

```bash
git tag -a v0.3.0 98e96160fc965bb382aca17301fb37da2ccec89f -m "v0.3.0"
git rev-parse v0.3.0^{}
git push origin refs/tags/v0.3.0
```

The peeled commit from `git rev-parse` must equal the exact commit shown
above. Do not use `--force`, `git tag -f`, or a moving branch reference.
Check the [release workflow](https://github.com/rodrix91/ops-field-brief/actions/workflows/release.yml)
and the [GitHub Releases page](https://github.com/rodrix91/ops-field-brief/releases)
after pushing. Confirm that both a wheel and source distribution are attached
and that both smoke tests completed successfully.

**Historical workflow caveat:** GitHub executes the workflow from the tagged
historical commit. Improvements introduced later on `main` are **not
retroactive**. In particular, newer checksum, attestation, action pinning and
hashed build-tooling steps must never be claimed for the old release unless
they are present in that exact tagged commit or have separately been
performed and verified.

## Future release safeguards

For future versions using the updated `.github/workflows/release.yml`:

- Tag/version consistency is verified before packaging.
- Build tooling is installed with `--require-hashes` from the already reviewed
  `requirements-dev.lock`, after checking its correspondence with declared
  development dependencies.
- Installed wheel and unpacked sdist are exercised before publication, and
  SHA-256 checksums and provenance attestations are generated.
- A tag's **existing GitHub Release is never overwritten** on a rerun.
  Investigate a failed or partial release and preserve its artifacts rather
  than applying `--clobber`.

These rules are verified by `tests/test_release_supply_chain.py` in the
normal offline CI. Release creation still requires a separately approved
tag push. The repository's automated tests do **not** deploy the application
or publish a new release.
