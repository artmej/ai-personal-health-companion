// AI Personal Health Companion - Private Network Infrastructure
// Secure deployment with Managed Identity and private networking only
// No internet access - internal communication via VNet and Private Endpoints

targetScope = 'resourceGroup'

@description('Environment name for resource naming')
param environmentName string = 'phealth'

@description('Azure location for all resources')
param location string = resourceGroup().location

@description('Principal ID for RBAC assignments')
param principalId string = ''

// Naming convention
var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))
var prefix = '${environmentName}-${resourceToken}'

var tags = {
  'azd-env-name': environmentName
  'project': 'ai-health-companion'
  'network-type': 'private-only'
}

// ================================
// NETWORKING - Private VNet
// ================================

resource vnet 'Microsoft.Network/virtualNetworks@2023-05-01' = {
  name: 'vnet-${prefix}'
  location: location
  tags: tags
  properties: {
    addressSpace: {
      addressPrefixes: [
        '10.0.0.0/16'
      ]
    }
    subnets: [
      {
        name: 'subnet-container-apps'
        properties: {
          addressPrefix: '10.0.1.0/24'
          delegations: [
            {
              name: 'Microsoft.App.environments'
              properties: {
                serviceName: 'Microsoft.App/environments'
              }
            }
          ]
        }
      }
      {
        name: 'subnet-private-endpoints'
        properties: {
          addressPrefix: '10.0.2.0/24'
          privateEndpointNetworkPolicies: 'Disabled'
          privateLinkServiceNetworkPolicies: 'Disabled'
        }
      }
    ]
  }
}

// Private DNS Zones for Azure services
resource privateDnsZoneStorage 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: 'privatelink.blob.core.windows.net'
  location: 'global'
  tags: tags
}

resource privateDnsZoneCosmosDb 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: 'privatelink.documents.azure.com'
  location: 'global'
  tags: tags
}

resource privateDnsZoneKeyVault 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: 'privatelink.vaultcore.azure.net'
  location: 'global'
  tags: tags
}

resource privateDnsZoneCognitiveServices 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: 'privatelink.cognitiveservices.azure.com'
  location: 'global'
  tags: tags
}

// Link private DNS zones to VNet
resource dnsLinkStorage 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: privateDnsZoneStorage
  name: 'link-storage'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: vnet.id
    }
  }
}

resource dnsLinkCosmosDb 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: privateDnsZoneCosmosDb
  name: 'link-cosmosdb'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: vnet.id
    }
  }
}

resource dnsLinkKeyVault 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: privateDnsZoneKeyVault
  name: 'link-keyvault'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: vnet.id
    }
  }
}

resource dnsLinkCognitiveServices 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: privateDnsZoneCognitiveServices
  name: 'link-cognitive'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: vnet.id
    }
  }
}

// ================================
// MANAGED IDENTITY
// ================================

resource managedIdentity 'Microsoft.ManagedIdentity/userAssignedManagedIdentities@2023-01-31' = {
  name: 'id-${prefix}'
  location: location
  tags: tags
}

// ================================
// STORAGE ACCOUNT - Private
// ================================

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: 'st${resourceToken}'
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    publicNetworkAccess: 'Disabled' // No internet access
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false // Only Managed Identity access
    networkAcls: {
      defaultAction: 'Deny'
      bypass: 'None'
    }
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

// Storage containers
resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: storageAccount
  name: 'default'
}

resource foodImagesContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobService
  name: 'food-images'
  properties: {
    publicAccess: 'None'
  }
}

resource medicalDocumentsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobService
  name: 'medical-documents'
  properties: {
    publicAccess: 'None'
  }
}

// Private endpoint for Storage
resource storagePrivateEndpoint 'Microsoft.Network/privateEndpoints@2023-05-01' = {
  name: 'pe-storage-${prefix}'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: '${vnet.id}/subnets/subnet-private-endpoints'
    }
    privateLinkServiceConnections: [
      {
        name: 'storage-connection'
        properties: {
          privateLinkServiceId: storageAccount.id
          groupIds: ['blob']
        }
      }
    ]
  }
}

resource storagePrivateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-05-01' = {
  parent: storagePrivateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'config'
        properties: {
          privateDnsZoneId: privateDnsZoneStorage.id
        }
      }
    ]
  }
}

// ================================
// COSMOS DB - Private
// ================================

resource cosmosDbAccount 'Microsoft.DocumentDB/databaseAccounts@2023-04-15' = {
  name: 'cosmos-${prefix}'
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    enableFreeTier: false
    publicNetworkAccess: 'Disabled' // No internet access
    networkAclBypass: 'None'
    disableKeyBasedMetadataWriteAccess: true // Only Managed Identity access
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    databaseAccountOfferType: 'Standard'
  }
}

resource cosmosDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-04-15' = {
  parent: cosmosDbAccount
  name: 'HealthCompanionDB'
  properties: {
    resource: {
      id: 'HealthCompanionDB'
    }
    options: {
      throughput: 400
    }
  }
}

