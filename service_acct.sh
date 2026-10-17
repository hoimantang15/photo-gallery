#!/bin/bash  

# Define variables directly inside the script 
PROJECT_ID="photo-gallery-510510" 
SA_NAME="github-actions-sa"  

echo "Creating service account..." 
gcloud iam service-accounts create $SA_NAME \
    --display-name="GitHub Actions Deployment SA" \
    --project=$PROJECT_ID  

echo "Granting Cloud Run Admin..." 
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/run.admin"  

echo "Granting Service Account User..." 
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/iam.serviceAccountUser"  

echo "Granting Artifact Registry Writer..." 
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/artifactregistry.writer"  

echo "Done!" 