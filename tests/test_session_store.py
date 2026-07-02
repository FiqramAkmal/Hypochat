from hypochat.storage.session_store import enqueue_pending_outgoing, get_pending_outgoing, pop_pending_outgoing


def test_pending_outgoing_queue_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setenv(XDG_DATA_HOME, str(tmp_path))
    monkeypatch.setenv(HYPOCHAT_PASSWORD, test-pass)
    enqueue_pending_outgoing(peer-1, msg-1)
    enqueue_pending_outgoing(peer-1, msg-2)
    assert get_pending_outgoing(peer-1) == [msg-1, msg-2]
    assert pop_pending_outgoing(peer-1) == [msg-1, msg-2]
    assert get_pending_outgoing(peer-1) == []
