from blastfx.core.bake_queue import BakeQueue


def test_enqueue_deduplicates_and_rejects_empty():
    queue = BakeQueue()
    assert queue.enqueue("a1") is True
    assert queue.enqueue("a1") is False
    assert queue.enqueue("") is False
    assert len(queue) == 1


def test_dequeue_is_fifo_and_empties():
    queue = BakeQueue()
    queue.enqueue("a1")
    queue.enqueue("b2")
    assert queue.dequeue() == "a1"
    assert queue.dequeue() == "b2"
    assert queue.dequeue() is None


def test_clear_reports_count_and_empties():
    queue = BakeQueue()
    queue.enqueue("a1")
    queue.enqueue("b2")
    assert queue.clear() == 2
    assert len(queue) == 0
    assert queue.clear() == 0


def test_position_is_one_based():
    queue = BakeQueue()
    queue.enqueue("a1")
    queue.enqueue("b2")
    assert queue.position("a1") == 1
    assert queue.position("b2") == 2
    assert queue.position("zz") is None


def test_pending_is_an_immutable_snapshot():
    queue = BakeQueue()
    queue.enqueue("a1")
    pending = queue.pending()
    queue.enqueue("b2")
    assert pending == ("a1",)
    assert queue.pending() == ("a1", "b2")
