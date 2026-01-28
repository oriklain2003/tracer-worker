# Docker Deployment Guide

## Overview

This directory contains Docker deployment files for the Onyx Cortex Flight Monitor application.

## Files

- `Dockerfile` - Multi-stage Docker image for the monitor application
- `docker-compose.yml` - Docker Compose configuration for local testing
- `build-and-push.bat` - Automated build and push script for AWS ECR
- `.env.example` - Example environment variables file

## Quick Start

### 1. Local Development with Docker Compose

```bash
# Copy and configure environment variables
cp .env.example .env
# Edit .env with your actual credentials

# Build and run
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### 2. Build and Push to AWS ECR

#### Prerequisites

- AWS CLI installed and configured
- Docker installed
- Proper AWS credentials with ECR access

#### Using the Batch Script (Windows)

```cmd
# Set environment variables (or add to system environment)
set PG_PASSWORD=your-actual-password

# Run the build and push script
build-and-push.bat
```

The script will:
1. Build the Docker image
2. Tag it for ECR
3. Login to AWS ECR
4. Push the image to ECR

#### Manual Commands

```cmd
# Build
docker build -t onyx-cortex-runner .

# Tag
docker tag onyx-cortex-runner:latest 211578345986.dkr.ecr.us-east-1.amazonaws.com/onyx-cortex-runner:latest

# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 211578345986.dkr.ecr.us-east-1.amazonaws.com

# Push
docker push 211578345986.dkr.ecr.us-east-1.amazonaws.com/onyx-cortex-runner:latest
```

## Environment Variables

### Required

- `PG_HOST` - PostgreSQL host address
- `PG_DATABASE` - PostgreSQL database name
- `PG_USER` - PostgreSQL username
- `PG_PASSWORD` - PostgreSQL password

### Optional

- `PG_PORT` - PostgreSQL port (default: 5432)
- `PG_SCHEMA` - PostgreSQL schema (default: live)

### Build Script Variables

- `AWS_ACCOUNT_ID` - AWS account ID (default: 211578345986)
- `AWS_REGION` - AWS region (default: us-east-1)
- `IMAGE_NAME` - Docker image name (default: onyx-cortex-runner)
- `IMAGE_TAG` - Docker image tag (default: latest)

## Running the Container

### Docker Run

```bash
docker run -d \
  --name flight-monitor \
  -e PG_HOST=your-host \
  -e PG_DATABASE=your-db \
  -e PG_USER=your-user \
  -e PG_PASSWORD=your-password \
  onyx-cortex-runner:latest
```

### AWS ECS Task Definition Example

```json
{
  "containerDefinitions": [
    {
      "name": "onyx-cortex-runner",
      "image": "211578345986.dkr.ecr.us-east-1.amazonaws.com/onyx-cortex-runner:latest",
      "environment": [
        {"name": "PG_HOST", "value": "your-host"},
        {"name": "PG_PORT", "value": "5432"},
        {"name": "PG_DATABASE", "value": "tracer"},
        {"name": "PG_SCHEMA", "value": "live"}
      ],
      "secrets": [
        {
          "name": "PG_USER",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:db-user"
        },
        {
          "name": "PG_PASSWORD",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:db-password"
        }
      ]
    }
  ]
}
```

## Troubleshooting

### Connection Issues

```bash
# Check if PostgreSQL is accessible
docker run --rm -it \
  -e PG_HOST=your-host \
  -e PG_USER=your-user \
  -e PG_PASSWORD=your-password \
  -e PG_DATABASE=tracer \
  onyx-cortex-runner:latest \
  python -c "import psycopg2; psycopg2.connect('postgresql://${PG_USER}:${PG_PASSWORD}@${PG_HOST}:5432/${PG_DATABASE}')"
```

### View Logs

```bash
# Docker Compose
docker-compose logs -f

# Docker Run
docker logs -f flight-monitor
```

### Debug Mode

```bash
# Run with interactive shell
docker run -it --rm \
  -e PG_HOST=your-host \
  -e PG_DATABASE=your-db \
  -e PG_USER=your-user \
  -e PG_PASSWORD=your-password \
  onyx-cortex-runner:latest \
  /bin/bash
```

## Security Notes

- **Never commit `.env` files** - They contain sensitive credentials
- Use AWS Secrets Manager or Parameter Store for production deployments
- Rotate credentials regularly
- Use IAM roles when running on AWS ECS/EKS
- Enable encryption at rest and in transit

## Health Check

The container includes a health check that verifies PostgreSQL connectivity every 30 seconds.

```bash
# Check container health
docker inspect --format='{{.State.Health.Status}}' flight-monitor
```
