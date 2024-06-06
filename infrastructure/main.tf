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
  backend_address_pool_name      = "${azurerm_virtual_network.this.name}-beap"
  frontend_port_name             = "${azurerm_virtual_network.this.name}-feport"
  frontend_ip_configuration_name = "${azurerm_virtual_network.this.name}-feip"
  http_setting_name              = "${azurerm_virtual_network.this.name}-be-htst"
  listener_name                  = "${azurerm_virtual_network.this.name}-httplstn"
  request_routing_rule_name      = "${azurerm_virtual_network.this.name}-rqrt"
  redirect_configuration_name    = "${azurerm_virtual_network.this.name}-rdrcfg"
}

resource "azurerm_virtual_network" "this" {
  name                = "mlops-network"
  location            = var.location
  resource_group_name = local.resource_group_name
  address_space       = ["10.1.0.0/16"]
}

resource "azurerm_subnet" "appgw" {
  name                 = "appgw-subnet"
  resource_group_name  = local.resource_group_name
  virtual_network_name = azurerm_virtual_network.this.name
  address_prefixes     = ["10.1.1.0/24"]
}

resource "azurerm_subnet" "kubernetes" {
  name                 = "kubernetes-kubernetes-subnet"
  resource_group_name  = local.resource_group_name
  virtual_network_name = azurerm_virtual_network.this.name
  address_prefixes     = ["10.1.2.0/24"]
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
  allocation_method   = "Static"
}

resource "azurerm_application_gateway" "network" {
  name                = "mlops-appgw"
  resource_group_name = local.resource_group_name
  location            = azurerm_resource_group.this.location

  sku {
    name     = "Standard_v2"
    tier     = "Standard_v2"
    capacity = 2
  }

  gateway_ip_configuration {
    name      = "mlops-gateway-ip-configuration"
    subnet_id = azurerm_subnet.example.id
  }

  frontend_port {
    name = local.frontend_port_name
    port = 80
  }

  frontend_ip_configuration {
    name                 = local.frontend_ip_configuration_name
    public_ip_address_id = azurerm_public_ip.example.id
  }

  backend_address_pool {
    name = local.backend_address_pool_name
  }

  backend_http_settings {
    name                  = local.http_setting_name
    cookie_based_affinity = "Disabled"
    path                  = "/"
    port                  = 80
    protocol              = "Http"
    request_timeout       = 60
  }

  http_listener {
    name                           = local.listener_name
    frontend_ip_configuration_name = local.frontend_ip_configuration_name
    frontend_port_name             = local.frontend_port_name
    protocol                       = "Http"
  }

  request_routing_rule {
    name                       = local.request_routing_rule_name
    priority                   = 9
    rule_type                  = "Basic"
    http_listener_name         = local.listener_name
    backend_address_pool_name  = local.backend_address_pool_name
    backend_http_settings_name = local.http_setting_name
  }
}

resource "azurerm_kubernetes_cluster" "this" {
  name                = var.kubernetes_cluster.name
  location            = "Poland Central"
  resource_group_name = local.resource_group_name

  dns_prefix = "mlops"

  default_node_pool {
    name           = "default"
    node_count     = var.kubernetes_cluster.node_count
    vm_size        = var.kubernetes_cluster.vm_size
    vnet_subnet_id = azurerm_subnet.kubernetes.id
  }

  network_profile {
    network_plugin = "azure"
  }

  identity {
    type = "SystemAssigned"
  }
}
