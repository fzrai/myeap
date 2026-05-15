"""Tests for MES Adapters"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass

from myeap.mes.adapters.base import MESAdapter, MESConfig
from myeap.mes.adapters.mqtt import MqttAdapter
from myeap.mes.adapters.rest import RestAdapter
from myeap.mes.adapters.kafka import KafkaAdapter


class TestMESConfig:
    """Test MESConfig dataclass"""

    def test_create_mqtt_config(self):
        """Test creating MQTT config"""
        config = MESConfig(
            adapter_type="mqtt",
            host="localhost",
            port=1883,
            username="user",
            password="pass",
            topic_prefix="mes/eap",
        )

        assert config.adapter_type == "mqtt"
        assert config.host == "localhost"
        assert config.port == 1883
        assert config.username == "user"
        assert config.topic_prefix == "mes/eap"

    def test_create_rest_config(self):
        """Test creating REST config"""
        config = MESConfig(
            adapter_type="rest",
            host="localhost",
            port=8001,
            base_url="http://localhost:8001/api",
        )

        assert config.adapter_type == "rest"
        assert config.base_url == "http://localhost:8001/api"

    def test_create_kafka_config(self):
        """Test creating Kafka config"""
        config = MESConfig(
            adapter_type="kafka",
            bootstrap_servers="localhost:9092",
            consumer_group="myeap-group",
            client_id="myeap",
        )

        assert config.adapter_type == "kafka"
        assert config.bootstrap_servers == "localhost:9092"
        assert config.consumer_group == "myeap-group"

    def test_config_defaults(self):
        """Test config default values"""
        config = MESConfig(
            adapter_type="mqtt",
        )

        assert config.host == "localhost"
        assert config.port == 1883
        assert config.username is None
        assert config.password is None
        assert config.topic_prefix == "mes/eap"
        assert config.client_id == "myeap"
        assert config.keepalive == 60
        assert config.tls_enabled is False


class TestMESAdapterBase:
    """Test MESAdapter base class"""

    def test_adapter_initialization(self):
        """Test adapter initialization"""
        config = MESConfig(
            adapter_type="mqtt",
            host="localhost",
            port=1883,
        )

        # Create a concrete adapter for testing
        class TestAdapter(MESAdapter):
            async def connect(self):
                self._connected = True

            async def disconnect(self):
                self._connected = False

            async def send(self, topic, message):
                pass

            async def subscribe(self, topic, handler):
                pass

            async def unsubscribe(self, topic):
                pass

        adapter = TestAdapter(config)

        assert adapter.config == config
        assert adapter.is_connected is False

    def test_adapter_connection_status(self):
        """Test adapter connection status property"""

        class TestAdapter(MESAdapter):
            async def connect(self):
                self._connected = True

            async def disconnect(self):
                self._connected = False

            async def send(self, topic, message):
                pass

            async def subscribe(self, topic, handler):
                pass

            async def unsubscribe(self, topic):
                pass

        config = MESConfig(adapter_type="mqtt", host="localhost", port=1883)
        adapter = TestAdapter(config)

        assert adapter.is_connected is False


class TestMQTTAdapter:
    """Test MqttAdapter class"""

    def test_create_mqtt_adapter(self):
        """Test creating MQTT adapter"""
        config = MESConfig(
            adapter_type="mqtt",
            host="localhost",
            port=1883,
        )

        adapter = MqttAdapter(config)
        assert adapter.config == config
        assert adapter._client is None
        assert adapter._connected is False

    @pytest.mark.asyncio
    async def test_mqtt_adapter_connect(self):
        """Test MQTT adapter connect"""
        config = MESConfig(
            adapter_type="mqtt",
            host="localhost",
            port=1883,
        )

        adapter = MqttAdapter(config)

        # Mock the aiomqtt.Client
        mock_client_instance = MagicMock()
        mock_client_instance.connect = AsyncMock()
        mock_client_instance.disconnect = AsyncMock()

        with patch("myeap.mes.adapters.mqtt.aiomqtt.Client", return_value=mock_client_instance):
            await adapter.connect()

            mock_client_instance.connect.assert_called_once()
            assert adapter._connected is True

    @pytest.mark.asyncio
    async def test_mqtt_adapter_disconnect(self):
        """Test MQTT adapter disconnect"""
        config = MESConfig(
            adapter_type="mqtt",
            host="localhost",
            port=1883,
        )

        adapter = MqttAdapter(config)

        mock_client_instance = MagicMock()
        mock_client_instance.connect = AsyncMock()
        mock_client_instance.disconnect = AsyncMock()

        with patch("myeap.mes.adapters.mqtt.aiomqtt.Client", return_value=mock_client_instance):
            await adapter.connect()
            assert adapter._connected is True

            await adapter.disconnect()
            mock_client_instance.disconnect.assert_called_once()
            assert adapter._connected is False

    @pytest.mark.asyncio
    async def test_mqtt_adapter_send(self):
        """Test MQTT adapter send"""
        config = MESConfig(
            adapter_type="mqtt",
            host="localhost",
            port=1883,
            topic_prefix="mes/eap",
        )

        adapter = MqttAdapter(config)

        mock_client_instance = MagicMock()
        mock_client_instance.connect = AsyncMock()
        mock_client_instance.publish = AsyncMock()

        with patch("myeap.mes.adapters.mqtt.aiomqtt.Client", return_value=mock_client_instance):
            await adapter.connect()

            message = {"type": "test", "data": "hello"}
            await adapter.send("test_topic", message)

            # Verify publish was called
            assert mock_client_instance.publish.called

    @pytest.mark.asyncio
    async def test_mqtt_adapter_send_not_connected(self):
        """Test MQTT send raises when not connected"""
        config = MESConfig(
            adapter_type="mqtt",
            host="localhost",
            port=1883,
        )

        adapter = MqttAdapter(config)

        with pytest.raises(RuntimeError, match="Not connected"):
            await adapter.send("test", {"data": "test"})

    @pytest.mark.asyncio
    async def test_mqtt_adapter_context_manager(self):
        """Test MQTT adapter as context manager"""
        config = MESConfig(
            adapter_type="mqtt",
            host="localhost",
            port=1883,
        )

        mock_client_instance = MagicMock()
        mock_client_instance.connect = AsyncMock()
        mock_client_instance.disconnect = AsyncMock()

        with patch("myeap.mes.adapters.mqtt.aiomqtt.Client", return_value=mock_client_instance):
            async with MqttAdapter(config) as adapter:
                assert adapter._connected is True

            mock_client_instance.disconnect.assert_called_once()


class TestRESTAdapter:
    """Test RestAdapter class"""

    def test_create_rest_adapter(self):
        """Test creating REST adapter"""
        config = MESConfig(
            adapter_type="rest",
            host="localhost",
            port=8001,
            base_url="http://localhost:8001/api",
        )

        adapter = RestAdapter(config)
        assert adapter.config == config
        assert adapter._session is None

    @pytest.mark.asyncio
    async def test_rest_adapter_connect(self):
        """Test REST adapter connect"""
        config = MESConfig(
            adapter_type="rest",
            host="localhost",
            port=8001,
        )

        adapter = RestAdapter(config)

        mock_response = MagicMock()
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock()

        mock_session = MagicMock()
        mock_session.request = MagicMock(return_value=mock_response)
        mock_session.close = AsyncMock()

        with patch("myeap.mes.adapters.rest.aiohttp.ClientSession", return_value=mock_session):
            await adapter.connect()

            assert adapter._session is not None
            assert adapter._connected is True

    @pytest.mark.asyncio
    async def test_rest_adapter_send(self):
        """Test REST adapter send"""
        config = MESConfig(
            adapter_type="rest",
            host="localhost",
            port=8001,
        )

        adapter = RestAdapter(config)

        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={"status": "ok"})

        mock_session = MagicMock()
        mock_request_ctx = MagicMock()
        mock_request_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_request_ctx.__aexit__ = AsyncMock()
        mock_session.request = MagicMock(return_value=mock_request_ctx)
        mock_session.close = AsyncMock()

        with patch("myeap.mes.adapters.rest.aiohttp.ClientSession", return_value=mock_session):
            await adapter.connect()

            message = {"type": "test", "data": "hello"}
            result = await adapter.send("/test", message, method="POST")

            assert result == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_rest_adapter_get(self):
        """Test REST adapter GET convenience method"""
        config = MESConfig(
            adapter_type="rest",
            host="localhost",
            port=8001,
        )

        adapter = RestAdapter(config)

        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={"data": "test"})

        mock_session = MagicMock()
        mock_request_ctx = MagicMock()
        mock_request_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_request_ctx.__aexit__ = AsyncMock()
        mock_session.request = MagicMock(return_value=mock_request_ctx)
        mock_session.close = AsyncMock()

        with patch("myeap.mes.adapters.rest.aiohttp.ClientSession", return_value=mock_session):
            await adapter.connect()

            result = await adapter.get("/data")
            assert result == {"data": "test"}

            # Verify GET was used
            mock_session.request.assert_called_once()
            call_args = mock_session.request.call_args
            assert call_args[1]["method"] == "GET"

    @pytest.mark.asyncio
    async def test_rest_adapter_post(self):
        """Test REST adapter POST convenience method"""
        config = MESConfig(
            adapter_type="rest",
            host="localhost",
            port=8001,
        )

        adapter = RestAdapter(config)

        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={"id": 1})

        mock_session = MagicMock()
        mock_request_ctx = MagicMock()
        mock_request_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_request_ctx.__aexit__ = AsyncMock()
        mock_session.request = MagicMock(return_value=mock_request_ctx)
        mock_session.close = AsyncMock()

        with patch("myeap.mes.adapters.rest.aiohttp.ClientSession", return_value=mock_session):
            await adapter.connect()

            message = {"name": "test"}
            result = await adapter.post("/items", message)
            assert result == {"id": 1}

            call_args = mock_session.request.call_args
            assert call_args[1]["method"] == "POST"


class TestKafkaAdapter:
    """Test KafkaAdapter class"""

    def test_create_kafka_adapter(self):
        """Test creating Kafka adapter"""
        config = MESConfig(
            adapter_type="kafka",
            bootstrap_servers="localhost:9092",
            consumer_group="myeap",
        )

        adapter = KafkaAdapter(config)
        assert adapter.config == config
        assert adapter._producer is None

    @pytest.mark.asyncio
    async def test_kafka_adapter_connect(self):
        """Test Kafka adapter connect"""
        config = MESConfig(
            adapter_type="kafka",
            bootstrap_servers="localhost:9092",
        )

        adapter = KafkaAdapter(config)

        mock_producer = MagicMock()
        mock_producer.start = AsyncMock()
        mock_producer.stop = AsyncMock()

        with patch("myeap.mes.adapters.kafka.AIOKafkaProducer", return_value=mock_producer):
            await adapter.connect()

            mock_producer.start.assert_called_once()
            assert adapter._producer is not None
            assert adapter._connected is True

    @pytest.mark.asyncio
    async def test_kafka_adapter_disconnect(self):
        """Test Kafka adapter disconnect"""
        config = MESConfig(
            adapter_type="kafka",
            bootstrap_servers="localhost:9092",
        )

        adapter = KafkaAdapter(config)

        mock_producer = MagicMock()
        mock_producer.start = AsyncMock()
        mock_producer.stop = AsyncMock()

        with patch("myeap.mes.adapters.kafka.AIOKafkaProducer", return_value=mock_producer):
            await adapter.connect()
            assert adapter._connected is True

            await adapter.disconnect()
            mock_producer.stop.assert_called_once()
            assert adapter._connected is False

    @pytest.mark.asyncio
    async def test_kafka_adapter_send(self):
        """Test Kafka adapter send"""
        config = MESConfig(
            adapter_type="kafka",
            bootstrap_servers="localhost:9092",
        )

        adapter = KafkaAdapter(config)

        mock_producer = MagicMock()
        mock_producer.start = AsyncMock()
        mock_producer.send_and_wait = AsyncMock()

        with patch("myeap.mes.adapters.kafka.AIOKafkaProducer", return_value=mock_producer):
            await adapter.connect()

            message = {"type": "test", "data": "hello"}
            await adapter.send("test-topic", message)

            mock_producer.send_and_wait.assert_called_once()

    @pytest.mark.asyncio
    async def test_kafka_adapter_send_with_key(self):
        """Test Kafka adapter send with key"""
        config = MESConfig(
            adapter_type="kafka",
            bootstrap_servers="localhost:9092",
        )

        adapter = KafkaAdapter(config)

        mock_producer = MagicMock()
        mock_producer.start = AsyncMock()
        mock_producer.send_and_wait = AsyncMock()

        with patch("myeap.mes.adapters.kafka.AIOKafkaProducer", return_value=mock_producer):
            await adapter.connect()

            message = {"type": "test"}
            await adapter.send("test-topic", message, key="partition-key")

            mock_producer.send_and_wait.assert_called_once()


class TestAdapterMetrics:
    """Test adapter metrics integration"""

    def test_adapter_has_metrics(self):
        """Test that adapter has metrics collector"""
        config = MESConfig(
            adapter_type="mqtt",
            host="localhost",
            port=1883,
        )

        class TestAdapter(MESAdapter):
            async def connect(self):
                pass

            async def disconnect(self):
                pass

            async def send(self, topic, message):
                pass

            async def subscribe(self, topic, handler):
                pass

            async def unsubscribe(self, topic):
                pass

        adapter = TestAdapter(config)
        assert adapter._metrics is not None

    def test_config_repr(self):
        """Test config string representation"""
        config = MESConfig(
            adapter_type="mqtt",
            host="localhost",
            port=1883,
        )

        repr_str = repr(config)
        assert "mqtt" in repr_str
        assert "localhost" in repr_str
        assert "1883" in repr_str


class TestAdapterFactory:
    """Test adapter factory patterns"""

    def test_get_adapter_by_type_mqtt(self):
        """Test getting MQTT adapter"""
        config = MESConfig(
            adapter_type="mqtt",
            host="localhost",
            port=1883,
        )

        adapter = MqttAdapter(config)
        assert isinstance(adapter, MESAdapter)
        assert isinstance(adapter, MqttAdapter)

    def test_get_adapter_by_type_rest(self):
        """Test getting REST adapter"""
        config = MESConfig(
            adapter_type="rest",
            host="localhost",
            port=8001,
        )

        adapter = RestAdapter(config)
        assert isinstance(adapter, MESAdapter)
        assert isinstance(adapter, RestAdapter)

    def test_get_adapter_by_type_kafka(self):
        """Test getting Kafka adapter"""
        config = MESConfig(
            adapter_type="kafka",
            bootstrap_servers="localhost:9092",
        )

        adapter = KafkaAdapter(config)
        assert isinstance(adapter, MESAdapter)
        assert isinstance(adapter, KafkaAdapter)
