from unittest.mock import Mock

import psycopg
import pytest

from banking import consumer


@pytest.mark.parametrize("write_succeeds", [True, False])
def test_offsets_follow_durable_write(monkeypatch, write_succeeds: bool) -> None:
    order = []
    kafka = Mock()
    message = Mock()
    message.error.return_value = None
    message.topic.return_value = "fixture"
    message.partition.return_value = 0
    message.offset.return_value = 0
    kafka.poll.return_value = message
    kafka.commit.return_value = []
    kafka.get_watermark_offsets.return_value = None

    def write(record):
        order.append("write")
        if not write_succeeds:
            raise psycopg.OperationalError("database unavailable")
        monkeypatch.setattr(consumer, "STOP", True)
        return "applied"

    kafka.commit.side_effect = lambda **_: order.append("offset") or []
    monkeypatch.setattr(consumer, "Consumer", lambda _: kafka)
    monkeypatch.setattr(consumer, "write", write)
    monkeypatch.setattr(consumer, "start_http_server", lambda _: None)
    monkeypatch.setattr(consumer.signal, "signal", lambda *_: None)
    if write_succeeds:
        consumer.run()
        assert order == ["write", "offset"]
        kafka.commit.assert_called_once_with(message=message, asynchronous=False)
    else:
        with pytest.raises(psycopg.OperationalError):
            consumer.run()
        assert order == ["write"]
        kafka.commit.assert_not_called()
    kafka.close.assert_called_once()


def test_transient_write_retry(monkeypatch) -> None:
    connect = Mock(side_effect=[psycopg.OperationalError("offline"), Mock()])
    connect.side_effect = [psycopg.OperationalError("offline"), connect.return_value]
    connect.return_value.__enter__ = Mock(return_value=Mock())
    connect.return_value.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(consumer.psycopg, "connect", connect)
    monkeypatch.setattr(consumer, "dsn", lambda _: "")
    monkeypatch.setattr(consumer, "persist", lambda *_: "applied")
    monkeypatch.setattr(consumer.time, "sleep", lambda _: None)
    assert consumer.write(Mock()) == "applied"
    assert connect.call_count == 2


@pytest.mark.parametrize(("offset", "watermarks", "expected"), [
    (-1001, (0, 10), 0),
    (4, (2, 10), 4),
    (-1001, (2, 10), None),
    (1, (2, 10), None),
    (11, (2, 10), None),
])
def test_assignment_guards_retained_history(offset, watermarks, expected) -> None:
    partition = consumer.TopicPartition("fixture", 0, offset)
    kafka = Mock()
    kafka.committed.return_value = [partition]
    kafka.get_watermark_offsets.return_value = watermarks
    if expected is None:
        with pytest.raises(RuntimeError, match="Missing retained history"):
            consumer.assign(kafka, [partition])
        kafka.assign.assert_not_called()
    else:
        consumer.assign(kafka, [partition])
        assert kafka.assign.call_args.args[0][0].offset == expected
