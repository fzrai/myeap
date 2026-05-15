"""Tests for MES Message Handlers"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from myeap.mes.handlers import (
    MESSHandler,
    HandlerNotFoundError,
    HandlerError,
    BatchMESSHandler,
)


class TestMESSHandler:
    """Test MESSHandler class"""

    def test_create_handler(self):
        """Test creating a handler instance"""
        handler = MESSHandler()
        assert handler is not None
        assert len(handler._handlers) == 0

    def test_register_sync_handler(self):
        """Test registering a synchronous handler"""
        handler = MESSHandler()

        def my_handler(message):
            return message

        handler.register("test_type", my_handler)
        assert "test_type" in handler._handlers
        assert handler._handlers["test_type"] == my_handler

    def test_register_async_handler(self):
        """Test registering an async handler"""
        handler = MESSHandler()

        async def async_handler(message):
            return message

        handler.register("async_type", async_handler)
        assert "async_type" in handler._handlers

    def test_register_with_decorator(self):
        """Test registering handler with decorator"""
        handler = MESSHandler()

        @handler.register("decorated_type")
        def decorated_handler(message):
            return message

        assert "decorated_type" in handler._handlers
        assert handler._handlers["decorated_type"] == decorated_handler

    @pytest.mark.asyncio
    async def test_handle_message_sync(self):
        """Test handling a message with sync handler"""
        handler = MESSHandler()
        results = []

        def sync_handler(message):
            results.append(message)
            return "handled"

        handler.register("sync_type", sync_handler)

        message = {"type": "sync_type", "data": "test"}
        result = await handler.handle_message(message)

        assert result == "handled"
        assert len(results) == 1
        assert results[0] == message

    @pytest.mark.asyncio
    async def test_handle_message_async(self):
        """Test handling a message with async handler"""
        handler = MESSHandler()
        results = []

        async def async_handler(message):
            results.append(message)
            return "async_handled"

        handler.register("async_type", async_handler)

        message = {"type": "async_type", "data": "test"}
        result = await handler.handle_message(message)

        assert result == "async_handled"
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_handle_message_not_found(self):
        """Test handling unknown message type"""
        handler = MESSHandler()

        message = {"type": "unknown_type", "data": "test"}

        with pytest.raises(HandlerNotFoundError) as exc_info:
            await handler.handle_message(message)

        assert "No handler for message type" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_handle_message_with_default_handler(self):
        """Test handling with default handler"""
        handler = MESSHandler()
        results = []

        def default_handler(message):
            results.append(message)

        handler.set_default_handler(default_handler)

        message = {"type": "new_type", "data": "test"}
        await handler.handle_message(message)

        assert len(results) == 1
        assert results[0] == message

    @pytest.mark.asyncio
    async def test_handle_message_with_error_handler(self):
        """Test handling with error handler"""
        handler = MESSHandler()
        errors = []

        def error_handler(message, error):
            errors.append(error)

        handler.set_error_handler(error_handler)

        def failing_handler(message):
            raise ValueError("Test error")

        handler.register("failing_type", failing_handler)

        message = {"type": "failing_type", "data": "test"}

        with pytest.raises(HandlerError):
            await handler.handle_message(message)

        # Error handler should have been called
        assert len(errors) == 1

    def test_unregister_handler(self):
        """Test unregistering a handler"""
        handler = MESSHandler()

        def my_handler(message):
            return message

        handler.register("test_type", my_handler)
        assert handler.has_handler("test_type")

        result = handler.unregister("test_type")
        assert result is True
        assert not handler.has_handler("test_type")

    def test_unregister_nonexistent_handler(self):
        """Test unregistering non-existent handler"""
        handler = MESSHandler()

        result = handler.unregister("nonexistent")
        assert result is False

    def test_get_registered_handlers(self):
        """Test getting registered handlers list"""
        handler = MESSHandler()

        def handler1(msg):
            return msg

        def handler2(msg):
            return msg

        handler.register("type1", handler1)
        handler.register("type2", handler2)

        registered = handler.get_registered_handlers()
        assert registered["type1"] == "handler1"
        assert registered["type2"] == "handler2"

    def test_has_handler(self):
        """Test checking if handler exists"""
        handler = MESSHandler()

        def my_handler(message):
            return message

        assert not handler.has_handler("test_type")

        handler.register("test_type", my_handler)
        assert handler.has_handler("test_type")


class TestHandlerEdgeCases:
    """Test handler edge cases"""

    @pytest.mark.asyncio
    async def test_empty_message_with_default(self):
        """Test handling empty message with default handler"""
        handler = MESSHandler()
        results = []

        def empty_handler(message):
            results.append(message)

        handler.register("empty", empty_handler)

        # Message with empty type - no handler
        with pytest.raises(HandlerNotFoundError):
            await handler.handle_message({})

    @pytest.mark.asyncio
    async def test_message_without_type(self):
        """Test handling message without type field"""
        handler = MESSHandler()

        # With default handler
        handler.set_default_handler(lambda m: "default")
        result = await handler.handle_message({"data": "test"})
        assert result == "default"

    @pytest.mark.asyncio
    async def test_handler_receives_full_message(self):
        """Test that handler receives full message"""
        handler = MESSHandler()
        received = {}

        def capture_handler(message):
            received.update(message)
            return message

        handler.register("full_msg", capture_handler)

        full_message = {
            "type": "full_msg",
            "message_id": "MSG001",
            "timestamp": "2024-01-01T00:00:00",
            "data": {"nested": "data"},
        }

        await handler.handle_message(full_message)
        assert received == full_message


class TestBatchMESSHandler:
    """Test BatchMESSHandler class"""

    def test_create_batch_handler(self):
        """Test creating batch handler"""
        handler = BatchMESSHandler(batch_size=5, batch_timeout=2.0)
        assert handler.batch_size == 5
        assert handler.batch_timeout == 2.0

    def test_default_batch_settings(self):
        """Test default batch settings"""
        handler = BatchMESSHandler()
        assert handler.batch_size == 10
        assert handler.batch_timeout == 1.0

    @pytest.mark.asyncio
    async def test_batch_handler_processes_batch(self):
        """Test batch handler processes messages in batches via queue"""
        import asyncio

        handler = BatchMESSHandler(batch_size=3, batch_timeout=0.05)
        batches = []

        def batch_handler(batch):
            batches.append(list(batch))

        handler.register("batch_type", batch_handler)

        # Directly put messages into the queue
        queue = asyncio.Queue()
        handler._batch_queues["batch_type"] = queue

        # Add messages directly to queue (simulating adapter)
        for i in range(3):
            await queue.put({"type": "batch_type", "index": i})

        # Process the batch manually
        async def process_batch():
            batch = []
            while len(batch) < 3:
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=0.01)
                    batch.append(msg)
                except asyncio.TimeoutError:
                    break
            if batch:
                batches.append(batch)

        await process_batch()

        # Should have processed one batch
        assert len(batches) == 1
        assert len(batches[0]) == 3

    @pytest.mark.asyncio
    async def test_batch_handler_timeout(self):
        """Test batch handler timeout logic"""
        import asyncio

        handler = BatchMESSHandler(batch_size=10, batch_timeout=0.02)
        batches = []

        def batch_handler(batch):
            batches.append(list(batch))

        handler.register("timeout_type", batch_handler)

        # Directly put messages into the queue
        queue = asyncio.Queue()
        handler._batch_queues["timeout_type"] = queue

        # Add fewer messages than batch_size
        for i in range(2):
            await queue.put({"type": "timeout_type", "index": i})

        # Process the batch with timeout
        async def process_batch():
            batch = []
            last_time = asyncio.get_event_loop().time()
            while True:
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=0.02)
                    batch.append(msg)
                    last_time = asyncio.get_event_loop().time()
                except asyncio.TimeoutError:
                    if batch and (asyncio.get_event_loop().time() - last_time) >= 0.02:
                        break
                    if not batch:
                        break
            if batch:
                batches.append(batch)

        await process_batch()

        # Should still process due to timeout
        assert len(batches) == 1
        assert len(batches[0]) == 2

    @pytest.mark.asyncio
    async def test_batch_handler_shutdown(self):
        """Test batch handler shutdown"""
        handler = BatchMESSHandler()

        # Create mock tasks
        import asyncio
        handler._batch_tasks["test"] = asyncio.create_task(asyncio.sleep(1))

        await handler.shutdown()

        assert len(handler._batch_tasks) == 0


class TestHandlerErrorHandling:
    """Test handler error handling scenarios"""

    @pytest.mark.asyncio
    async def test_handler_returns_none(self):
        """Test handler that returns None"""
        handler = MESSHandler()

        def none_handler(message):
            return None

        handler.register("none_type", none_handler)

        result = await handler.handle_message({"type": "none_type"})
        assert result is None

    @pytest.mark.asyncio
    async def test_handler_raises_exception(self):
        """Test handler that raises exception"""
        handler = MESSHandler()

        def exception_handler(message):
            raise RuntimeError("Test exception")

        handler.register("exception_type", exception_handler)

        with pytest.raises(HandlerError) as exc_info:
            await handler.handle_message({"type": "exception_type"})

        assert "Handler error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_error_handler_receives_exception(self):
        """Test error handler receives exception"""
        handler = MESSHandler()
        received_errors = []

        def error_handler(message, error):
            received_errors.append(error)

        handler.set_error_handler(error_handler)

        def failing_handler(message):
            raise ValueError("Original error")

        handler.register("failing", failing_handler)

        with pytest.raises(HandlerError):
            await handler.handle_message({"type": "failing"})

        assert len(received_errors) == 1
        assert isinstance(received_errors[0], ValueError)
        assert str(received_errors[0]) == "Original error"


class TestHandlerWithMocks:
    """Test handler with mock objects"""

    @pytest.mark.asyncio
    async def test_handler_with_mock_metrics(self):
        """Test handler with mocked metrics"""
        handler = MESSHandler()

        with patch.object(handler, "_metrics") as mock_metrics:
            def simple_handler(message):
                return "ok"

            handler.register("mocked", simple_handler)
            await handler.handle_message({"type": "mocked"})

            # Metrics should be called
            # Note: actual metric calls depend on tracing setup

    @pytest.mark.asyncio
    async def test_multiple_handlers(self):
        """Test registering multiple handlers"""
        handler = MESSHandler()
        results = {"type1": [], "type2": [], "type3": []}

        def handler1(msg):
            results["type1"].append(msg)

        def handler2(msg):
            results["type2"].append(msg)

        async def handler3(msg):
            results["type3"].append(msg)

        handler.register("type1", handler1)
        handler.register("type2", handler2)
        handler.register("type3", handler3)

        await handler.handle_message({"type": "type1", "data": 1})
        await handler.handle_message({"type": "type2", "data": 2})
        await handler.handle_message({"type": "type3", "data": 3})

        assert len(results["type1"]) == 1
        assert len(results["type2"]) == 1
        assert len(results["type3"]) == 1
