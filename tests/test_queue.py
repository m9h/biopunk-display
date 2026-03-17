"""Tests for the priority message queue (app/display/queue.py).

These tests exercise QueuedMessage ordering and MessageQueue logic
without requiring Flask, a database, or any display hardware.
"""

import time
from unittest.mock import MagicMock

import pytest

from app.display.queue import MessageQueue, QueuedMessage


# ---------------------------------------------------------------------------
# 1. QueuedMessage dataclass ordering — higher priority sorts first
# ---------------------------------------------------------------------------

class TestQueuedMessageOrdering:
    """QueuedMessage uses sort_key=(-priority, seq) so higher priority
    (larger number) produces a smaller negated value, sorting first."""

    def test_higher_priority_sorts_before_lower(self):
        low = QueuedMessage(sort_key=(-1, 1), body="low")
        high = QueuedMessage(sort_key=(-5, 2), body="high")
        assert high < low, "priority-5 message should sort before priority-1"

    def test_equal_priority_sorted_by_sequence(self):
        first = QueuedMessage(sort_key=(-3, 1), body="first")
        second = QueuedMessage(sort_key=(-3, 2), body="second")
        assert first < second, "same priority: lower sequence number sorts first"

    def test_sorted_list_respects_priority(self):
        msgs = [
            QueuedMessage(sort_key=(-1, 1), body="p1"),
            QueuedMessage(sort_key=(-5, 2), body="p5"),
            QueuedMessage(sort_key=(-3, 3), body="p3"),
        ]
        ordered = sorted(msgs)
        assert [m.body for m in ordered] == ["p5", "p3", "p1"]

    def test_sorted_list_fifo_within_same_priority(self):
        msgs = [
            QueuedMessage(sort_key=(-2, 3), body="third"),
            QueuedMessage(sort_key=(-2, 1), body="first"),
            QueuedMessage(sort_key=(-2, 2), body="second"),
        ]
        ordered = sorted(msgs)
        assert [m.body for m in ordered] == ["first", "second", "third"]


# ---------------------------------------------------------------------------
# 2. QueuedMessage FIFO ordering — same priority, insertion order via seq
# ---------------------------------------------------------------------------

class TestQueuedMessageFIFO:
    """When priority is identical, the sequence number breaks ties."""

    def test_fifo_two_messages(self):
        a = QueuedMessage(sort_key=(-1, 10), body="a")
        b = QueuedMessage(sort_key=(-1, 20), body="b")
        assert a < b

    def test_fifo_many_messages(self):
        items = [QueuedMessage(sort_key=(0, i), body=f"msg-{i}") for i in range(100)]
        shuffled = items[50:] + items[:50]
        assert sorted(shuffled) == items


# ---------------------------------------------------------------------------
# 3. MessageQueue.enqueue — messages are added to the queue
# ---------------------------------------------------------------------------

class TestMessageQueueEnqueue:

    def test_enqueue_adds_one_message(self):
        mq = MessageQueue()
        mq.enqueue("hello")
        assert mq.pending == 1

    def test_enqueue_adds_multiple_messages(self):
        mq = MessageQueue()
        mq.enqueue("a")
        mq.enqueue("b")
        mq.enqueue("c")
        assert mq.pending == 3

    def test_enqueue_sets_body(self):
        mq = MessageQueue()
        mq.enqueue("test body")
        item = mq._queue.get_nowait()
        assert item.body == "test body"

    def test_enqueue_sets_transition(self):
        mq = MessageQueue()
        mq.enqueue("x", transition="pop")
        item = mq._queue.get_nowait()
        assert item.transition == "pop"

    def test_enqueue_default_transition(self):
        mq = MessageQueue()
        mq.enqueue("x")
        item = mq._queue.get_nowait()
        assert item.transition == "righttoleft"

    def test_enqueue_sets_message_id(self):
        mq = MessageQueue()
        mq.enqueue("x", message_id=42)
        item = mq._queue.get_nowait()
        assert item.message_id == 42

    def test_enqueue_increments_sequence(self):
        mq = MessageQueue()
        mq.enqueue("a", priority=0)
        mq.enqueue("b", priority=0)
        item_a = mq._queue.get_nowait()
        item_b = mq._queue.get_nowait()
        assert item_a.sort_key[1] < item_b.sort_key[1]

    def test_enqueue_negates_priority(self):
        mq = MessageQueue()
        mq.enqueue("x", priority=7)
        item = mq._queue.get_nowait()
        assert item.sort_key[0] == -7


