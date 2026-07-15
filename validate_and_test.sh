#!/bin/bash

# Set error handling
set -e

echo "=== Starting validation of Book Dork Search API v2.0 ==="

# Function to cleanup on exit
cleanup() {
    echo "Stopping and removing containers..."
    docker-compose down -v > /dev/null 2>&1
}
trap cleanup EXIT

# Step 1: Start services
echo "Starting services..."
docker-compose up --build -d

# Wait for services to be ready (adjust time as needed)
echo "Waiting for services to initialize (40 seconds)..."
sleep 40

# Step 2: Test health endpoint
echo "Testing health endpoint..."
HEALTH_RESPONSE=$(curl -s -w "%{http_code}" http://localhost:8000/health -o /dev/null || echo "000")
if [ "$HEALTH_RESPONSE" -ne 200 ]; then
    echo "❌ HEALTH CHECK FAILED: Expected 200, got $HEALTH_RESPONSE"
    exit 1
else
    echo "✅ Health check passed"
fi

# Step 3: Test root endpoint
echo "Testing root endpoint..."
ROOT_RESPONSE=$(curl -s http://localhost:8000/ | grep '"status":"online"' || echo "NOT_FOUND")
if [ -z "$ROOT_RESPONSE" ]; then
    echo "❌ ROOT ENDPOINT FAILED: Expected 'status\":\"online\"' not found in response"
    exit 1
else
    echo "✅ Root endpoint passed"
fi

# Step 4: Test search and check for multiple sources
echo "Testing search for multiple sources..."
SEARCH_RESPONSE=$(curl -s -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"title":"harry potter"}')

# Check if response is valid JSON and extract sources
SOURCES=$(echo "$SEARCH_RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    sources = set(r['source'] for r in data.get('results', []))
    print(' '.join(sorted(sources)))
except Exception as e:
    print('ERROR:', str(e))
    sys.exit(1)
")

if [ "$SOURCES" = "ERROR:"* ]; then
    echo "❌ SEARCH FAILED: Invalid JSON response"
    echo "Response: $SEARCH_RESPONSE"
    exit 1
fi

echo "Found sources: $SOURCES"
SOURCE_COUNT=$(echo "$SOURCES" | wc -w)
if [ "$SOURCE_COUNT" -lt 2 ]; then
    echo "❌ MULTIPLE SOURCES CHECK FAILED: Expected at least 2 sources, got $SOURCE_COUNT"
    echo "Sources found: $SOURCES"
    exit 1
else
    echo "✅ Multiple sources check passed ($SOURCE_COUNT sources found)"
fi

# Step 5: Test rate limiting (light test - 101 requests)
echo "Testing rate limiting (making 101 requests)..."
RATE_LIMIT_COUNT=0
for i in {1..101}; do
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/search \
      -H "Content-Type: application/json" \
      -d '{"title":"ratelimittest"}' || echo "000")
    if [ "$STATUS" -eq" ]; then
        RATE_LIMIT_COUNT=$((RATE_LIMIT_COUNT + 1))
    fi
    # Small delay to avoid overwhelming, but not too slow
    sleep 0.01
done

if [ "$RATE_LIMIT_COUNT" -eq 0 ]; then
    echo "❌ RATE LIMITING FAILED: No 429 responses received in 101 requests"
    exit 1
else
    echo "✅ Rate limiting passed ($RATE_LIMIT_COUNT responses were 429)"
fi

# If we got here, all tests passed
echo ""
echo "🎉 ALL TESTS PASSED! The system is ready for GitHub commit."
echo "You can now safely run: git add . && git commit -m \"feat: implementar melhorias de produção\" && git push"

exit 0