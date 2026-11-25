import os
import signal
import time

import psycopg
from confluent_kafka import Consumer, KafkaException, Message, TopicPartition
from prometheus_client import Counter, Gauge, start_http_server

from banking.config import dsn
from banking.logging import log
from banking.sink import persist

RECORDS = Counter("banking_cdc_records", "Observed record outcomes", ["outcome"])
FAILURES = Counter("banking_cdc_failures", "Processing failures", ["stage"])
LAG = Gauge("banking_cdc_partition_lag", "Broker high watermark minus committed offset", ["partition"])
READY = Gauge("banking_cdc_ready", "One after successful group assignment")
STOP = False


def stop(*_: object) -> None:
    global STOP
    STOP = True


def write(message: Message) -> str:
    coordinate = (message.topic(), message.partition(), message.offset())
    for attempt in range(4):
        try:
            with psycopg.connect(dsn("target"), autocommit=True) as conn:
                return persist(conn, coordinate, message.key(), message.value())
        except (psycopg.OperationalError, psycopg.errors.SerializationFailure,
                psycopg.errors.DeadlockDetected, psycopg.errors.LockNotAvailable) as error:
            FAILURES.labels("database").inc()
            log("write_retry", coordinate=coordinate, attempt=attempt + 1,
                error_type=type(error).__name__)
            if attempt == 3 or STOP:
                raise
            time.sleep(2**attempt)
    raise AssertionError("retry loop exhausted")


def assign(consumer: Consumer, partitions: list[TopicPartition]) -> None:
    committed = consumer.committed(partitions, timeout=10)
    for partition in committed:
        if partition.error is not None:
            raise KafkaException(partition.error)
        low, high = consumer.get_watermark_offsets(partition, timeout=5)
        if partition.offset < 0 and low == 0:
            partition.offset = 0
        if not low <= partition.offset <= high:
            raise RuntimeError(f"Missing retained history for {partition}")
    consumer.assign(committed)


def run() -> None:
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    start_http_server(9100)
    topic = os.environ.get("CDC_TOPIC", "banking.bank.transactions")
    consumer = Consumer({
        "bootstrap.servers": os.environ.get("KAFKA_BOOTSTRAP", "broker:29092"),
        "group.id": os.environ.get("CDC_GROUP", "banking-sink-v1"),
        "enable.auto.commit": False,
        "enable.auto.offset.store": False,
        "session.timeout.ms": 15000,
        "heartbeat.interval.ms": 3000,
        "auto.offset.reset": "error",
    })
    consumer.subscribe([topic], on_assign=assign)
    try:
        while not STOP:
            message = consumer.poll(1)
            READY.set(int(bool(consumer.assignment())))
            if message is None:
                continue
            if message.error():
                FAILURES.labels("broker").inc()
                raise KafkaException(message.error())
            try:
                outcome = write(message)
            except psycopg.Error as error:
                FAILURES.labels("write").inc()
                log("write_failed", partition=message.partition(), offset=message.offset(),
                    sqlstate=error.sqlstate, error_type=type(error).__name__)
                raise
            try:
                offsets = consumer.commit(message=message, asynchronous=False)
                for offset in offsets:
                    if offset.error is not None:
                        raise KafkaException(offset.error)
            except KafkaException:
                FAILURES.labels("offset_commit").inc()
                raise
            _, high = consumer.get_watermark_offsets(
                TopicPartition(message.topic(), message.partition()), cached=True
            ) or (-1, -1)
            if high >= message.offset() + 1:
                LAG.labels(message.partition()).set(high - message.offset() - 1)
            RECORDS.labels(outcome).inc()
            log("record_committed", outcome=outcome, partition=message.partition(),
                offset=message.offset())
    finally:
        READY.set(0)
        consumer.close()


if __name__ == "__main__":
    run()
