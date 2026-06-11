#!/usr/bin/env bash
# deploy.sh — Build, push to AWS ECR, and trigger an ECS rolling deploy.
#
# Prerequisites:
#   - AWS CLI configured (aws configure)
#   - Docker running
#   - ECR repository already created
#   - ECS cluster + service already created
#
# Usage:
#   AWS_REGION=us-east-1 ECR_REPO=task-flow ECS_CLUSTER=task-flow \
#     ECS_SERVICE=task-flow-service ./deploy.sh
#
# Environment variables (all have defaults or are required):
#   AWS_REGION    — AWS region (default: us-east-1)
#   ECR_REPO      — ECR repository name (default: task-flow)
#   IMAGE_TAG     — Docker image tag (default: git short SHA)
#   ECS_CLUSTER   — ECS cluster name (required for ECS deploy)
#   ECS_SERVICE   — ECS service name (required for ECS deploy)

set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
ECR_REPO="${ECR_REPO:-task-flow}"
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD)}"
ECS_CLUSTER="${ECS_CLUSTER:-}"
ECS_SERVICE="${ECS_SERVICE:-}"

echo "▶ region:    $AWS_REGION"
echo "▶ repo:      $ECR_REPO"
echo "▶ tag:       $IMAGE_TAG"

# ── 1. Run tests before building ──────────────────────────────────────
echo ""
echo "── Running tests ──"
python -m pytest --tb=short -q
echo "✓ All tests passed"

# ── 2. Build Docker image ─────────────────────────────────────────────
echo ""
echo "── Building image ──"
docker build -t "${ECR_REPO}:${IMAGE_TAG}" -t "${ECR_REPO}:latest" .
echo "✓ Build complete"

# ── 3. Authenticate with ECR ──────────────────────────────────────────
echo ""
echo "── Authenticating with ECR ──"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}"

aws ecr get-login-password --region "${AWS_REGION}" | \
  docker login --username AWS --password-stdin "${ECR_URI}"
echo "✓ Authenticated"

# ── 4. Tag and push ────────────────────────────────────────────────────
echo ""
echo "── Pushing image ──"
docker tag "${ECR_REPO}:${IMAGE_TAG}" "${ECR_URI}:${IMAGE_TAG}"
docker tag "${ECR_REPO}:latest"       "${ECR_URI}:latest"
docker push "${ECR_URI}:${IMAGE_TAG}"
docker push "${ECR_URI}:latest"
echo "✓ Pushed ${ECR_URI}:${IMAGE_TAG}"

# ── 5. Trigger ECS rolling deploy (optional) ──────────────────────────
if [[ -n "$ECS_CLUSTER" && -n "$ECS_SERVICE" ]]; then
  echo ""
  echo "── Deploying to ECS ──"
  aws ecs update-service \
    --region "${AWS_REGION}" \
    --cluster "${ECS_CLUSTER}" \
    --service "${ECS_SERVICE}" \
    --force-new-deployment \
    --output table

  echo ""
  echo "── Waiting for service stability ──"
  aws ecs wait services-stable \
    --region "${AWS_REGION}" \
    --cluster "${ECS_CLUSTER}" \
    --services "${ECS_SERVICE}"
  echo "✓ ECS service is stable"
else
  echo ""
  echo "ℹ  ECS_CLUSTER / ECS_SERVICE not set — skipping ECS deploy."
  echo "   To deploy: update your ECS task definition to use ${ECR_URI}:${IMAGE_TAG}"
fi

echo ""
echo "✓ Done — image: ${ECR_URI}:${IMAGE_TAG}"
