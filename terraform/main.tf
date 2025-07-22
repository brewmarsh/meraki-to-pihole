provider "docker" {}

resource "docker_image" "meraki_pihole_sync" {
  name         = "meraki_pihole_sync"
  keep_locally = true
  build {
    context = ".."
    dockerfile = "../Dockerfile"
  }
}

resource "docker_container" "meraki_pihole_sync_container" {
  image = docker_image.meraki_pihole_sync.latest
  name  = "meraki_pihole_sync"
  ports {
    internal = 8000
    external = 8000
  }
  env = [
    "MERAKI_API_KEY=${var.meraki_api_key}",
    "MERAKI_ORG_ID=${var.meraki_org_id}",
    "PIHOLE_API_URL=${var.pihole_api_url}",
    "PIHOLE_API_KEY=${var.pihole_api_key}",
    "HOSTNAME_SUFFIX=${var.hostname_suffix}",
    "NETWORK_IDS=${var.network_ids}",
    "CLIENT_TIMESPAN=${var.client_timespan}"
  ]
}

variable "meraki_api_key" {
  description = "Meraki API Key"
  type        = string
  sensitive   = true
}

variable "meraki_org_id" {
  description = "Meraki Organization ID"
  type        = string
}

variable "pihole_api_url" {
  description = "Pi-hole API URL"
  type        = string
}

variable "pihole_api_key" {
  description = "Pi-hole API Key"
  type        = string
  sensitive   = true
}

variable "hostname_suffix" {
  description = "Hostname Suffix"
  type        = string
  default     = "meraki.local"
}

variable "network_ids" {
  description = "Meraki Network IDs"
  type        = string
  default     = ""
}

variable "client_timespan" {
  description = "Client Timespan"
  type        = string
  default     = "86400"
}
