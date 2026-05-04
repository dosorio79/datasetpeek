terraform {
  required_providers {
    github = {
      source  = "integrations/github"
      version = "~> 6.0"
    }
  }
}

provider "github" {
  token = var.github_token
  owner = var.owner
}

# master: fully protected

resource "github_branch_protection" "master" {
  repository_id = var.repository
  pattern       = "master"

  # PR required before merging (at least 1 approval)
  required_pull_request_reviews {
    required_approving_review_count = 1
    dismiss_stale_reviews           = true
  }

  # CI must pass (the "test" job from .github/workflows/ci.yml)
  required_status_checks {
    strict   = true
    contexts = ["test"]
  }

  require_signed_commits = true
  allows_force_pushes    = false
  allows_deletions       = false
  enforce_admins         = true # no bypassing settings
}

# dev: semi-open

resource "github_branch_protection" "dev" {
  repository_id = var.repository
  pattern       = "dev"

  # No PR requirement - direct pushes allowed
  allows_force_pushes = false
  allows_deletions    = true
}
