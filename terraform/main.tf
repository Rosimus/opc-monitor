# ============================================
# Provider configuration
# ============================================
provider "yandex" {
  token     = var.yc_token
  cloud_id  = var.yc_cloud_id
  folder_id = var.yc_folder_id
  zone      = var.master_zone
}

# ============================================
# Local values
# ============================================
locals {
  name_prefix = "opc-monitor-${var.environment}"

  common_labels = {
    project     = "opc-monitor"
    environment = var.environment
    managed_by  = "terraform"
  }
}