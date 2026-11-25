import json
import os
import time
from urllib.error import HTTPError, URLError
from typing import Any
from urllib.request import Request, urlopen

from confluent_kafka.admin import AdminClient, NewTopic
from confluent_kafka import KafkaError, KafkaException

TOPIC = "banking.bank.transactions"
CONNECT = os.environ.get("CONNECT_URL", "http://connect:8083").rstrip("/")
CONNECTORS = CONNECT + "/connectors"
SOURCE_CONNECTOR = CONNECTORS + "/banking-source"


def request(url: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    req = Request(url, data=None if data is None else json.dumps(data).encode(),
                  headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=15) as response:
        return json.load(response)


def main() -> None:
    admin = AdminClient({"bootstrap.servers": os.environ.get("KAFKA_BOOTSTRAP", "broker:29092")})
    result = admin.create_topics([NewTopic(TOPIC, num_partitions=3, replication_factor=1, config={
        "cleanup.policy": "delete",
        "retention.ms": "604800000",
    })], request_timeout=15)[TOPIC]
    try:
        result.result()
    except KafkaException as error:
        if error.args[0].code() != KafkaError.TOPIC_ALREADY_EXISTS:
            raise

    config = {
        "name": "banking-source",
        "config": {
            "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
            "tasks.max": "1",
            "database.hostname": os.environ.get("SOURCE_HOST", "source"),
            "database.port": os.environ.get("SOURCE_PORT", "5432"),
            "database.user": "bank",
            "database.password": os.environ["SOURCE_PASSWORD"],
            "database.dbname": "source",
            "topic.prefix": "banking",
            "plugin.name": "pgoutput",
            "slot.name": "banking_cdc",
            "publication.name": "banking_cdc",
            "publication.autocreate.mode": "disabled",
            "table.include.list": r"bank\.transactions",
            "snapshot.mode": "initial",
            "tombstones.on.delete": "true",
            "topic.creation.default.replication.factor": "1",
            "topic.creation.default.partitions": "3",
            "topic.creation.default.cleanup.policy": "delete",
            "topic.creation.default.retention.ms": "604800000",
            "key.converter": "org.apache.kafka.connect.json.JsonConverter",
            "key.converter.schemas.enable": "false",
            "value.converter": "org.apache.kafka.connect.json.JsonConverter",
            "value.converter.schemas.enable": "false",
        }
    }
    for _ in range(60):
        try:
            try:
                status = request(SOURCE_CONNECTOR + "/status")
            except HTTPError as error:
                if error.code != 404:
                    raise
                request(CONNECTORS, config)
            else:
                tasks = status.get("tasks", [])
                if status["connector"]["state"] == "RUNNING" and tasks and all(
                    task["state"] == "RUNNING" for task in tasks
                ):
                    print("banking-source connector and task RUNNING")
                    return
                if status["connector"]["state"] == "FAILED" or any(
                    task["state"] == "FAILED" for task in tasks
                ):
                    raise RuntimeError("CDC connector or task failed. Inspect Connect status.")
        except HTTPError as error:
            if error.code not in (409, 502, 503, 504):
                raise
        except (URLError, TimeoutError):
            pass
        time.sleep(2)
    raise TimeoutError("CDC connector did not become ready")


if __name__ == "__main__":
    main()
