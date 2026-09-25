# ============================================
# k3s Master node
# ============================================
resource "yandex_compute_instance" "k3s_master" {
  name        = "${local.name_prefix}-master"
  hostname    = "k3s-master"
  platform_id = "standard-v3"
  zone        = var.master_zone
  labels      = local.common_labels

  resources {
    cores  = var.master_cores
    memory = var.master_memory
  }

  boot_disk {
    initialize_params {
      image_id = "fd8mfc6onomehi2m9o5d" # Ubuntu 22.04 LTS
      size     = 30
      type     = "network-ssd"
    }
  }

  network_interface {
    subnet_id          = yandex_vpc_subnet.public.id
    nat                = true
    security_group_ids = [yandex_vpc_security_group.k3s.id]
  }

  metadata = {
    ssh-keys = "ubuntu:${var.ssh_public_key}"
    user-data = templatefile("${path.module}/templates/k3s-master-cloud-init.yaml", {
      k3s_token = var.k3s_token
    })
  }
}

# ============================================
# k3s Worker nodes
# ============================================
resource "yandex_compute_instance" "k3s_worker" {
  count       = length(var.worker_zones)
  name        = "${local.name_prefix}-worker-${count.index + 1}"
  hostname    = "k3s-worker-${count.index + 1}"
  platform_id = "standard-v3"
  zone        = var.worker_zones[count.index]
  labels      = local.common_labels

  resources {
    cores  = var.worker_cores
    memory = var.worker_memory
  }

  boot_disk {
    initialize_params {
      image_id = "fd8mfc6onomehi2m9o5d"
      size     = 50
      type     = "network-ssd"
    }
  }

  network_interface {
    subnet_id          = yandex_vpc_subnet.private[count.index].id
    nat                = false
    security_group_ids = [yandex_vpc_security_group.k3s.id]
  }

  metadata = {
    ssh-keys = "ubuntu:${var.ssh_public_key}"
    user-data = templatefile("${path.module}/templates/k3s-worker-cloud-init.yaml", {
      k3s_token  = var.k3s_token
      k3s_master = yandex_compute_instance.k3s_master.network_interface[0].ip_address
    })
  }

  depends_on = [yandex_compute_instance.k3s_master]
}