variable "location" {
  type        = string
  default     = "Poland Central"
  description = "The Azure region to deploy resources"
}

variable "resource_group" {
  type = object({
    name   = string
    create = bool
  })
  default = {
    name   = "mlops"
    create = false
  }
  description = "Resource group configuration"
}

variable "kubernetes_cluster" {
  type = object({
    name       = string
    vm_size    = string
    node_count = number
  })
  default = {
    name = "mlops-cluster"
    vm_size = "Standard_D4ds_v5"
    node_count = 1
  }
  description = "Kubernetes cluster configuration"
}