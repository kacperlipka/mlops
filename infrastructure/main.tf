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
  address_space       = ["10.0.0.0/16"]
  dns_servers         = ["10.0.0.4", "10.0.0.5"]
}

resource "azurerm_subnet" "appgw" {
  name                 = "appgw-subnet"
  resource_group_name  = local.resource_group_name
  virtual_network_name = azurerm_virtual_network.this.name
  address_prefixes     = ["10.0.1.0/24"]
}

resource "azurerm_subnet" "kubernetes_pods" {
  name                 = "kubernetes-pods-subnet"
  resource_group_name  = local.resource_group_name
  virtual_network_name = azurerm_virtual_network.this.name
  address_prefixes     = ["10.0.2.0/24"]
}


resource "azurerm_subnet" "kubernetes_nodes" {
  name                 = "kubernetes-nodes-subnet"
  resource_group_name  = local.resource_group_name
  virtual_network_name = azurerm_virtual_network.this.name
  address_prefixes     = ["10.0.2.0/24"]
}

resource "azurerm_dns_zone" "this" {
  name                = "kacperlipka.mlops.com"
  resource_group_name = local.resource_group_name
}

resource "azurerm_dns_a_record" "this" {
  name                = "appgw"
  zone_name           = azurerm_dns_zone.this.name
  resource_group_name = local.resource_group_name
  ttl                 = 300
  records             = [azurerm_public_ip.this.ip_address]
}

resource "azurerm_public_ip" "this" {
  name                = "appgw-pip"
  resource_group_name = local.resource_group_name
  location            = var.location
  allocation_method   = "Dynamic"
}


resource "azurerm_application_gateway" "this" {
  name                = "mlops-gateway"
  resource_group_name = local.resource_group_name
  location            = var.location
  sku {
    name     = "Standard_v2"
    tier     = "Standard_v2"
    capacity = 2
  }

  gateway_ip_configuration {
    name      = "mlops-ip-configuration"
    subnet_id = azurerm_subnet.appgw.id
  }

  frontend_port {
    name = "http"
    port = 80
  }

  frontend_ip_configuration {
    name                 = "frontend-ip"
    public_ip_address_id = azurerm_public_ip.this.ip_address
  }

  backend_address_pool {
    name = "kubernetes"
  }

  backend_http_settings {
    name                  = "http-setting"
    cookie_based_affinity = "Disabled"
    path                  = "/"
    port                  = 80
    protocol              = "Http"
    request_timeout       = 60
  }

  http_listener {
    name                           = "http-listener"
    frontend_ip_configuration_name = "frontend-ip"
    frontend_port_name             = "http"
    protocol                       = "Http"
  }

  request_routing_rule {
    name                       = "rule"
    priority                   = 9
    rule_type                  = "Basic"
    http_listener_name         = "http-listener"
    backend_address_pool_name  = "kubernetes"
    backend_http_settings_name = "http-setting"
  }
}

resource "azurerm_kubernetes_cluster" "this" {
  name                = var.kubernetes_cluster.name
  location            = "Poland Central"
  resource_group_name = local.resource_group_name

  default_node_pool {
    name           = "default"
    node_count     = var.kubernetes_cluster.node_count
    vm_size        = var.kubernetes_cluster.vm_size
    pod_subnet_id  = azurerm_subnet.kubernetes_pods.id
    vnet_subnet_id = azurerm_subnet.kubernetes_nodes.id
  }

  dns_prefix = "mlops"
  identity {
    type = "SystemAssigned"
  }
}
