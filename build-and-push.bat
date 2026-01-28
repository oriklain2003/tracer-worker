@echo off
REM Build and Push Docker Image to AWS ECR
REM 
REM Required Environment Variables:
REM - AWS_ACCOUNT_ID: Your AWS account ID (default: 211578345986)
REM - AWS_REGION: AWS region (default: us-east-1)
REM - IMAGE_NAME: Docker image name (default: onyx-cortex-runner)
REM - IMAGE_TAG: Docker image tag (default: latest)
REM
REM Optional:
REM - PG_HOST: PostgreSQL host
REM - PG_DATABASE: PostgreSQL database name
REM - PG_USER: PostgreSQL username
REM - PG_PASSWORD: PostgreSQL password

setlocal enabledelayedexpansion

REM Set default values if environment variables are not set
if "%AWS_ACCOUNT_ID%"=="" set AWS_ACCOUNT_ID=211578345986
if "%AWS_REGION%"=="" set AWS_REGION=us-east-1
if "%IMAGE_NAME%"=="" set IMAGE_NAME=onyx-cortex-worker
if "%IMAGE_TAG%"=="" set IMAGE_TAG=latest

REM Construct ECR repository URL
set ECR_REPO=%AWS_ACCOUNT_ID%.dkr.ecr.%AWS_REGION%.amazonaws.com/%IMAGE_NAME%

echo ====================================
echo Building Docker Image
echo ====================================
echo Image: %IMAGE_NAME%:%IMAGE_TAG%
echo ECR Repository: %ECR_REPO%:%IMAGE_TAG%
echo ====================================

REM Step 1: Build Docker image
echo.
echo [1/4] Building Docker image...
docker build -t %IMAGE_NAME%:%IMAGE_TAG% .
if errorlevel 1 (
    echo ERROR: Docker build failed
    exit /b 1
)
echo ✓ Build successful

REM Step 2: Tag image for ECR
echo.
echo [2/4] Tagging image for ECR...
docker tag %IMAGE_NAME%:%IMAGE_TAG% %ECR_REPO%:%IMAGE_TAG%
if errorlevel 1 (
    echo ERROR: Docker tag failed
    exit /b 1
)
echo ✓ Tag successful

REM Step 3: Login to ECR
echo.
echo [3/4] Logging into AWS ECR...
aws ecr get-login-password --region %AWS_REGION% | docker login --username AWS --password-stdin %AWS_ACCOUNT_ID%.dkr.ecr.%AWS_REGION%.amazonaws.com
if errorlevel 1 (
    echo ERROR: ECR login failed. Make sure AWS CLI is configured correctly.
    exit /b 1
)
echo ✓ ECR login successful

REM Step 4: Push image to ECR
echo.
echo [4/4] Pushing image to ECR...
docker push %ECR_REPO%:%IMAGE_TAG%
if errorlevel 1 (
    echo ERROR: Docker push failed
    exit /b 1
)
echo ✓ Push successful

echo.
echo ====================================
echo DEPLOYMENT SUCCESSFUL
echo ====================================
echo Image: %ECR_REPO%:%IMAGE_TAG%
echo.
echo To run locally with environment variables:
echo docker run -e PG_HOST=your-host -e PG_DATABASE=your-db -e PG_USER=your-user -e PG_PASSWORD=your-password %IMAGE_NAME%:%IMAGE_TAG%
echo ====================================

endlocal
