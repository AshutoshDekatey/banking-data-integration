# Costs

Cloud-service target is $0. Docker pulls images and runs all infrastructure on your machine. GitHub Actions usage follows the repository owner's GitHub plan.

| Mode | Suggested host RAM | Docker CPU | Free disk |
| --- | --- | --- | --- |
| Core CDC and occasional dbt | 8 GB | 2–4 cores | 8 GB |
| Core plus Airflow | 16 GB | 4 cores | 15 GB |

These are planning estimates. Docker Desktop, WSL, image caches, PostgreSQL WAL and retained Kafka data affect actual usage. Inspect `docker stats --no-stream` and `docker system df`. A stalled logical slot retains source WAL. Monitor slot backlog during outages.
