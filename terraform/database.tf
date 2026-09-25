# ============================================
# Managed PostgreSQL cluster
# ============================================
resource "yandex_mdb_postgresql_cluster" "opc_monitor" {
  name        = "${local.name_prefix}-postgres"
  description = "PostgreSQL for OPC Monitor"
  environment = var.environment == "prod" ? "PRODUCTION" : "PRESTABLE"
  network_id  = yandex_vpc_network.k3s.id
  labels      = local.common_labels

  config {
    version = "15"

    resources {
      resource_preset_id = "s2.micro"
      disk_type_id       = "network-ssd"
      disk_size          = 20
    }

    postgresql_config = {
      max_connections = 100
    }
  }

  host {
    zone      = var.master_zone
    subnet_id = yandex_vpc_subnet.public.id
  }

  security_group_ids = [yandex_vpc_security_group.k3s.id]
}

resource "yandex_mdb_postgresql_database" "opc_monitor" {
  cluster_id = yandex_mdb_postgresql_cluster.opc_monitor.id
  name       = "opc_monitor"
  owner      = "opc_user"
}

resource "yandex_mdb_postgresql_user" "opc_user" {
  cluster_id = yandex_mdb_postgresql_cluster.opc_monitor.id
  name       = "opc_user"
  password   = var.postgres_password

  depends_on = [yandex_mdb_postgresql_database.opc_monitor]
}