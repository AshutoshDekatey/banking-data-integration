# Setup

Use Docker Desktop with Linux containers and WSL 2 on Windows, or Docker Engine with the Compose v2 plugin on Linux. Work in the WSL filesystem, for example `~/projects`. The [runbook](RUNBOOK.md) includes installation commands and checks.

Copy `.env.example` to `.env` in a new checkout. PostgreSQL and the broker listen only on the Compose network. API, Connect REST, metrics, and optional Airflow ports bind to loopback. Credentials are disposable local values. Avoid publishing Compose configuration output because interpolation can reveal passwords. The source bootstrap role is a PostgreSQL superuser for local logical replication; split application access, replication, and migration roles before deploying elsewhere. Connect REST and the API have no network-facing authentication in this demo.

Optional profiles are `tools` for command containers, `analytics` for dbt, and `orchestration` for Airflow. Explicitly targeting a profiled service activates its profile for the command. dbt and tools use `run --rm` to finish after a job.
