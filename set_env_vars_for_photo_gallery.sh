export PROJECT_ID="photo-gallery-510510"
export GITHUB_REPO="hoimantang15/photo-gallery" 
export SA_NAME="github-actions-sa"

# Automatically fetches your numeric project ID 
export PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")  
gcloud config set project $PROJECT_ID 