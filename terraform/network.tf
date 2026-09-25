# ============================================
# VPC Network
# ============================================
resource "yandex_vpc_network" "k3s" {
  name        = "${local.name_prefix}-net"
  description = "VPC for OPC Monitor k3s cluster"
  labels      = local.common_labels
}

# ============================================
# Public subnet (for master node)
# ============================================
resource "yandex_vpc_subnet" "public" {
  name           = "${local.name_prefix}-public"
  zone           = var.master_zone
  network_id     = yandex_vpc_network.k3s.id
  v4_cidr_blocks = ["10.10.1.0/24"]
  labels         = local.common_labels
}

# ============================================
# Private subnets (for worker nodes)
# ============================================
resource "yandex_vpc_subnet" "private" {
  count          = length(var.worker_zones)
  name           = "${local.name_prefix}-private-${count.index + 1}"
  zone           = var.worker_zones[count.index]
  network_id     = yandex_vpc_network.k3s.id
  v4_cidr_blocks = ["10.10.${10 + count.index}.0/24"]
  labels         = local.common_labels
}

# ============================================
# NAT gateway (for internet access from private subnets)
# ============================================
resource "yandex_vpc_gateway" "nat" {
  name = "${local.name_prefix}-nat"
  shared_egress_gateway {}
}

resource "yandex_vpc_route_table" "nat" {
  name       = "${local.name_prefix}-nat-route"
  network_id = yandex_vpc_network.k3s.id

  static_route {
    destination_prefix = "0.0.0.0/0"
    gateway_id         = yandex_vpc_gateway.nat.id
  }
}

# ============================================
# Security Group
# ============================================
resource "yandex_vpc_security_group" "k3s" {
  name       = "${local.name_prefix}-sg"
  network_id = yandex_vpc_network.k3s.id
  labels     = local.common_labels

  # --- Ingress ---

  # SSH
  ingress {
    protocol       = "TCP"
    description    = "SSH access"
    port           = 22
    v4_cidr_blocks = var.allowed_ssh_cidr
  }

  # k3s API server
  ingress {
    protocol       = "TCP"
    description    = "k3s API server"
    port           = 6443
    v4_cidr_blocks = ["10.10.0.0/16"]
  }

  # k3s VXLAN
  ingress {
    protocol       = "UDP"
    description    = "k3s VXLAN"
    port           = 8472
    v4_cidr_blocks = ["10.10.0.0/16"]
  }

  # kubelet
  ingress {
    protocol       = "TCP"
    description    = "kubelet API"
    port           = 10250
    v4_cidr_blocks = ["10.10.0.0/16"]
  }

  # HTTP
  ingress {
    protocol       = "TCP"
    description    = "HTTP"
    port           = 80
    v4_cidr_blocks = ["0.0.0.0/0"]
  }

  # HTTPS
  ingress {
    protocol       = "TCP"
    description    = "HTTPS"
    port           = 443
    v4_cidr_blocks = ["0.0.0.0/0"]
  }

  # Grafana (optional)
  ingress {
    protocol       = "TCP"
    description    = "Grafana"
    port           = 3000
    v4_cidr_blocks = ["0.0.0.0/0"]
  }

  # --- Egress ---
  egress {
    protocol       = "ANY"
    description    = "Allow all outbound"
    v4_cidr_blocks = ["0.0.0.0/0"]
  }
}