// Cosmos DB containers
resource usersContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  parent: cosmosDatabase
  name: 'users'
  properties: {
    resource: {
      id: 'users'
      partitionKey: {
        paths: ['/userId']
        kind: 'Hash'
      }
    }
  }
}

resource foodAnalysisContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  parent: cosmosDatabase
  name: 'food-analysis'
  properties: {
    resource: {
      id: 'food-analysis'
      partitionKey: {
        paths: ['/userId']
        kind: 'Hash'
      }
    }
  }
}

resource medicalDocumentsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  parent: cosmosDatabase
  name: 'medical-documents'
  properties: {
    resource: {
      id: 'medical-documents'
      partitionKey: {
        paths: ['/userId']
        kind: 'Hash'
      }
    }
  }
}

// Private endpoint for Cosmos DB
resource cosmosPrivateEndpoint 'Microsoft.Network/privateEndpoints@2023-05-01' = {
  name: 'pe-cosmos-${prefix}'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: '${vnet.id}/subnets/subnet-private-endpoints'
    }
    privateLinkServiceConnections: [
      {
        name: 'cosmos-connection'
        properties: {
          privateLinkServiceId: cosmosDbAccount.id
          groupIds: ['Sql']
        }
      }
    ]
  }
}

resource cosmosPrivateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-05-01' = {
  parent: cosmosPrivateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'config'
        properties: {
          privateDnsZoneId: privateDnsZoneCosmosDb.id
        }
      }
    ]
  }
}

// ================================
// KEY VAULT - Private
// ================================

resource keyVault 'Microsoft.KeyVault/vaults@2023-02-01' = {
  name: 'kv-${resourceToken}'
  location: location
  tags: tags
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    publicNetworkAccess: 'Disabled' // No internet access
    enabledForDeployment: false
    enabledForTemplateDeployment: false
    enabledForDiskEncryption: false
    enableRbacAuthorization: true // Use RBAC instead of access policies
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    enablePurgeProtection: true
  }
}

// Private endpoint for Key Vault
resource keyVaultPrivateEndpoint 'Microsoft.Network/privateEndpoints@2023-05-01' = {
  name: 'pe-keyvault-${prefix}'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: '${vnet.id}/subnets/subnet-private-endpoints'
    }
    privateLinkServiceConnections: [
      {
        name: 'keyvault-connection'
        properties: {
          privateLinkServiceId: keyVault.id
          groupIds: ['vault']
        }
      }
    ]
  }
}

resource keyVaultPrivateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-05-01' = {
  parent: keyVaultPrivateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'config'
        properties: {
          privateDnsZoneId: privateDnsZoneKeyVault.id
        }
      }
    ]
  }
}

// ================================
// COGNITIVE SERVICES - Private
// ================================

resource aiServices 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: 'cog-${prefix}'
  location: location
  tags: tags
  sku: {
    name: 'S0'
  }
  kind: 'CognitiveServices'
  properties: {
    publicNetworkAccess: 'Disabled' // No internet access
    networkAcls: {
      defaultAction: 'Deny'
      bypass: 'None'
    }
    disableLocalAuth: true // Only Managed Identity access
  }
}

// Private endpoint for Cognitive Services
resource cognitiveServicesPrivateEndpoint 'Microsoft.Network/privateEndpoints@2023-05-01' = {
  name: 'pe-cognitive-${prefix}'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: '${vnet.id}/subnets/subnet-private-endpoints'
    }
    privateLinkServiceConnections: [
      {
        name: 'cognitive-connection'
        properties: {
          privateLinkServiceId: aiServices.id
          groupIds: ['account']
        }
      }
    ]
  }
}

resource cognitiveServicesPrivateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-05-01' = {
  parent: cognitiveServicesPrivateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'config'
        properties: {
          privateDnsZoneId: privateDnsZoneCognitiveServices.id
        }
      }
    ]
  }
}

// ================================
// APPLICATION INSIGHTS
// ================================

resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: 'log-${prefix}'
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
    publicNetworkAccessForIngestion: 'Disabled'
    publicNetworkAccessForQuery: 'Disabled'
  }
}

resource applicationInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-${prefix}'
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalyticsWorkspace.id
    publicNetworkAccessForIngestion: 'Disabled'
    publicNetworkAccessForQuery: 'Disabled'
  }
}

// ================================
// CONTAINER APPS ENVIRONMENT
// ================================

resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2023-05-02-preview' = {
  name: 'cae-${prefix}'
  location: location
  tags: tags
  properties: {
    vnetConfiguration: {
      infrastructureSubnetId: '${vnet.id}/subnets/subnet-container-apps'
      internal: true // Internal load balancer only
    }
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsWorkspace.properties.customerId
        sharedKey: logAnalyticsWorkspace.listKeys().primarySharedKey
      }
    }
  }
}

