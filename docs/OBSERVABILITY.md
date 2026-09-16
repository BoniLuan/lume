# Observability

Lume reuses the VPS shared Prometheus and Grafana deployment. The API joins only
the external `vigil-monitoring` network under the unique alias
`lume-api-metrics`; it exposes port 8000 inside Docker and publishes no host port.
Prometheus scrapes `http://lume-api-metrics:8000/metrics` every 30 seconds.

The public gateway and shared edge return 404 for `/metrics`, `/readyz`, and
internal paths. Application logs are structured JSON and omit request bodies,
authentication values, and financial fields. Compose bounds each container's
`json-file` logs.

Alert rules in `deploy/monitoring/alerts.yml` cover target failure, missing scrape
configuration, and repeated 5xx responses. The scrape fragment is stored in
`deploy/monitoring/scrape.json`, which is valid Prometheus YAML as well as JSON.

## Prepare and validate

The current VPS first applies Relay's monitoring override to Vigil's base
configuration. Generate Lume's ignored integrated configuration from that active
Relay/Vigil snapshot:

```bash
make monitoring-prepare
docker run --rm --network none \
  -v "$PWD/.local/prometheus.integrated.yml:/etc/prometheus/prometheus.yml:ro" \
  -v /home/luan/projects/relay/deploy/monitoring:/etc/prometheus/relay:ro \
  -v "$PWD/deploy/monitoring:/etc/prometheus/lume:ro" \
  --entrypoint /bin/promtool prom/prometheus:v3.14.0 \
  check config /etc/prometheus/prometheus.yml
```

The generator preserves all existing jobs, rules, and Alertmanager settings,
records a source checksum, and refuses a duplicate `lume-api` job. Regenerate and
review it whenever the Vigil or Relay configuration changes.

## Activate

Apply Lume's override last so its root config mount supersedes the earlier root
mount while Compose retains both projects' rule mounts:

```bash
docker compose --env-file /home/luan/.config/vigil/observability.env \
  -f /home/luan/projects/vigil/deploy/observability/compose.yaml \
  -f /home/luan/projects/relay/deploy/monitoring/shared.override.yaml \
  -f /home/luan/projects/lume/deploy/monitoring/shared.override.yaml \
  config --quiet

docker compose --env-file /home/luan/.config/vigil/observability.env \
  -f /home/luan/projects/vigil/deploy/observability/compose.yaml \
  -f /home/luan/projects/relay/deploy/monitoring/shared.override.yaml \
  -f /home/luan/projects/lume/deploy/monitoring/shared.override.yaml \
  up -d --no-deps --force-recreate prometheus
```

Only Prometheus is recreated; `vigil-prometheus-data` remains mounted. Verify all
six targets are up and all Lume rules report healthy. Preserve the three-layer
Compose command on later observability deployments. Never route metrics through
`web-proxy`.
