# ============================================
# Cluster outputs
# ============================================
output "master_public_ip" {
  description = "Public IP of k3s master"
  value       = yandex_compute_instance.k3s_master.network_interface[0].nat_ip_address
}

output "master_private_ip" {
  description = "Private IP of k3s master"
  value       = yandex_compute_instance.k3s_master.network_interface[0].ip_address
}

output "workers_private_ips" {
  description = "Private IPs of k3s workers"
  value       = yandex_compute_instance.k3s_worker[*].network_interface[0].ip_address
}

# ============================================
# Database outputs
# ============================================
output "postgres_host" {
  description = "PostgreSQL cluster FQDN"
  value       = yandex_mdb_postgresql_cluster.opc_monitor.host[0].fqdn
  sensitive   = true
}

# ============================================
# Network outputs
# ============================================
output "vpc_id" {
  description = "VPC network ID"
  value       = yandex_vpc_network.k3s.id
}

output "security_group_id" {
  description = "Security group ID"
  value       = yandex_vpc_security_group.k3s.id
}

# ============================================
# Connection info
# ============================================
output "ssh_command" {
  description = "SSH command to connect to master"
  value       = "ssh ubuntu@${yandex_compute_instance.k3s_master.network_interface[0].nat_ip_address}"
}