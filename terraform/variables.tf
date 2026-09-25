# ============================================
# Yandex Cloud credentials
# ============================================
variable "yc_token" {
  description = "Yandex Cloud OAuth token"
  type        = string
  sensitive   = true
}

variable "yc_cloud_id" {
  description = "Yandex Cloud ID"
  type        = string
}

variable "yc_folder_id" {
  description = "Yandex Cloud folder ID"
  type        = string
}

# ============================================
# Environment
# ============================================
variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "prod"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

# ============================================
# SSH access
# ============================================
variable "ssh_public_key" {
  description = "SSH public key for VM access"
  type        = string
}

variable "allowed_ssh_cidr" {
  description = "CIDR allowed for SSH access"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

# ============================================
# Cluster configuration
# ============================================
variable "master_zone" {
  description = "Availability zone for master node"
  type        = string
  default     = "ru-central1-a"
}

variable "worker_zones" {
  description = "Availability zones for worker nodes"
  type        = list(string)
  default     = ["ru-central1-a", "ru-central1-b"]
}

variable "master_cores" {
  description = "Number of CPU cores for master"
  type        = number
  default     = 2
}

variable "master_memory" {
  description = "Memory in GB for master"
  type        = number
  default     = 4
}

variable "worker_cores" {
  description = "Number of CPU cores for workers"
  type        = number
  default     = 2
}

variable "worker_memory" {
  description = "Memory in GB for workers"
  type        = number
  default     = 4
}

# ============================================
# Database
# ============================================
variable "postgres_password" {
  description = "PostgreSQL admin password"
  type        = string
  sensitive   = true
  default     = ""
}

# ============================================
# k3s token
# ============================================
variable "k3s_token" {
  description = "k3s cluster join token"
  type        = string
  sensitive   = true
  default     = ""
}