// ================================
// RBAC ASSIGNMENTS FOR MANAGED IDENTITY
// ================================

// Storage Blob Data Contributor role
resource storageBlobDataContributorRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, managedIdentity.id, 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// Cosmos DB Built-in Data Contributor role
resource cosmosDbDataContributorRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(cosmosDbAccount.id, managedIdentity.id, '00000000-0000-0000-0000-000000000002')
  scope: cosmosDbAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '00000000-0000-0000-0000-000000000002')
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// Key Vault Secrets Officer role
resource keyVaultSecretsOfficerRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, managedIdentity.id, 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7')
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7')
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// Cognitive Services User role
resource cognitiveServicesUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aiServices.id, managedIdentity.id, 'a97b65f3-24c7-4388-baec-2e87135dc908')
  scope: aiServices
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908')
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// Principal access (if provided)
resource keyVaultSecretsOfficerRolePrincipal 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(principalId)) {
  name: guid(keyVault.id, principalId, 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7')
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7')
    principalId: principalId
    principalType: 'User'
  }
}

// ================================
// CONTAINER APPS
// ================================

// API Container App
resource apiContainerApp 'Microsoft.App/containerApps@2023-05-02-preview' = {
  name: 'ca-api-${prefix}'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      ingress: {
        external: false // Internal only
        targetPort: 8000
        transport: 'http'
      }
      secrets: []
    }
    template: {
      containers: [
        {
          image: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
          name: 'api'
          env: [
            {
              name: 'AZURE_CLIENT_ID'
              value: managedIdentity.properties.clientId
            }
            {
              name: 'COSMOS_DB_ENDPOINT'
              value: cosmosDbAccount.properties.documentEndpoint
            }
            {
              name: 'STORAGE_ACCOUNT_ENDPOINT'
              value: storageAccount.properties.primaryEndpoints.blob
            }
            {
              name: 'COGNITIVE_SERVICES_ENDPOINT'
              value: aiServices.properties.endpoint
            }
            {
              name: 'KEY_VAULT_URL'
              value: keyVault.properties.vaultUri
            }
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              value: applicationInsights.properties.ConnectionString
            }
          ]
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 3
      }
    }
  }
}

// Web Container App
resource webContainerApp 'Microsoft.App/containerApps@2023-05-02-preview' = {
  name: 'ca-web-${prefix}'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      ingress: {
        external: false // Internal only
        targetPort: 8501
        transport: 'http'
      }
      secrets: []
    }
    template: {
      containers: [
        {
          image: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
          name: 'web'
          env: [
            {
              name: 'AZURE_CLIENT_ID'
              value: managedIdentity.properties.clientId
            }
            {
              name: 'API_BASE_URL'
              value: 'http://${apiContainerApp.properties.latestRevisionFqdn}'
            }
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              value: applicationInsights.properties.ConnectionString
            }
          ]
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 3
      }
    }
  }
}

// Background Processor Container App
resource processorContainerApp 'Microsoft.App/containerApps@2023-05-02-preview' = {
  name: 'ca-processor-${prefix}'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      secrets: []
    }
    template: {
      containers: [
        {
          image: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
          name: 'processor'
          env: [
            {
              name: 'AZURE_CLIENT_ID'
              value: managedIdentity.properties.clientId
            }
            {
              name: 'COSMOS_DB_ENDPOINT'
              value: cosmosDbAccount.properties.documentEndpoint
            }
            {
              name: 'STORAGE_ACCOUNT_ENDPOINT'
              value: storageAccount.properties.primaryEndpoints.blob
            }
            {
              name: 'COGNITIVE_SERVICES_ENDPOINT'
              value: aiServices.properties.endpoint
            }
            {
              name: 'KEY_VAULT_URL'
              value: keyVault.properties.vaultUri
            }
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              value: applicationInsights.properties.ConnectionString
            }
          ]
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
}

// ================================
// OUTPUTS
// ================================

output RESOURCE_GROUP_NAME string = resourceGroup().name
output MANAGED_IDENTITY_CLIENT_ID string = managedIdentity.properties.clientId
output MANAGED_IDENTITY_PRINCIPAL_ID string = managedIdentity.properties.principalId
output VNET_ID string = vnet.id

output COSMOS_DB_ENDPOINT string = cosmosDbAccount.properties.documentEndpoint
output STORAGE_ACCOUNT_ENDPOINT string = storageAccount.properties.primaryEndpoints.blob
output COGNITIVE_SERVICES_ENDPOINT string = aiServices.properties.endpoint
output KEY_VAULT_URL string = keyVault.properties.vaultUri

output API_CONTAINER_APP_NAME string = apiContainerApp.name
output WEB_CONTAINER_APP_NAME string = webContainerApp.name
output PROCESSOR_CONTAINER_APP_NAME string = processorContainerApp.name

output APPLICATIONINSIGHTS_CONNECTION_STRING string = applicationInsights.properties.ConnectionString
