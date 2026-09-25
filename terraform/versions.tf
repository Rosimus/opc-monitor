terraform {
  required_version = ">= 1.5.0"

  required_providers {
    yandex = {
      source  = "yandex-cloud/yandex"
      version = "~> 0.110"
    }
  }

  # Backend для хранения state
  # Раскомментировать для production (Object Storage Yandex Cloud)
  # backend "s3" {
  #   endpoints = {
  #     s3 = "https://storage.yandexcloud.net"
  #   }
  #   bucket                      = "opc-monitor-tfstate"
  #   key                         = "prod/terraform.tfstate"
  #   region                      = "ru-central1"
  #   skip_region_validation      = true
  #   skip_credentials_validation = true
  #   skip_requesting_account_id  = true
  #   skip_s3_checksum            = true
  # }
}