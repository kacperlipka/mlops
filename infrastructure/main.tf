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
  resource_group_name = var.resource_group.create ? azurerm_resource_group.this[0].name : data.azurerm_resource_group.this[0].name
}

resource "azurerm_virtual_network" "this" {
  name                = "mlops-network"
  location            = var.location
  resource_group_name = local.resource_group_name
  address_space       = ["10.1.0.0/16"]
}

resource "azurerm_subnet" "kubernetes" {
  name                 = "kubernetes-subnet"
  resource_group_name  = local.resource_group_name
  virtual_network_name = azurerm_virtual_network.this.name
  address_prefixes     = ["10.1.1.0/24"]
}

resource "azurerm_kubernetes_cluster" "this" {
  name                = var.kubernetes_cluster.name
  location            = var.location
  resource_group_name = local.resource_group_name

  dns_prefix = "mlops"

  default_node_pool {
    name                = "default"
    vm_size             = var.kubernetes_cluster.vm_size
    vnet_subnet_id      = azurerm_subnet.kubernetes.id
    enable_auto_scaling = true
    node_count          = var.kubernetes_cluster.node_count
    min_count           = var.kubernetes_cluster.min_count
    max_count           = var.kubernetes_cluster.max_count
  }

  storage_profile {
    blob_driver_enabled = true
    file_driver_enabled = true
  }

  network_profile {
    network_plugin = "azure"
  }

  identity {
    type = "SystemAssigned"
  }
}

resource "azurerm_storage_account" "this" {
  name                     = var.storage_account.name
  resource_group_name      = local.resource_group_name
  location                 = var.location
  account_tier             = var.storage_account.account_tier
  account_replication_type = var.storage_account.account_replication_type
  is_hns_enabled           = var.storage_account.is_hns_enabled
  nfsv3_enabled            = var.storage_account.nfs3_enabled

  network_rules {
    default_action = "Deny"
    virtual_network_subnet_ids = [azurerm_subnet.kubernetes.id]
  }
}