# ===============================
#  Configuration de Terraform
# ===============================
terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.116.0"
    }
  }
  required_version = ">= 1.0"
}

# ===============================
# Provider Azure
# ===============================
provider "azurerm" {
  features {}
  skip_provider_registration = true
}

# ===============================
#  Resource Group
# ===============================
resource "azurerm_resource_group" "aks_rg" {
  name     = "aks-resource-group"
  location = "italynorth"
}

# ===============================
# 4️⃣ Cluster AKS
# ===============================
resource "azurerm_kubernetes_cluster" "aks" {
  name                = "aks-cluster"
  location            = azurerm_resource_group.aks_rg.location
  resource_group_name = azurerm_resource_group.aks_rg.name
  dns_prefix          = "aksdemo"

  # ✅ Valid Kubernetes version (remove or let Azure choose default)
  
  default_node_pool {
    name       = "nodepool1"
    node_count = 1
    vm_size    = "Standard_B2s"
  }

  identity {
    type = "SystemAssigned"
  }

  tags = {
    Environment = "Development"
    Project     = "AKS-Demo"
  }
}