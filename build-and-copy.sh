#!/bin/bash
# Build the frontend and copy to backend static directory

echo "Building frontend..."
cd "$(dirname "$0")/app/frontend"
npm run build --mode=development

echo "Copying built files to backend static directory..."
cp -r dist/* ../backend/static/

echo "Done! Now restart your backend server if needed."
