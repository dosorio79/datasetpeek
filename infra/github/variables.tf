variable "github_token" {
  description = "GitHub personal access token with repo admin permissions"
  type        = string
  sensitive   = true
}

variable "repository" {
  description = "GitHub repository name"
  type        = string
  default     = "datasetpeek"
}

variable "owner" {
  description = "GitHub organization or user that owns the repository"
  type        = string
  default     = "dosorio79"
}
