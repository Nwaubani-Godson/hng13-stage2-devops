# Quick Setup Guide for Ubuntu

This guide will walk you through setting up and running the Blue/Green deployment on your Ubuntu machine.

## Prerequisites Check

First, let's make sure you have everything installed:

```bash
# Check Docker
docker --version
# Should show: Docker version 20.10+ or higher

# Check Docker Compose
docker-compose --version
# Should show: Docker Compose version 2.0+ or higher

# If not installed, install them:
sudo apt update
sudo apt install -y docker.io docker-compose

# Add your user to docker group (to run without sudo)
sudo usermod -aG docker $USER
# Log out and back in for this to take effect
```

## Step-by-Step Setup

### 1. Create Project Directory
```bash
# Create and navigate to project directory
mkdir -p ~/devops-stage-2
cd ~/devops-stage-2
```

### 2. Create All Required Files

Create each file with the content provided in the artifacts:

```bash
# Create docker-compose.yml
nano docker-compose.yml
# Paste the content, save (Ctrl+O, Enter, Ctrl+X)

# Create Dockerfile.nginx
nano Dockerfile.nginx
# Paste the content, save

# Create nginx.conf.template
nano nginx.conf.template
# Paste the content, save

# Create entrypoint.sh
nano entrypoint.sh
# Paste the content, save

# Make entrypoint.sh executable
chmod +x entrypoint.sh

# Create .env from example
nano .env
# Paste the .env.example content, save

# Create .gitignore
nano .gitignore
# Paste the content, save

# Create test script
nano test-failover.sh
# Paste the content, save

# Make test script executable
chmod +x test-failover.sh
```

### 3. Verify Your Files

Your directory should look like this:

```bash
ls -la
# Should show:
# docker-compose.yml
# Dockerfile.nginx
# nginx.conf.template
# entrypoint.sh (executable)
# .env
# .gitignore
# test-failover.sh (executable)
# README.md (optional)
# DECISION.md (optional)
```

### 4. Start the Services

```bash
# Pull the images (this might take a moment)
docker-compose pull

# Build and start all services
docker-compose up -d

# Check if all services are running
docker-compose ps

# You should see 3 services running:
# - nginx_lb (port 8080)
# - app_blue (port 8081)
# - app_green (port 8082)
```

### 5. Verify Everything Works

```bash
# Test the main endpoint (through Nginx)
curl -i http://localhost:8080/version

# You should see:
# HTTP/1.1 200 OK
# X-App-Pool: blue
# X-Release-Id: blue-v1.0.0

# Test Blue directly
curl -i http://localhost:8081/version

# Test Green directly
curl -i http://localhost:8082/version
```

### 6. Test Failover

```bash
# Run the automated test script
./test-failover.sh

# Or test manually:

# 1. Induce chaos on Blue
curl -X POST http://localhost:8081/chaos/start?mode=error

# 2. Test main endpoint (should automatically use Green)
curl -i http://localhost:8080/version
# Should show: X-App-Pool: green

# 3. Stop chaos
curl -X POST http://localhost:8081/chaos/stop
```

## Troubleshooting

### Issue: "Permission denied" when running docker commands

```bash
# Add yourself to docker group
sudo usermod -aG docker $USER

# Log out and back in, or run:
newgrp docker

# Try again
docker ps
```

### Issue: Port already in use

```bash
# Check what's using the ports
sudo lsof -i :8080
sudo lsof -i :8081
sudo lsof -i :8082

# Stop the conflicting service or change ports in .env
```

### Issue: Services not starting

```bash
# Check logs
docker-compose logs

# Check specific service
docker-compose logs nginx
docker-compose logs app_blue

# Restart services
docker-compose restart
```

### Issue: Can't reach services

```bash
# Check if services are running
docker-compose ps

# Check network connectivity
docker-compose exec nginx ping app_blue
docker-compose exec nginx ping app_green

# Rebuild if needed
docker-compose down
docker-compose up -d --build
```

### Issue: Headers not showing

```bash
# Use verbose curl
curl -v http://localhost:8080/version

# Check Nginx logs
docker-compose logs nginx | tail -20
```

## Viewing Logs

```bash
# Follow all logs
docker-compose logs -f

# Follow specific service
docker-compose logs -f nginx

# View last 50 lines
docker-compose logs --tail=50

# View logs since 5 minutes ago
docker-compose logs --since 5m
```

## Stopping and Cleaning Up

```bash
# Stop all services
docker-compose down

# Stop and remove volumes
docker-compose down -v

# Remove all (including images)
docker-compose down --rmi all -v
```

## Initialize Git Repository (Optional)

```bash
# Initialize git
git init

# Add files
git add .

# Commit
git commit -m "Initial commit: Blue/Green deployment with Nginx"

# Add remote (replace with your repo URL)
git remote add origin https://github.com/username/repo.git

# Push
git push -u origin main
```

## Before Submitting

Make sure to check:

- [ ] All services start successfully
- [ ] Can access http://localhost:8080/version
- [ ] Headers show correct pool and release ID
- [ ] Failover works (run test-failover.sh)
- [ ] Zero errors during failover test
- [ ] README.md is complete
- [ ] .env.example exists (don't commit .env)
- [ ] Repository is public on GitHub
- [ ] DECISION.md explains your choices (optional but recommended)

## Quick Reference Commands

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# Restart services
docker-compose restart

# View logs
docker-compose logs -f

# Check status
docker-compose ps

# Test endpoint
curl -i http://localhost:8080/version

# Induce chaos
curl -X POST http://localhost:8081/chaos/start?mode=error

# Stop chaos
curl -X POST http://localhost:8081/chaos/stop

# Run full test
./test-failover.sh
```

