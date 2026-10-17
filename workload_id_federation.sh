#!/bin/bash

PROJECT_ID="photo-gallery-510510"
SA_NAME="github-actions-sa"
GITHUB_REPO="hoimantang15/photo-gallery"
PROJECT_NUMBER="157284883074"

# 1. CREATE THE WORKLOAD IDENTITY POOL FIRST
echo "Creating Workload Identity Pool..."
gcloud iam workload-identity-pools create "github-pool" \
    --location="global" \
    --display-name="GitHub Pool" \
    --project=$PROJECT_ID

# 2. CREATE THE OIDC PROVIDER
echo "Creating OIDC Provider with strict attribute condition..."
gcloud iam workload-identity-pools providers create-oidc github-provider \
    --location="global" \
    --workload-identity-pool="github-pool" \
    --display-name="GitHub Provider" \
    --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
    --attribute-condition="assertion.repository == '$GITHUB_REPO'" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --project=$PROJECT_ID

echo "Binding GitHub repository to Service Account..."
gcloud iam service-accounts add-iam-policy-binding $SA_NAME@$PROJECT_ID.iam.gserviceaccount.com \
    --role="roles/iam.workloadIdentityUser" \
    --member="principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/attribute.repository/$GITHUB_REPO"

echo "Done! Your provider string for your GitHub Actions YAML file is:"
echo "projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/providers/github-provider"