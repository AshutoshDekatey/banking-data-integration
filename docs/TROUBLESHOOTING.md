# Troubleshooting

| Symptom | Checks and recovery |
| --- | --- |
| Docker daemon unavailable | Start Docker Desktop, switch to Linux containers, and enable WSL integration for your distro. Run `docker info` inside WSL. |
| Port already used | Stop the first copy before starting integration. Local ports are 8000, 8083, 9100, and optionally 8080. |
| Source schema missing | Inspect `docker compose logs source`. Init SQL runs once per fresh volume. For a disposable demo use only the scoped reset in the runbook. |
| Connector task FAILED | Inspect `curl -fsS localhost:8083/connectors/banking-source/status` and `docker compose logs connect`. Resolve credentials, publication, slot or broker issues before restarting failed tasks. |
| Target database unavailable | Check `docker compose ps` and target logs. Resume target service and check consumer logs and offsets. |
| Consumer checkpoint outside retention | Preserve broker and target evidence, inspect group offsets and slot health, and plan a source-backed recovery. An arbitrary offset reset can lose changes. |
| Generator reports HTTP 409 | IDs derive from seed and index. Use a new seed for another create run. Mutate the original seed once after successful creation. |
| Reconciliation shows mismatches | Pause writes and let CDC catch up. Check quarantine and group lag, then retry. Use backfill only for missing or older active rows. |
| Airflow has no runs | Start with the orchestration profile, unpause the DAG, trigger it, and inspect task logs. |
