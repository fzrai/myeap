"""REST MES Adapter

使用aiohttp实现与MES系统的REST API通信。
"""

import asyncio
import json
from typing import Any, Callable, Dict, Optional

import aiohttp
from aiohttp import BasicAuth

from myeap.mes.adapters.base import MESAdapter, MESConfig
from myeap.observability.tracing import trace_async, create_span


class RestAdapter(MESAdapter):
    """REST MES适配器

    使用aiohttp库实现与MES系统的REST API通信。

    支持：
    - GET/POST/PUT/DELETE请求
    - 基础认证
    - 长轮询订阅模式

    Example:
        config = MESConfig(
            adapter_type="rest",
            host="localhost",
            port=8001,
            base_url="http://localhost:8001/api",
        )
        adapter = RestAdapter(config)
        await adapter.connect()
        response = await adapter.send("/work_order", {"action": "receive"}, method="POST")
        await adapter.subscribe("/events", handler)
    """

    def __init__(self, config: MESConfig):
        super().__init__(config)
        self._session: Optional[aiohttp.ClientSession] = None
        self._poll_tasks: Dict[str, asyncio.Task] = {}
        self._running = False

    async def connect(self) -> None:
        """连接到MES REST API"""
        self.logger.info(
            "Connecting to MES REST API",
            base_url=self.config.base_url or f"http://{self.config.host}:{self.config.port}",
        )

        try:
            # 构建base_url
            base_url = self.config.base_url or f"http://{self.config.host}:{self.config.port}"

            # 配置认证
            auth = None
            if self.config.username and self.config.password:
                auth = BasicAuth(self.config.username, self.config.password)

            # 创建会话
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            self._session = aiohttp.ClientSession(
                base_url=base_url,
                auth=auth,
                timeout=timeout,
                json_serialize=lambda x: json.dumps(x, default=str),
            )

            self._running = True
            self._update_connection_status(True)

            self.logger.info(
                "Connected to MES REST API",
                base_url=base_url,
            )

        except Exception as e:
            self.logger.error(
                "Failed to connect to MES REST API",
                error=str(e),
            )
            raise

    async def disconnect(self) -> None:
        """断开REST连接"""
        self.logger.info("Disconnecting from MES REST API")

        self._running = False

        # 取消所有轮询任务
        for task in self._poll_tasks.values():
            task.cancel()
        self._poll_tasks.clear()

        # 关闭会话
        if self._session:
            try:
                await self._session.close()
            except Exception as e:
                self.logger.warning(
                    "Error closing REST session",
                    error=str(e),
                )
            finally:
                self._session = None

        self._update_connection_status(False)
        self.logger.info("Disconnected from MES REST API")

    @trace_async("rest_send")
    async def send(
        self,
        path: str,
        message: Dict[str, Any],
        method: str = "POST",
    ) -> Dict[str, Any]:
        """发送REST请求

        Args:
            path: API路径
            message: 请求消息体
            method: HTTP方法 (GET, POST, PUT, DELETE)

        Returns:
            响应数据
        """
        if not self._session or not self._connected:
            raise RuntimeError("Not connected to MES REST API")

        message_type = message.get("type", "unknown")

        with create_span("rest_request", attributes={"path": path, "method": method, "message_type": message_type}) as span:
            try:
                self.logger.debug(
                    "Sending REST request",
                    path=path,
                    method=method,
                    message_type=message_type,
                )

                async with self._session.request(
                    method=method,
                    url=path,
                    json=message,
                ) as response:
                    response_data = await response.json()
                    self._record_message_sent(message_type)

                    span.set_attribute("rest.status_code", response.status)

                    self.logger.debug(
                        "REST request completed",
                        path=path,
                        method=method,
                        status=response.status,
                    )

                    return response_data

            except aiohttp.ClientError as e:
                self.logger.error(
                    "REST request failed",
                    path=path,
                    method=method,
                    error=str(e),
                )
                raise
            except Exception as e:
                self.logger.error(
                    "Unexpected error in REST request",
                    path=path,
                    error=str(e),
                )
                raise

    @trace_async("rest_subscribe")
    async def subscribe(self, path: str, handler: Callable[[Dict[str, Any]], Any]) -> None:
        """订阅REST事件（长轮询模式）

        REST推送通常使用长轮询实现。

        Args:
            path: 订阅路径
            handler: 消息处理器
        """
        if not self._session or not self._connected:
            raise RuntimeError("Not connected to MES REST API")

        # 创建长轮询任务
        task = asyncio.create_task(self._poll_loop(path, handler))
        self._poll_tasks[path] = task

        self.logger.info(
            "Started REST subscription (long polling)",
            path=path,
        )

    async def _poll_loop(self, path: str, handler: Callable[[Dict[str, Any]], Any]) -> None:
        """长轮询循环

        Args:
            path: 轮询路径
            handler: 消息处理器
        """
        poll_interval = 5  # 轮询间隔（秒）

        while self._running:
            try:
                async with self._session.get(path) as response:
                    if response.status == 200:
                        data = await response.json()

                        message_type = data.get("type", "unknown")
                        self._record_message_received(message_type)

                        with create_span("rest_poll_message", attributes={"path": path, "message_type": message_type}):
                            await handler(data)

                    elif response.status == 204:
                        # 无内容，继续轮询
                        pass

                    elif response.status >= 400:
                        self.logger.warning(
                            "REST poll received error response",
                            path=path,
                            status=response.status,
                        )
                        await asyncio.sleep(poll_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(
                    "Error in REST poll loop",
                    path=path,
                    error=str(e),
                )
                await asyncio.sleep(poll_interval)

        self.logger.debug("REST poll loop exited", path=path)

    async def unsubscribe(self, path: str) -> None:
        """取消订阅

        Args:
            path: 订阅路径
        """
        if path in self._poll_tasks:
            self._poll_tasks[path].cancel()
            del self._poll_tasks[path]

        self.logger.info(
            "Unsubscribed from REST path",
            path=path,
        )

    async def get(self, path: str) -> Dict[str, Any]:
        """发送GET请求

        Args:
            path: API路径

        Returns:
            响应数据
        """
        return await self.send(path, {}, method="GET")

    async def post(self, path: str, message: Dict[str, Any]) -> Dict[str, Any]:
        """发送POST请求

        Args:
            path: API路径
            message: 请求消息体

        Returns:
            响应数据
        """
        return await self.send(path, message, method="POST")

    async def put(self, path: str, message: Dict[str, Any]) -> Dict[str, Any]:
        """发送PUT请求

        Args:
            path: API路径
            message: 请求消息体

        Returns:
            响应数据
        """
        return await self.send(path, message, method="PUT")

    async def delete(self, path: str) -> Dict[str, Any]:
        """发送DELETE请求

        Args:
            path: API路径

        Returns:
            响应数据
        """
        return await self.send(path, {}, method="DELETE")

    async def __aenter__(self) -> "RestAdapter":
        """上下文管理器入口"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """上下文管理器出口"""
        await self.disconnect()
