from unittest.mock import Mock
from urllib.error import HTTPError

from banking import bootstrap


def test_bootstrap_registers_precreated_cdc_topic(monkeypatch) -> None:
    admin = Mock()

    def create_topics(topics, **_):
        topic, = topics
        assert topic.topic == bootstrap.TOPIC
        assert topic.num_partitions == 3
        assert topic.replication_factor == 1
        assert topic.replica_assignment is None
        assert topic.config == {"cleanup.policy": "delete", "retention.ms": "604800000"}
        return {topic.topic: Mock()}

    admin.create_topics.side_effect = create_topics
    monkeypatch.setattr(bootstrap, "AdminClient", lambda _: admin)
    monkeypatch.setenv("SOURCE_PASSWORD", "synthetic")
    request = Mock(side_effect=[
        HTTPError(bootstrap.SOURCE_CONNECTOR, 404, "missing", None, None),
        {},
        {"connector": {"state": "RUNNING"}, "tasks": [{"state": "RUNNING"}]},
    ])
    monkeypatch.setattr(bootstrap, "request", request)
    monkeypatch.setattr(bootstrap.time, "sleep", lambda _: None)
    bootstrap.main()
    admin.create_topics.assert_called_once()
    url, payload = request.call_args_list[1].args
    assert url == bootstrap.CONNECTORS
    assert payload["config"]["topic.creation.default.replication.factor"] == "1"
    assert payload["config"]["table.include.list"] == r"bank\.transactions"
