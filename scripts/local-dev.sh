#!/bin/bash
# Local Development Script for IntelliDocs
# Starts all services for local development

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}    IntelliDocs Local Development${NC}"
echo -e "${GREEN}========================================${NC}"

# Check if .env exists
check_env() {
    if [ ! -f "$PROJECT_ROOT/.env" ]; then
        echo -e "${YELLOW}Creating .env from template...${NC}"
        cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env" 2>/dev/null || \
        cat > "$PROJECT_ROOT/.env" << 'EOF'
# AWS Credentials
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-1

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/intellidocs

# Redis (optional - for caching)
UPSTASH_REDIS_REST_URL=https://YOUR_REDIS.upstash.io
UPSTASH_REDIS_REST_TOKEN=YOUR_TOKEN

# JWT Secret
JWT_SECRET_KEY=change-me-in-production

# AWS Bedrock Models
BEDROCK_MODEL_ID=amazon.nova-pro-v1:0
BEDROCK_EMBEDDING_MODEL_ID=amazon.titan-embed-text-v2:0
EOF
        echo -e "${YELLOW}Please update .env with your credentials${NC}"
    fi
}

# Start Docker services
start_docker() {
    echo -e "\n${YELLOW}Starting Docker services...${NC}"
    
    cd "$PROJECT_ROOT"
    
    # Create docker-compose for local dev if not exists
    if [ ! -f "docker-compose.yml" ]; then
        cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  postgres:
    image: pgvector/pgvector:pg16
    container_name: intellidocs-postgres
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: intellidocs
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: intellidocs-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
EOF
    fi
    
    docker-compose up -d
    
    echo -e "${GREEN}Docker services started!${NC}"
}

# Install dependencies
install_deps() {
    echo -e "\n${YELLOW}Installing dependencies...${NC}"
    
    # Backend
    cd "$PROJECT_ROOT/backend"
    pip3 install -e ".[dev]" 2>/dev/null || pip3 install -e .
    
    # Frontend
    cd "$PROJECT_ROOT/frontend"
    npm install
    
    echo -e "${GREEN}Dependencies installed!${NC}"
}

# Run migrations
run_migrations() {
    echo -e "\n${YELLOW}Running database migrations...${NC}"
    
    cd "$PROJECT_ROOT/backend"
    
    # Wait for postgres
    sleep 3
    
    # Set DATABASE_URL for local postgres
    export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/intellidocs"
    
    # Run alembic migrations
    alembic upgrade head 2>/dev/null || echo "Migrations skipped (may need manual setup)"
    
    echo -e "${GREEN}Migrations complete!${NC}"
}

# Start backend
start_backend() {
    echo -e "\n${YELLOW}Starting backend...${NC}"
    
    cd "$PROJECT_ROOT/backend"
    
    # Load env
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
    
    # Use local database if cloud not configured
    if [ -z "$DATABASE_URL" ] || [ "$DATABASE_URL" = "your_database_url" ]; then
        export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/intellidocs"
    fi
    
    python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
    BACKEND_PID=$!
    
    echo -e "${GREEN}Backend started (PID: $BACKEND_PID)${NC}"
}

# Start frontend
start_frontend() {
    echo -e "\n${YELLOW}Starting frontend...${NC}"
    
    cd "$PROJECT_ROOT/frontend"
    
    npm run dev &
    FRONTEND_PID=$!
    
    echo -e "${GREEN}Frontend started (PID: $FRONTEND_PID)${NC}"
}

# Cleanup function
cleanup() {
    echo -e "\n${YELLOW}Stopping services...${NC}"
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    docker-compose down 2>/dev/null
    exit 0
}

# Main
main() {
    trap cleanup SIGINT SIGTERM
    
    check_env
    start_docker
    install_deps
    run_migrations
    start_backend
    start_frontend
    
    echo -e "\n${GREEN}========================================${NC}"
    echo -e "${GREEN}    All services running!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo -e "Backend:  http://localhost:8000"
    echo -e "Frontend: http://localhost:3001"
    echo -e "API Docs: http://localhost:8000/docs"
    echo -e "\nPress Ctrl+C to stop all services"
    
    # Wait for Ctrl+C
    wait
}

main "$@"
