terraform {
  backend "azurerm" {
    resource_group_name  = "mlops"
    storage_account_name = "infrastructure319068"
    container_name       = "tfstate"
    key                  = "terraform.tfstate"
    use_oidc             = true
  }
}