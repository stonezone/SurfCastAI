# SurfCastAI Deployment Guide

## Table of Contents

- [Overview](#overview)
- [Production Deployment](#production-deployment)
- [Automated Scheduling](#automated-scheduling)
- [Docker Deployment](#docker-deployment)
- [Monitoring and Alerting](#monitoring-and-alerting)
- [Backup and Recovery](#backup-and-recovery)
- [Security Considerations](#security-considerations)
- [Performance Optimization](#performance-optimization)
- [Troubleshooting](#troubleshooting)

## Overview

This guide covers deploying SurfCastAI in production environments, including:
- Automated daily forecast generation
- Web viewer deployment
- Monitoring and alerting
- Backup strategies
- Security hardening

### Deployment Architectures

**Single-Server (Recommended for most users):**
```
┌─────────────────────────────────┐
│   Linux/macOS Server            │
│                                 │
│  ┌──────────────────────────┐  │
│  │  SurfCastAI              │  │
│  │  - Data collection       │  │
│  │  - Processing            │  │
│  │  - Forecast generation   │  │
│  │  - Validation            │  │
│  └──────────────────────────┘  │
│                                 │
│  ┌──────────────────────────┐  │
│  │  FastAPI Web Viewer      │  │
│  │  (port 8000)             │  │
│  └──────────────────────────┘  │
│                                 │
│  ┌──────────────────────────┐  │
│  │  Cron/Systemd            │  │
│  │  - Daily forecasts       │  │
│  │  - Validation            │  │
│  └──────────────────────────┘  │
└─────────────────────────────────┘
```

**Docker Deployment:**
```
┌─────────────────────────────────┐
│   Docker Host                   │
│                                 │
│  ┌──────────────────────────┐  │
│  │  surfcastai Container    │  │
│  │  - App + dependencies    │  │
│  │  - Cron scheduler        │  │
│  └──────────────────────────┘  │
│                                 │
│  ┌──────────────────────────┐  │
│  │  Web Viewer Container    │  │
│  │  - FastAPI + Uvicorn     │  │
│  │  - Port 8000 → 80        │  │
│  └──────────────────────────┘  │
│                                 │
│  ┌──────────────────────────┐  │
│  │  Volume Mounts           │  │
│  │  - data/                 │  │
│  │  - output/               │  │
│  │  - logs/                 │  │
│  └──────────────────────────┘  │
└─────────────────────────────────┘
```

## Production Deployment

### System Requirements

**Minimum:**
- CPU: 2 cores
- RAM: 4 GB
- Disk: 20 GB
- Network: Stable broadband connection

**Recommended:**
- CPU: 4+ cores
- RAM: 8+ GB
- Disk: 50 GB SSD
- Network: Low-latency connection

**Operating Systems:**
- Linux (Ubuntu 20.04+, Debian 11+, CentOS 8+)
- macOS 11+
- Windows 10+ (with WSL2)

### Installation Steps

#### 1. Clone Repository

```bash
# Clone to production directory
cd /opt
sudo git clone https://github.com/yourusername/surfCastAI.git
cd surfCastAI

# Set ownership
sudo chown -R surfcast:surfcast /opt/surfCastAI
```

#### 2. Create Service User

```bash
# Create dedicated user (Linux)
sudo useradd -r -s /bin/bash -d /opt/surfCastAI -m surfcast

# Add to necessary groups
sudo usermod -aG www-data surfcast  # If serving web viewer
```

#### 3. Install Dependencies

```bash
# Switch to service user
sudo su - surfcast

# Run setup script
./setup.sh

# Activate virtual environment
source venv/bin/activate

# Verify installation
python src/main.py --help
```

#### 4. Configure Application

```bash
# Copy configuration template
cp config/config.example.yaml config/config.yaml

# Create .env file with API key
cat > .env << EOF
OPENAI_API_KEY=sk-your-production-key-here
EOF

# Set restrictive permissions
chmod 600 .env
chmod 600 config/config.yaml

# Edit configuration for production
nano config/config.yaml
```

**Production config.yaml:**
```yaml
general:
  log_level: INFO
  log_file: /var/log/surfcastai/app.log
  output_directory: /var/www/surfcastai/forecasts
  data_directory: /opt/surfCastAI/data

openai:
  model: gpt-4o  # Best quality for production

forecast:
  refinement_cycles: 2
  formats: markdown,html,pdf
```

#### 5. Test Installation

```bash
# Generate a test forecast
python src/main.py run --mode full

# Verify output
ls -l output/

# Check logs
tail -50 logs/surfcastai.log
```

### Directory Structure (Production)

```
/opt/surfCastAI/              # Application root
├── config/
│   ├── config.yaml           # Production config (not in git)
│   └── .env                  # API keys (not in git)
├── data/                     # Data bundles
├── venv/                     # Python virtual environment
├── src/                      # Application source
└── logs/                     # Application logs

/var/log/surfcastai/          # System logs (logrotate)
└── app.log

/var/www/surfcastai/          # Web-accessible output
└── forecasts/                # Generated forecasts
    └── forecast_*/
```

## Automated Scheduling

### Cron Setup (Linux/macOS)

#### Daily Forecast Generation

Use the helper script to manage logging and basic rotation:

```bash
# Edit crontab
crontab -e

# Run twice daily (adjust schedule as needed)
0 6,18 * * * /opt/surfCastAI/deployment/cron_example.sh >> /dev/null 2>&1
```

`deployment/cron_example.sh` writes forecasts to `logs/cron-YYYYMMDD.log`, runs `python src.main.py run --mode full`, and keeps the seven newest cron logs.

#### Weekly Accuracy Report

Use the provided helper to capture seven-day accuracy snapshots:

```
0 20 * * 0 /opt/surfCastAI/scripts/weekly_review.sh >> /dev/null 2>&1
```

The script stores output at `logs/weekly-YYYYMMDD.log` and echoes a short summary to stdout.

#### Cron Best Practices

1. **Use absolute paths** for Python and working directory
2. **Redirect output** to log files for debugging
3. **Set appropriate environment** (OPENAI_API_KEY)
4. **Test commands manually** before adding to cron
5. **Monitor cron logs** for failures

**Cron environment setup:**
```bash
# Add to crontab
SHELL=/bin/bash
PATH=/usr/local/bin:/usr/bin:/bin
OPENAI_API_KEY=sk-your-key-here

# Or load from .env in script
```

### Systemd Timer Setup (Linux)

More robust than cron, with better logging and monitoring.

#### Create Service Unit

```bash
# /etc/systemd/system/surfcastai-forecast.service
sudo nano /etc/systemd/system/surfcastai-forecast.service
```

```ini
[Unit]
Description=SurfCastAI Forecast Generation
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=surfcast
Group=surfcast
WorkingDirectory=/opt/surfCastAI
Environment="PATH=/opt/surfCastAI/venv/bin:/usr/bin:/bin"
EnvironmentFile=/opt/surfCastAI/.env
ExecStart=/opt/surfCastAI/venv/bin/python src/main.py run --mode full
StandardOutput=journal
StandardError=journal
SyslogIdentifier=surfcastai-forecast

[Install]
WantedBy=multi-user.target
```

#### Create Timer Unit

```bash
# /etc/systemd/system/surfcastai-forecast.timer
sudo nano /etc/systemd/system/surfcastai-forecast.timer
```

```ini
[Unit]
Description=SurfCastAI Forecast Generation Timer
Requires=surfcastai-forecast.service

[Timer]
# Run daily at 6:00 AM HST (16:00 UTC)
OnCalendar=*-*-* 16:00:00
Persistent=true
Unit=surfcastai-forecast.service

[Install]
WantedBy=timers.target
```

#### Enable and Start

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable timer (start on boot)
sudo systemctl enable surfcastai-forecast.timer

# Start timer
sudo systemctl start surfcastai-forecast.timer

# Check status
sudo systemctl status surfcastai-forecast.timer

# View logs
sudo journalctl -u surfcastai-forecast.service -f
```

### Web Viewer Deployment

#### Systemd Service (Production)

```bash
# /etc/systemd/system/surfcastai-web.service
sudo nano /etc/systemd/system/surfcastai-web.service
```

```ini
[Unit]
Description=SurfCastAI Web Viewer
After=network.target

[Service]
Type=notify
User=surfcast
Group=surfcast
WorkingDirectory=/opt/surfCastAI
Environment="PATH=/opt/surfCastAI/venv/bin"
Environment="SURFCAST_OUTPUT_DIR=/var/www/surfcastai/forecasts"
ExecStart=/opt/surfCastAI/venv/bin/uvicorn src.web.app:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 4 \
    --log-level info
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable surfcastai-web.service
sudo systemctl start surfcastai-web.service

# Check status
sudo systemctl status surfcastai-web.service
```

#### Nginx Reverse Proxy

```bash
# /etc/nginx/sites-available/surfcastai
sudo nano /etc/nginx/sites-available/surfcastai
```

```nginx
server {
    listen 80;
    server_name surf.example.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name surf.example.com;

    # SSL certificates (from Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/surf.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/surf.example.com/privkey.pem;

    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Proxy to FastAPI
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Static files (optional, if serving directly)
    location /forecasts/ {
        alias /var/www/surfcastai/forecasts/;
        autoindex on;
    }

    # Logs
    access_log /var/log/nginx/surfcastai-access.log;
    error_log /var/log/nginx/surfcastai-error.log;
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/surfcastai /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx
```

## Docker Deployment

### Dockerfile

```dockerfile
# Dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    cairo \
    pango \
    gdk-pixbuf \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Create app user
RUN useradd -m -u 1000 surfcast

# Set working directory
WORKDIR /app

# Copy application
COPY --chown=surfcast:surfcast . /app

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create necessary directories
RUN mkdir -p /app/data /app/output /app/logs && \
    chown -R surfcast:surfcast /app

# Switch to app user
USER surfcast

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Default command
CMD ["python", "src/main.py", "run", "--mode", "full"]
```

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  surfcastai:
    build: .
    container_name: surfcastai
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - ./data:/app/data
      - ./output:/app/output
      - ./logs:/app/logs
      - ./config:/app/config
    command: >
      sh -c "
      while true; do
        python src/main.py run --mode full
        sleep 21600
      done
      "

  web:
    build: .
    container_name: surfcastai-web
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - SURFCAST_OUTPUT_DIR=/app/output
    volumes:
      - ./output:/app/output:ro
    command: uvicorn src.web.app:app --host 0.0.0.0 --port 8000 --workers 4

  nginx:
    image: nginx:alpine
    container_name: surfcastai-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - ./output:/var/www/html/forecasts:ro
      - /etc/letsencrypt:/etc/letsencrypt:ro
    depends_on:
      - web
```

### Build and Run

```bash
# Build image
docker-compose build

# Start services
docker-compose up -d

# View logs
docker-compose logs -f surfcastai

# Stop services
docker-compose down
```

## Monitoring and Alerting

### Log Monitoring

#### Logrotate Configuration

```bash
# /etc/logrotate.d/surfcastai
sudo nano /etc/logrotate.d/surfcastai
```

```
/var/log/surfcastai/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0644 surfcast surfcast
    sharedscripts
    postrotate
        systemctl reload surfcastai-web 2>/dev/null || true
    endscript
}
```

#### Log Analysis Script

```bash
#!/bin/bash
# /opt/surfCastAI/scripts/check_logs.sh

LOG_FILE="/var/log/surfcastai/app.log"
ERROR_COUNT=$(tail -1000 "$LOG_FILE" | grep -c "ERROR")
CRITICAL_COUNT=$(tail -1000 "$LOG_FILE" | grep -c "CRITICAL")

if [ "$CRITICAL_COUNT" -gt 0 ]; then
    echo "CRITICAL: $CRITICAL_COUNT critical errors in last 1000 lines"
    tail -50 "$LOG_FILE" | grep "CRITICAL" | mail -s "SurfCastAI CRITICAL Errors" admin@example.com
    exit 2
elif [ "$ERROR_COUNT" -gt 10 ]; then
    echo "WARNING: $ERROR_COUNT errors in last 1000 lines"
    exit 1
else
    echo "OK: No significant errors"
    exit 0
fi
```

### Health Check Endpoints

Add to `src/web/app.py`:

```python
@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

@app.get("/health/forecast")
async def forecast_health():
    """Check latest forecast status."""
    # Get latest forecast
    output_dir = Path(os.getenv("SURFCAST_OUTPUT_DIR", "output"))
    forecasts = sorted(output_dir.glob("forecast_*"), reverse=True)

    if not forecasts:
        return {"status": "unhealthy", "error": "No forecasts found"}

    latest = forecasts[0]
    age_hours = (datetime.now() - datetime.fromtimestamp(latest.stat().st_mtime)).total_seconds() / 3600

    if age_hours > 36:
        return {"status": "stale", "age_hours": age_hours, "latest": latest.name}

    return {"status": "healthy", "age_hours": age_hours, "latest": latest.name}
```

### Prometheus Metrics (Optional)

```python
# Add to requirements.txt
prometheus-client==0.18.0

# Add to src/web/app.py
from prometheus_client import Counter, Histogram, generate_latest

forecast_counter = Counter('surfcastai_forecasts_total', 'Total forecasts generated')
forecast_duration = Histogram('surfcastai_forecast_duration_seconds', 'Forecast generation duration')

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(generate_latest(), media_type="text/plain")
```

### Alerting with Healthchecks.io

```bash
# Add to cron job
0 6 * * * cd /opt/surfCastAI && /opt/surfCastAI/venv/bin/python src/main.py run --mode full && curl -fsS -m 10 --retry 5 -o /dev/null https://hc-ping.com/YOUR-UUID-HERE
```

### Email Alerts

```bash
#!/bin/bash
# /opt/surfCastAI/scripts/forecast_with_alerts.sh

cd /opt/surfCastAI
source venv/bin/activate

# Run forecast
python src/main.py run --mode full > /tmp/forecast_output.txt 2>&1
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    # Send failure alert
    cat /tmp/forecast_output.txt | mail -s "SurfCastAI Forecast FAILED" admin@example.com
    exit $EXIT_CODE
fi

# Check forecast quality
CONFIDENCE=$(grep -oP 'Confidence: \K[0-9.]+' /tmp/forecast_output.txt | head -1)
if (( $(echo "$CONFIDENCE < 0.6" | bc -l) )); then
    echo "Low confidence forecast: $CONFIDENCE" | mail -s "SurfCastAI Low Confidence Warning" admin@example.com
fi

exit 0
```

## Backup and Recovery

### Backup Strategy

**What to Backup:**
1. Configuration files (`.env`, `config.yaml`)
2. Validation database (`data/validation.db`)
3. Generated forecasts (`output/`)
4. Application logs (optional)

**Backup Frequency:**
- Configuration: After any changes
- Database: Daily
- Forecasts: Weekly (or retain N most recent)
- Logs: Not typically backed up (use log rotation)

### Backup Script

```bash
#!/bin/bash
# /opt/surfCastAI/scripts/backup.sh

BACKUP_DIR="/backups/surfcastai"
DATE=$(date +%Y%m%d)
RETENTION_DAYS=30

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup configuration
tar -czf "$BACKUP_DIR/config_$DATE.tar.gz" -C /opt/surfCastAI config/ .env

# Backup validation database
cp /opt/surfCastAI/data/validation.db "$BACKUP_DIR/validation_$DATE.db"
gzip "$BACKUP_DIR/validation_$DATE.db"

# Backup recent forecasts (last 30 days)
find /opt/surfCastAI/output -name "forecast_*" -mtime -30 -type d | \
    tar -czf "$BACKUP_DIR/forecasts_$DATE.tar.gz" -T -

# Remove old backups
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "*.db.gz" -mtime +$RETENTION_DAYS -delete

echo "Backup completed: $DATE"
```

### Automated Backups (Cron)

```bash
# Add to crontab
0 2 * * * /opt/surfCastAI/scripts/backup.sh >> /var/log/surfcastai/backup.log 2>&1
```

### Restore Procedure

```bash
# Restore configuration
cd /opt/surfCastAI
tar -xzf /backups/surfcastai/config_20251007.tar.gz

# Restore validation database
gunzip -c /backups/surfcastai/validation_20251007.db.gz > data/validation.db

# Restore forecasts
tar -xzf /backups/surfcastai/forecasts_20251007.tar.gz -C output/

# Restart services
sudo systemctl restart surfcastai-web
```

### Cloud Backup (AWS S3)

```bash
#!/bin/bash
# /opt/surfCastAI/scripts/backup_s3.sh

BUCKET="s3://my-surfcastai-backups"
DATE=$(date +%Y%m%d)

# Sync validation database
aws s3 cp /opt/surfCastAI/data/validation.db \
    "$BUCKET/validation/validation_$DATE.db"

# Sync recent forecasts
aws s3 sync /opt/surfCastAI/output/ \
    "$BUCKET/forecasts/" \
    --exclude "*" \
    --include "forecast_*" \
    --storage-class GLACIER
```

## Security Considerations

### File Permissions

```bash
# Restrict configuration files
chmod 600 /opt/surfCastAI/.env
chmod 600 /opt/surfCastAI/config/config.yaml
chmod 700 /opt/surfCastAI/config

# Application directories
chown -R surfcast:surfcast /opt/surfCastAI
chmod 755 /opt/surfCastAI
chmod 755 /opt/surfCastAI/src
```

### Firewall Configuration

```bash
# Ubuntu/Debian (ufw)
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw allow 22/tcp    # SSH (restrict source IPs if possible)
sudo ufw enable

# RHEL/CentOS (firewalld)
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

### API Key Rotation

```bash
# 1. Generate new OpenAI API key
# 2. Update .env file
echo "OPENAI_API_KEY=sk-new-key-here" > /opt/surfCastAI/.env

# 3. Restart services (if using systemd)
sudo systemctl restart surfcastai-forecast
sudo systemctl restart surfcastai-web

# 4. Revoke old key via OpenAI dashboard
```

### Principle of Least Privilege

- Run application as non-root user (`surfcast`)
- Restrict file permissions (600 for configs, 644 for code)
- Use separate API keys for dev/prod
- Limit network access (firewall rules)

## Performance Optimization

### Concurrent Data Collection

```yaml
# config.yaml
data_collection:
  max_concurrent: 20  # Increase parallelism
```

### Caching

```python
# Add Redis caching for buoy data (optional)
import redis

cache = redis.Redis(host='localhost', port=6379, db=0)

def get_buoy_data_cached(buoy_id):
    key = f"buoy:{buoy_id}"
    cached = cache.get(key)
    if cached:
        return json.loads(cached)

    data = fetch_buoy_data(buoy_id)
    cache.setex(key, 3600, json.dumps(data))  # 1 hour TTL
    return data
```

### Database Optimization

```sql
-- Add indexes for faster validation queries
CREATE INDEX idx_validations_forecast_id ON validations(forecast_id);
CREATE INDEX idx_predictions_forecast_id ON predictions(forecast_id);
CREATE INDEX idx_forecasts_created_at ON forecasts(created_at);
```

## Troubleshooting

### Service Won't Start

```bash
# Check service status
sudo systemctl status surfcastai-web

# View logs
sudo journalctl -u surfcastai-web -n 50

# Check permissions
ls -la /opt/surfCastAI/.env
ls -la /opt/surfCastAI/config/config.yaml

# Test manually
sudo su - surfcast
cd /opt/surfCastAI
source venv/bin/activate
python src/main.py run --mode full
```

### Cron Jobs Not Running

```bash
# Check cron logs (Ubuntu/Debian)
grep CRON /var/log/syslog

# Check cron logs (RHEL/CentOS)
grep CRON /var/log/cron

# Test cron command manually
cd /opt/surfCastAI && /opt/surfCastAI/venv/bin/python src/main.py run --mode full

# Verify crontab
crontab -l
```

### Database Lock Issues

```bash
# Check for stale lock
fuser /opt/surfCastAI/data/validation.db

# Kill processes holding lock
fuser -k /opt/surfCastAI/data/validation.db

# Backup and rebuild database
cp data/validation.db data/validation.db.backup
rm data/validation.db
python src/main.py validate-all  # Recreates database
```

### High Memory Usage

```bash
# Monitor memory
htop
free -h

# Check process memory
ps aux | grep python | sort -k 4 -r

# Reduce image processing
# Edit config.yaml:
forecast:
  max_images: 4  # Reduce from 10
  image_detail_levels:
    pressure_charts: low
    wave_models: low
```

## Summary

This guide covered:
- **Production Deployment:** Installation, configuration, directory structure
- **Automated Scheduling:** Cron, systemd timers, web viewer deployment
- **Docker Deployment:** Dockerfile, docker-compose, container orchestration
- **Monitoring:** Log rotation, health checks, alerting
- **Backup:** Automated backups, restore procedures, cloud sync
- **Security:** Permissions, firewall, API key rotation
- **Performance:** Concurrency, caching, database optimization
- **Troubleshooting:** Common issues and solutions

For additional support, see:
- [README.md](README.md) - General usage
- [CONFIGURATION.md](CONFIGURATION.md) - Configuration options
- [VALIDATION_GUIDE.md](VALIDATION_GUIDE.md) - Validation system

Production checklist:
- [ ] Install on dedicated server/container
- [ ] Configure secure API keys in `.env`
- [ ] Set up automated scheduling (cron/systemd)
- [ ] Deploy web viewer with reverse proxy
- [ ] Configure log rotation
- [ ] Set up monitoring and alerting
- [ ] Implement backup strategy
- [ ] Test restore procedure
- [ ] Harden security (permissions, firewall)
- [ ] Document custom deployment specifics
