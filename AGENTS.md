# Repository instructions

- Use synthetic data. Keep source and target database changes separate and use integer minor units for amounts.
- Preserve the source transaction ID and monotonic version contract. Document schema and CDC compatibility changes.
- Keep Kafka acknowledgments after the target transaction commits. Cover offset, replay, or sink changes with regression tests.
- Run `python -m pytest -q` and `bash -n scripts/integration.sh`. Run the integration script where Docker is available and record actual results.
- Keep Airflow and dbt on demand. Publish user-facing behavior changes in the changelog and version documentation.
