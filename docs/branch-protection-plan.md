# Branch Protection

Repository: `dosorio79/datasetpeek`

Branch protection is managed with Terraform in [infra/github](../infra/github).
Do not edit these rules manually in the GitHub UI except for emergency recovery.

## Prepared policy — not yet applied

Both `dev` (integration) and `master` (release) require a PR, up-to-date branch,
resolved conversations, and these exact CI jobs: `test`, `quality`,
`dependency-audit`, `branch-policy`. Force pushes and deletion are disabled;
admin enforcement is enabled. Signed commits are not required.

Feature branches start at `dev` and open PRs into `dev`. Only same-repository
`dev` → `master` passes the release branch check. Use merge commits for releases.
See [CONTRIBUTING.md](../CONTRIBUTING.md) for the complete workflow.
After each release, create a short-lived sync branch from `dev`, merge `master`
into it, and merge its PR into `dev` with a merge commit. Never squash that sync:
strict status checks require release ancestry to reach `dev` before the next release.

Required approving reviews stay at zero so the owner can release alone. Prefer
fork contributors without upstream write access: only the owner can merge.
Granting write access makes owner-only merging a convention, not an enforced
restriction. The branch-policy workflow prevents accidental routing errors; it
is not an authorization boundary against a writer who can propose workflow edits.

## Rollout prerequisites

The previous checked-in policy required only `test` on `master` and allowed
direct pushes to `dev`. This change prepares stricter rules without applying them.

1. Publish the workflow and tooling through the currently available PR flow.
2. Observe all four successful job names on PRs into `dev` and `master`.
3. Merge configuration into `master` so schedules and Dependabot can activate.
4. Review a fresh Terraform plan, then apply with owner authorization.
5. Verify live protections and a subsequent no-drift plan. Test branch routing
   on actual PRs before relying on it for collaborators.

Do not apply early: absent required contexts can prevent merging. CodeQL,
Dependabot security updates, and private reporting are separate pending GitHub
settings; secret scanning and push protection were already enabled when read
on 2026-10-31. No collaborator has been invited by this implementation.

## Apply Changes

Create a local ignored `infra/github/terraform.tfvars` file with a GitHub token:

```hcl
github_token = "..."
```

Then run:

```bash
cd infra/github
terraform init
terraform fmt
terraform validate
terraform plan
terraform apply
```

## Verify

After applying, run:

```bash
cd infra/github
terraform plan
```

Expected result:

```text
No changes. Your infrastructure matches the configuration.
```

## Notes

- Commit `.terraform.lock.hcl`.
- Do not commit `terraform.tfvars`, `terraform.tfstate`, `terraform.tfstate.backup`, or `.terraform/`.
- If regular independent review becomes desirable, agree an approval policy
  before changing `required_approving_review_count`; the owner cannot approve
  their own release PR.
