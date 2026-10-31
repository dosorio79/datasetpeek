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

  # Fork contributors cannot merge upstream; the owner can release without self-review.
  required_pull_request_reviews {
    required_approving_review_count = 0
    dismiss_stale_reviews           = true
  }

  # Apply only after these jobs have passed on published PRs.
  required_status_checks {
    strict   = true
    contexts = ["test", "quality", "dependency-audit", "branch-policy"]
  }

  require_signed_commits          = false
  allows_force_pushes             = false
  allows_deletions                = false
  enforce_admins                  = true # no bypassing settings
  require_conversation_resolution = true
}

# dev: protected integration branch

resource "github_branch_protection" "dev" {
  repository_id = var.repository
  pattern       = "dev"

  required_pull_request_reviews {
    required_approving_review_count = 0
    dismiss_stale_reviews           = true
  }

  required_status_checks {
    strict   = true
    contexts = ["test", "quality", "dependency-audit", "branch-policy"]
  }

  allows_force_pushes             = false
  allows_deletions                = false
  enforce_admins                  = true
  require_conversation_resolution = true
}
