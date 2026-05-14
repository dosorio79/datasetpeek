# Branch Protection

Repository: `dosorio79/datasetpeek`

Branch protection is managed with Terraform in [infra/github](../infra/github).
Do not edit these rules manually in the GitHub UI except for emergency recovery.

## Policy

`master` is the protected release branch:

- Pull request required before merge.
- Required approving reviews: `0`, because this is a solo-maintained repo.
- Required status check: `test` from [.github/workflows/ci.yml](../.github/workflows/ci.yml).
- Branch must be up to date before merge.
- Force pushes disabled.
- Branch deletion disabled.
- Admin enforcement enabled.
- Signed commits are not required.

`dev` is the working branch:

- Direct pushes allowed.
- Force pushes disabled.
- Branch deletion allowed.
- Pull requests and status checks are not required.

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
- If this repo later gains regular reviewers, raise `required_approving_review_count` in [main.tf](../infra/github/main.tf) from `0` to `1`.
