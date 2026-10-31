## Change

Describe the problem and the resulting behavior.

## Verification

List commands run and results, plus any checks not run and why.

- [ ] Feature/fix/docs PR targets `dev`; release PR is upstream `dev` → `master`.
- [ ] `make check` passes; relevant behavior has regression coverage.
- [ ] Dependency changes pass `make audit` and preserve a current `uv.lock`.
- [ ] Documentation reflects changed behavior or setup.
- [ ] Fixtures are synthetic; no credentials or private datasets are included.

Describe security implications or limitations if relevant. Leave merging to
the maintainer. See [contributor guidance](../CONTRIBUTING.md).
