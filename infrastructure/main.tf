resource "azurerm_resource_group" "this" {
  count = var.resource_group.create ? 1 : 0

  name     = var.resource_group.name
  location = var.location
}

data "azurerm_resource_group" "this" {
  count = var.resource_group.create ? 0 : 1

  name = var.resource_group.name
}

locals {
  resource_group_name = var.resource_group.create ? azurerm_resource_group.this[0].name : data.resource_group.this[0].name
}

resource "azurerm_kubernetes_cluster" "example" {
  name                = var.kubernetes_cluster.name
  location            = var.location
  resource_group_name = local.resource_group_name

  default_node_pool {
    name       = "default"
    node_count = var.kubernetes_cluster.node_count
    vm_size    = var.kubernetes_cluster.vm_size
  }
}