# ---------------------------------------------------------------------------
# 4. MessageQueue.pending — returns correct queue size
# ---------------------------------------------------------------------------

class TestMessageQueuePending:

    def test_pending_empty_queue(self):
        mq = MessageQueue()
        assert mq.pending == 0

    def test_pending_after_enqueue(self):
        mq = MessageQueue()
        for i in range(5):
            mq.enqueue(f"msg-{i}")
        assert mq.pending == 5

    def test_pending_decreases_after_get(self):
        mq = MessageQueue()
        mq.enqueue("a")
        mq.enqueue("b")
        mq._queue.get_nowait()
        assert mq.pending == 1


# ---------------------------------------------------------------------------
# 5. MessageQueue.stop — sentinel message stops the worker
# ---------------------------------------------------------------------------

class TestMessageQueueStop:

    def test_stop_puts_sentinel(self):
        mq = MessageQueue()
        mq.stop()
        item = mq._queue.get_nowait()
        assert item.sort_key == (999, 999)

    def test_stop_sets_running_false(self):
        mq = MessageQueue()
        mq._running = True
        mq.stop()
        assert mq._running is False

    def test_stop_terminates_worker_thread(self):
        mock_display = MagicMock()
        mq = MessageQueue()
        mq._display = mock_display
        mq.start()
        assert mq._worker.is_alive()
        mq.stop()
        mq._worker.join(timeout=3)
        assert not mq._worker.is_alive()

    def test_stop_idempotent_no_worker(self):
        mq = MessageQueue()
        mq.stop()  # should not raise


# ---------------------------------------------------------------------------
# 6. Queue priority behavior — priority=5 dequeued before priority=1
# ---------------------------------------------------------------------------

class TestQueuePriorityBehavior:

    def test_priority_5_before_priority_1(self):
        mq = MessageQueue()
        mq.enqueue("low", priority=1)
        mq.enqueue("high", priority=5)
        first = mq._queue.get_nowait()
        second = mq._queue.get_nowait()
        assert first.body == "high"
        assert second.body == "low"

    def test_priority_ordering_multiple_levels(self):
        mq = MessageQueue()
        mq.enqueue("p0", priority=0)
        mq.enqueue("p10", priority=10)
        mq.enqueue("p3", priority=3)
        mq.enqueue("p7", priority=7)
        mq.enqueue("p1", priority=1)

        dequeued = []
        while mq.pending > 0:
            dequeued.append(mq._queue.get_nowait().body)
        assert dequeued == ["p10", "p7", "p3", "p1", "p0"]

    def test_same_priority_fifo_via_enqueue(self):
        mq = MessageQueue()
        mq.enqueue("first", priority=2)
        mq.enqueue("second", priority=2)
        mq.enqueue("third", priority=2)
        dequeued = []
        while mq.pending > 0:
            dequeued.append(mq._queue.get_nowait().body)
        assert dequeued == ["first", "second", "third"]

    def test_mixed_priority_and_fifo(self):
        mq = MessageQueue()
        mq.enqueue("low-1", priority=1)
        mq.enqueue("low-2", priority=1)
        mq.enqueue("high-1", priority=5)
        mq.enqueue("high-2", priority=5)
        mq.enqueue("mid-1", priority=3)

        dequeued = []
        while mq.pending > 0:
            dequeued.append(mq._queue.get_nowait().body)
        assert dequeued == ["high-1", "high-2", "mid-1", "low-1", "low-2"]

    def test_worker_plays_in_priority_order(self):
        played = []
        mock_display = MagicMock()
        mock_display.send_message.side_effect = lambda body, trans: played.append(body)

        mq = MessageQueue()
        mq._display = mock_display

        mq.enqueue("low", priority=1)
        mq.enqueue("high", priority=5)
        mq.enqueue("mid", priority=3)

        mq.start()
        deadline = time.monotonic() + 3.0
        while mq.pending > 0 and time.monotonic() < deadline:
            time.sleep(0.05)
        mq.stop()

        assert played == ["high", "mid", "low"]
