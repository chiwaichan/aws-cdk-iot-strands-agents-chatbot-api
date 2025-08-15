#!/bin/bash

set -e

echo "🚀 Starting deployment process..."

# Install Node.js dependencies
echo "📦 Installing Node.js dependencies..."
npm install

# Create Python virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "🐍 Creating Python virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

# Install Python dependencies for local development
echo "📚 Installing Python dependencies for local development..."
pip3 install -r requirements.txt

# Install Python dependencies for Lambda with correct architecture
echo "🏗️ Installing Python dependencies for Lambda (ARM64)..."
pip3 install -r requirements.txt --python-version 3.12 --platform manylinux2014_aarch64 --target ./packaging/_dependencies --only-binary=:all:

# Package the Lambda
echo "📦 Packaging Lambda function..."
python3 ./bin/package_for_lambda.py

# Bootstrap AWS environment (only if not already done)
echo "🏗️ Bootstrapping AWS environment..."
npx cdk bootstrap

# Deploy the Lambda
echo "🚀 Deploying to AWS..."
npx cdk deploy --require-approval never

echo "✅ Deployment completed successfully!"
