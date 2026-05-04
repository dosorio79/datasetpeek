# Branch Protection Plan

Repository: dosorio79/datapeek

Branch protection is managed as Terraform in [infra/github](../infra/github).
The GitHub UI path below is retained only as a manual fallback.

## Terraform

The Terraform config protects:
- `master`: PR required, 1 approval, stale review dismissal, CI status check `test`, signed commits, no force pushes, no deletion, admin enforcement.
- `dev`: no force pushes, deletion allowed, no PR requirement.

Apply flow:

```bash
cd infra/github
terraform init
terraform plan -var='github_token=...'
terraform apply -var='github_token=...'
```

You can also provide the token via a local ignored `terraform.tfvars` file.

## Path 1: Protect master

Target policy:
- PR required
- CI required
- No force push
- No deletion
- Signed commits required

Click path:
1. Open GitHub repo: dosorio79/datapeek.
2. Go to Settings -> Branches.
3. Under Branch protection rules, click Add rule.
4. Branch name pattern: master.
5. Turn on Require a pull request before merging.
6. In that section, keep at least 1 approval required.
7. Turn on Require status checks to pass before merging.
8. In required checks, select test (job from CI workflow).
9. Turn on Require signed commits.
10. Ensure Allow force pushes is off.
11. Ensure Allow deletions is off.
12. Click Create (or Save changes).

Recommended strictness:
- Turn on Do not allow bypassing the above settings.

## Path 2: Leave dev semi-open

Target policy:
- No force push
- CI required only if easy (optional)
- PR not required

Click path:
1. Open GitHub repo: dosorio79/datapeek.
2. Go to Settings -> Branches.
3. Under Branch protection rules, click Add rule.
4. Branch name pattern: dev.
5. Leave Require a pull request before merging off.
6. Ensure Allow force pushes is off.
7. Leave Allow deletions on (semi-open).
8. CI option:
   - If you want CI enforced now, turn on Require status checks to pass before merging and select test.
   - If you want faster iteration, leave status checks off for now.
9. Click Create (or Save changes).

## Notes
- The status check to use is test from the CI workflow at [.github/workflows/ci.yml](../.github/workflows/ci.yml).
- If your default branch is main, use main instead of master in the branch name pattern.
