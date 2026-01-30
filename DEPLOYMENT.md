# 🚀 Deployment Guide - PanScience Innovations

This guide covers various deployment strategies for PanScience Innovations.

## 📋 Table of Contents

- [Pre-Deployment Checklist](#pre-deployment-checklist)
- [Docker Deployment](#docker-deployment)
- [Cloud Platforms](#cloud-platforms)
- [Database Setup](#database-setup)
- [Environment Variables](#environment-variables)
- [Monitoring & Logging](#monitoring--logging)

---

## ✅ Pre-Deployment Checklist

### Security

- [ ] Generate strong JWT_SECRET_KEY (32+ characters)
- [ ] Set DEBUG=false in production
- [ ] Configure CORS with specific origins
- [ ] Enable HTTPS/SSL certificates
- [ ] Review file upload limits
- [ ] Enable rate limiting
- [ ] Update default passwords
- [ ] Review API key permissions

### Configuration

- [ ] Set up MongoDB Atlas production cluster
- [ ] Configure backup strategy
- [ ] Set up monitoring (APM)
- [ ] Configure logging aggregation
- [ ] Test health check endpoints
- [ ] Set up error tracking (Sentry)

### Performance

- [ ] Enable compression (gzip)
- [ ] Configure CDN for static assets
- [ ] Set up Redis for caching
- [ ] Optimize Docker images
- [ ] Configure resource limits

---

## 🐳 Docker Deployment

### Production Docker Compose

```bash
# Use production compose file
docker-compose -f docker-compose.prod.yml up -d --build

# View logs
docker-compose -f docker-compose.prod.yml logs -f

# Scale backend (if needed)
docker-compose -f docker-compose.prod.yml up -d --scale backend=3
```

### Single Server Deployment

**Requirements:**
- Ubuntu 20.04+ or similar Linux distribution
- Docker 20.10+
- Docker Compose 2.0+
- 2GB+ RAM, 20GB+ storage

**Steps:**

1. **Install Docker**
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

2. **Clone Repository**
```bash
git clone https://github.com/Vishwajeet-Kumar-Patel/PanScience_Innovations.git
cd PanScience_Innovations
```

3. **Configure Environment**
```bash
cd backend
cp .env.example .env
# Edit .env with production values
nano .env

cd ../frontend
cp .env.example .env
# Edit .env with production API URL
nano .env
```

4. **Deploy**
```bash
cd ..
docker-compose -f docker-compose.prod.yml up -d --build
```

5. **Set Up Reverse Proxy (Nginx)**
```bash
sudo apt install nginx certbot python3-certbot-nginx

# Create Nginx config
sudo nano /etc/nginx/sites-available/panscience

# Add configuration:
server {
    listen 80;
    server_name yourdomain.com;
    
    location / {
        proxy_pass http://localhost:5173;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
    
    location /api {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}

# Enable site
sudo ln -s /etc/nginx/sites-available/panscience /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Get SSL certificate
sudo certbot --nginx -d yourdomain.com
```

---

## ☁️ Cloud Platforms

### AWS Deployment

#### Using ECS (Elastic Container Service)

1. **Push Images to ECR**
```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Build and tag images
docker build -t panscience-backend ./backend
docker tag panscience-backend:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/panscience-backend:latest

docker build -f ./frontend/Dockerfile.prod -t panscience-frontend ./frontend
docker tag panscience-frontend:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/panscience-frontend:latest

# Push to ECR
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/panscience-backend:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/panscience-frontend:latest
```

2. **Create ECS Task Definition**
```json
{
  "family": "panscience",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "containerDefinitions": [
    {
      "name": "backend",
      "image": "<account-id>.dkr.ecr.us-east-1.amazonaws.com/panscience-backend:latest",
      "portMappings": [{"containerPort": 8000}],
      "environment": [
        {"name": "ENVIRONMENT", "value": "production"}
      ],
      "secrets": [
        {"name": "MONGODB_URL", "valueFrom": "arn:aws:secretsmanager:..."}
      ]
    }
  ]
}
```

3. **Create ECS Service**
```bash
aws ecs create-service \
  --cluster panscience-cluster \
  --service-name panscience-service \
  --task-definition panscience \
  --desired-count 2 \
  --launch-type FARGATE
```

### Google Cloud Platform

#### Using Cloud Run

```bash
# Build and push to GCR
gcloud builds submit --tag gcr.io/PROJECT_ID/panscience-backend ./backend
gcloud builds submit --tag gcr.io/PROJECT_ID/panscience-frontend ./frontend

# Deploy to Cloud Run
gcloud run deploy panscience-backend \
  --image gcr.io/PROJECT_ID/panscience-backend \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated

gcloud run deploy panscience-frontend \
  --image gcr.io/PROJECT_ID/panscience-frontend \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

### DigitalOcean App Platform

1. **Create app.yaml**
```yaml
name: panscience
services:
  - name: backend
    github:
      repo: Vishwajeet-Kumar-Patel/PanScience_Innovations
      branch: main
      deploy_on_push: true
    dockerfile_path: backend/Dockerfile
    envs:
      - key: MONGODB_URL
        scope: RUN_TIME
        type: SECRET
    http_port: 8000
    instance_count: 2
    instance_size_slug: basic-xs
    
  - name: frontend
    github:
      repo: Vishwajeet-Kumar-Patel/PanScience_Innovations
      branch: main
      deploy_on_push: true
    dockerfile_path: frontend/Dockerfile.prod
    http_port: 80
    instance_count: 1
    instance_size_slug: basic-xs
```

2. **Deploy**
```bash
doctl apps create --spec app.yaml
```

### Heroku

```bash
# Login to Heroku
heroku login
heroku container:login

# Create app
heroku create panscience-backend
heroku create panscience-frontend

# Set environment variables
heroku config:set MONGODB_URL="..." --app panscience-backend
heroku config:set JWT_SECRET_KEY="..." --app panscience-backend

# Deploy backend
cd backend
heroku container:push web --app panscience-backend
heroku container:release web --app panscience-backend

# Deploy frontend
cd ../frontend
heroku container:push web --app panscience-frontend
heroku container:release web --app panscience-frontend
```

---

## 🗄️ Database Setup

### MongoDB Atlas (Recommended)

1. **Create Cluster**
   - Go to [MongoDB Atlas](https://www.mongodb.com/cloud/atlas)
   - Create a free M0 cluster or paid cluster
   - Choose region close to your servers

2. **Configure Network Access**
   - Add IP addresses of your servers
   - Or allow access from anywhere (0.0.0.0/0) for development

3. **Create Database User**
   - Username: panscience_user
   - Password: Generate strong password
   - Assign readWrite role

4. **Get Connection String**
```
mongodb+srv://panscience_user:<password>@cluster0.xxxxx.mongodb.net/panscience?retryWrites=true&w=majority
```

5. **Enable Backup**
   - Configure continuous backup
   - Set retention period
   - Test restore process

---

## 🔧 Environment Variables

### Production Backend .env

```bash
# Application
ENVIRONMENT=production
DEBUG=false

# MongoDB
MONGODB_URL=mongodb+srv://user:pass@cluster.mongodb.net/panscience?retryWrites=true&w=majority
DATABASE_NAME=panscience

# Security
JWT_SECRET_KEY=<generate-secure-random-key-32chars>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# AI Services
OPENAI_API_KEY=sk-proj-xxxxx
DEEPGRAM_API_KEY=xxxxx

# Storage
UPLOAD_DIR=/app/uploads
MAX_FILE_SIZE=524288000
VECTOR_STORE_TYPE=faiss

# Performance
RATE_LIMIT_ENABLED=true
RATE_LIMIT_CALLS=100
RATE_LIMIT_PERIOD=60

# Redis (if enabled)
REDIS_URL=redis://redis:6379
REDIS_ENABLED=false
```

### Production Frontend .env

```bash
VITE_API_BASE_URL=https://api.yourdomain.com
```

---

## 📊 Monitoring & Logging

### Application Monitoring

**Set up Sentry (Error Tracking)**

```python
# backend/app/main.py
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

sentry_sdk.init(
    dsn="https://xxxxx@sentry.io/xxxxx",
    integrations=[FastApiIntegration()],
    environment="production",
    traces_sample_rate=0.1
)
```

### Health Checks

```bash
# Check backend health
curl https://api.yourdomain.com/health

# Expected response
{
  "status": "healthy",
  "app_name": "PanScience Q&A",
  "version": "1.0.0",
  "environment": "production"
}
```

### Logging

**Centralized Logging with ELK Stack**

```yaml
# Add to docker-compose.prod.yml
elasticsearch:
  image: elasticsearch:8.11.0
  environment:
    - discovery.type=single-node
  ports:
    - "9200:9200"

kibana:
  image: kibana:8.11.0
  ports:
    - "5601:5601"
  depends_on:
    - elasticsearch

logstash:
  image: logstash:8.11.0
  volumes:
    - ./logstash.conf:/usr/share/logstash/pipeline/logstash.conf
  depends_on:
    - elasticsearch
```

### Backup Strategy

```bash
# MongoDB backup (run as cron job)
mongodump --uri="mongodb+srv://..." --out=/backup/$(date +%Y%m%d)

# Uploads backup
tar -czf /backup/uploads-$(date +%Y%m%d).tar.gz /app/uploads

# FAISS index backup
tar -czf /backup/faiss-$(date +%Y%m%d).tar.gz /app/faiss_index
```

---

## 🔄 CI/CD Pipeline

### GitHub Actions

See `.github/workflows/ci-cd.yml` for automated:
- Testing
- Building
- Deploying

### Manual Deployment Updates

```bash
# Pull latest changes
git pull origin main

# Rebuild and restart
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up -d --build

# Check logs
docker-compose -f docker-compose.prod.yml logs -f
```

---

## 🆘 Troubleshooting

### Container Not Starting

```bash
# Check logs
docker logs panscience-backend
docker logs panscience-frontend

# Check resource usage
docker stats

# Restart specific service
docker-compose restart backend
```

### Database Connection Issues

- Verify MongoDB URL is correct
- Check IP whitelist in Atlas
- Ensure database user has correct permissions
- Test connection string with mongosh

### Performance Issues

- Check container resource limits
- Monitor MongoDB metrics
- Review application logs
- Enable Redis caching
- Scale horizontally (add more containers)

---

## 📞 Support

For deployment issues:
- Open an issue on GitHub
- Check documentation
- Review logs carefully

---

**Last Updated:** January 2026  
**Version:** 1.0.0
