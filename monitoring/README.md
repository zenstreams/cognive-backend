# Cognive Monitoring & Observability Stack

This directory contains the configuration files for the complete monitoring and observability stack for the Cognive Control Plane.

## Stack Components

| Component | Purpose | Port | URL (Local) |
|-----------|---------|------|-------------|
| **Prometheus** | Metrics collection & alerting | 9090 | http://localhost:9090 |
| **Grafana** | Dashboards & visualization | 3030 | http://localhost:3030 |
| **Alertmanager** | Alert routing & notifications | 9093 | http://localhost:9093 |
| **Loki** | Log aggregation | 3100 | http://localhost:3100 |
| **Promtail** | Log collection | 9080 | - |
| **GlitchTip** | Error tracking (Sentry alternative) | 8010 | http://localhost:8010 |
| **Uptime Kuma** | Uptime monitoring | 3001 | http://localhost:3001 |

## Quick Start

### 1. Start the Monitoring Stack

```bash
# Start the main application stack first
docker-compose up -d

# Then start the monitoring stack
docker-compose -f docker-compose.monitoring.yml up -d
```

### 2. Access Dashboards

- **Grafana**: http://localhost:3030 (admin/admin)
- **Prometheus**: http://localhost:9090
- **Alertmanager**: http://localhost:9093
- **GlitchTip**: http://localhost:8010
- **Uptime Kuma**: http://localhost:3001

### 3. Default Credentials

| Service | Username | Password |
|---------|----------|----------|
| Grafana | admin | admin |
| GlitchTip | (create on first access) | - |
| Uptime Kuma | (create on first access) | - |

## Configuration Files

```
monitoring/
├── prometheus.yml           # Prometheus scrape configuration
├── alert.rules.yml          # Alerting rules
├── alertmanager.yml         # Alert routing & notifications
├── loki-config.yaml         # Loki log aggregation config
├── promtail-config.yaml     # Promtail log collection config
├── grafana/
│   ├── provisioning/
│   │   ├── datasources/
│   │   │   └── datasources.yml    # Data source configs
│   │   └── dashboards/
│   │       └── dashboards.yml     # Dashboard provider config
│   └── dashboards/
│       └── cognive-api-overview.json   # Pre-built dashboard
└── README.md                # This file
```

## Metrics Endpoints

The Cognive API exposes Prometheus metrics at `/metrics`:

```bash
curl http://localhost:8000/metrics
```

### Available Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `cognive_http_requests_total` | Counter | Total HTTP requests |
| `cognive_http_request_duration_seconds` | Histogram | Request latency |
| `cognive_http_requests_inprogress` | Gauge | In-flight requests |
| `cognive_agent_runs_total` | Counter | Agent execution count |
| `cognive_agent_run_duration_seconds` | Histogram | Agent run duration |
| `cognive_llm_calls_total` | Counter | LLM API calls |
| `cognive_llm_tokens_total` | Counter | LLM tokens consumed |
| `cognive_cache_hits_total` | Counter | Cache hits |
| `cognive_cache_misses_total` | Counter | Cache misses |
| `cognive_celery_tasks_total` | Counter | Celery task count |

## Alerting

### Alert Categories

1. **API Health**: API down, high error rate, high latency
2. **Database**: Connection pool exhaustion, replication lag
3. **Cache**: Redis down, high miss rate
4. **Message Queue**: RabbitMQ down, queue backlog
5. **Agent Execution**: High failure rate, long-running agents
6. **Cost/Budget**: Budget nearly exhausted, spending spikes
7. **Infrastructure**: High CPU/memory, low disk space

### Configuring Notifications

Edit `alertmanager.yml` to configure notification channels:

```yaml
receivers:
  - name: 'slack-alerts'
    slack_configs:
      - channel: '#alerts'
        api_url: 'https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK'
```

## Error Tracking (GlitchTip)

GlitchTip is a self-hosted, free alternative to Sentry.

### Setup

1. Access GlitchTip at http://localhost:8010
2. Create an organization and project
3. Copy the DSN from project settings
4. Add to your `.env`:

```bash
GLITCHTIP_DSN=http://your-dsn@localhost:8010/1
```

### Python Integration

The Cognive API automatically sends exceptions to GlitchTip when configured.

## Log Aggregation (Loki)

### Querying Logs in Grafana

1. Open Grafana → Explore
2. Select "Loki" datasource
3. Use LogQL queries:

```logql
# All API logs
{service="api"}

# Error logs only
{service="api"} |= "error"

# Logs with specific trace ID
{service="api"} |= "trace_id=abc123"
```

## Uptime Monitoring

### Setup Monitors in Uptime Kuma

1. Access Uptime Kuma at http://localhost:3001
2. Create a new monitor for each service:
   - **API Health**: `http://api:8000/api/v1/health/live`
   - **PostgreSQL**: TCP check on port 5432
   - **Redis**: TCP check on port 6379
   - **RabbitMQ**: `http://rabbitmq:15672`

## Kubernetes Deployment

For K8s deployment, see `k8s/monitoring/`:

```bash
# Deploy all monitoring components
kubectl apply -f k8s/monitoring/prometheus/
kubectl apply -f k8s/monitoring/grafana/
kubectl apply -f k8s/monitoring/alertmanager/
kubectl apply -f k8s/monitoring/loki/
kubectl apply -f k8s/monitoring/promtail/
kubectl apply -f k8s/monitoring/glitchtip/
kubectl apply -f k8s/monitoring/uptime-kuma/
```

## Troubleshooting

### Prometheus not scraping targets

```bash
# Check target status
curl http://localhost:9090/api/v1/targets

# Verify API metrics endpoint
curl http://localhost:8000/metrics
```

### Loki not receiving logs

```bash
# Check Promtail status
docker logs cognive-promtail

# Verify Loki health
curl http://localhost:3100/ready
```

### Grafana dashboard not loading

```bash
# Restart Grafana to reload provisioned dashboards
docker restart cognive-grafana
```

## Environment Variables

Add these to your `.env` file:

```bash
# Monitoring
ENABLE_METRICS=true
APP_VERSION=0.1.0

# Error Tracking
GLITCHTIP_DSN=http://your-dsn@glitchtip:8000/1

# Grafana
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=your-secure-password

# GlitchTip
GLITCHTIP_SECRET_KEY=your-random-secret-key
```

