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
    max_count  = number
    min_count  = number
  })
  default = {
    name       = "mlops-cluster"
    vm_size    = "Standard_D4ds_v5"
    node_count = 2
    max_count  = 3
    min_count  = 1
  }
  description = "Kubernetes cluster configuration"
}

variable "storage_account" {
  type = object({
    name                     = string
    account_tier             = string
    account_replication_type = string
    is_hns_enabled           = bool
    nfs3_enabled             = bool
  })
  default = {
    name                     = "mlopskubeflowstorageaccount"
    account_tier             = "Standard"
    account_replication_type = "ZRS"
    is_hns_enabled           = true
    nfs3_enabled             = true
  }
  description = "Storage account configuration"
}