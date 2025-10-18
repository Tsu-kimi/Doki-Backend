#!/bin/bash

# Test script for local Docker deployment
# This script builds and tests the Docker container locally

set -e  # Exit on error

echo "🐳 Doki Backend - Local Docker Test Script"
echo "=========================================="

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
IMAGE_NAME="doki-backend"
IMAGE_TAG="dev"
CONTAINER_NAME="doki-backend-test"
PORT=8080

# Step 1: Check if .env file exists
echo ""
echo "📋 Step 1: Checking for .env file..."
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  Warning: .env file not found${NC}"
    echo "Creating .env from env.sample..."
    cp env.sample .env
    echo -e "${YELLOW}⚠️  Please edit .env with your actual credentials before continuing${NC}"
    exit 1
else
    echo -e "${GREEN}✓ .env file found${NC}"
fi

# Step 2: Build Docker image
echo ""
echo "🔨 Step 2: Building Docker image..."
docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Docker image built successfully${NC}"
else
    echo -e "${RED}✗ Failed to build Docker image${NC}"
    exit 1
fi

# Step 3: Stop and remove existing container if running
echo ""
echo "🧹 Step 3: Cleaning up existing containers..."
if docker ps -a | grep -q ${CONTAINER_NAME}; then
    docker stop ${CONTAINER_NAME} 2>/dev/null || true
    docker rm ${CONTAINER_NAME} 2>/dev/null || true
    echo -e "${GREEN}✓ Cleaned up existing container${NC}"
else
    echo "No existing container to clean up"
fi

# Step 4: Run container with environment variables from .env
echo ""
echo "🚀 Step 4: Starting container..."
docker run -d \
    --name ${CONTAINER_NAME} \
    -p ${PORT}:${PORT} \
    --env-file .env \
    -e PORT=${PORT} \
    ${IMAGE_NAME}:${IMAGE_TAG}

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Container started successfully${NC}"
else
    echo -e "${RED}✗ Failed to start container${NC}"
    exit 1
fi

# Step 5: Wait for container to be ready
echo ""
echo "⏳ Step 5: Waiting for container to be ready..."
sleep 5

# Check if container is still running
if ! docker ps | grep -q ${CONTAINER_NAME}; then
    echo -e "${RED}✗ Container stopped unexpectedly${NC}"
    echo "Container logs:"
    docker logs ${CONTAINER_NAME}
    exit 1
fi

# Step 6: Test health endpoint
echo ""
echo "🏥 Step 6: Testing health endpoint..."
HEALTH_RESPONSE=$(curl -s http://localhost:${PORT}/ || echo "FAILED")

if echo "$HEALTH_RESPONSE" | grep -q "Doki Backend up"; then
    echo -e "${GREEN}✓ Health check passed${NC}"
    echo "Response: $HEALTH_RESPONSE"
else
    echo -e "${RED}✗ Health check failed${NC}"
    echo "Response: $HEALTH_RESPONSE"
    echo ""
    echo "Container logs:"
    docker logs ${CONTAINER_NAME}
    exit 1
fi

# Step 7: Test API docs endpoint
echo ""
echo "📚 Step 7: Testing API docs endpoint..."
DOCS_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:${PORT}/docs)

if [ "$DOCS_STATUS" = "200" ]; then
    echo -e "${GREEN}✓ API docs accessible${NC}"
else
    echo -e "${RED}✗ API docs not accessible (HTTP $DOCS_STATUS)${NC}"
fi

# Step 8: Show container info
echo ""
echo "📊 Step 8: Container Information"
echo "================================"
echo "Container Name: ${CONTAINER_NAME}"
echo "Image: ${IMAGE_NAME}:${IMAGE_TAG}"
echo "Port: ${PORT}"
echo "Status: $(docker ps --filter name=${CONTAINER_NAME} --format '{{.Status}}')"
echo ""
echo "🔗 Useful URLs:"
echo "   Health: http://localhost:${PORT}/"
echo "   API Docs: http://localhost:${PORT}/docs"
echo "   ReDoc: http://localhost:${PORT}/redoc"

# Step 9: Show logs
echo ""
echo "📝 Recent Container Logs:"
echo "========================"
docker logs --tail 20 ${CONTAINER_NAME}

# Step 10: Instructions
echo ""
echo "✅ Docker container is running!"
echo ""
echo "📋 Next Steps:"
echo "   • View logs: docker logs -f ${CONTAINER_NAME}"
echo "   • Stop container: docker stop ${CONTAINER_NAME}"
echo "   • Remove container: docker rm ${CONTAINER_NAME}"
echo "   • Access shell: docker exec -it ${CONTAINER_NAME} /bin/bash"
echo ""
echo "🧪 Test Endpoints:"
echo "   curl http://localhost:${PORT}/"
echo "   curl http://localhost:${PORT}/connectors/sheets/schema"
echo "   curl http://localhost:${PORT}/auth/google/login"
echo ""
echo -e "${GREEN}🎉 All tests passed!${NC}"
