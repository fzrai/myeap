"""数据采样器

提供多种采样策略，用于减少数据量同时保留关键信息：
- TimeBasedSampler: 定时采样（保留所有点）
- ChangeBasedSampler: 变化采样（值变化超过阈值时采样）
- StatisticalSampler: 统计采样（聚合后采样）
- SmartSampler: 智能采样（基于信号特征）
"""

import logging
import statistics
from collections import deque
from typing import Deque, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from myeap.data.models import DataPoint

from myeap.data.models import DataPoint

logger = logging.getLogger(__name__)


class DataSampler:
    """数据采样器

    支持多种采样策略：
    - 定时采样
    - 变化采样（值变化超过阈值时采样）
    - 统计采样（聚合后采样）
    - 智能采样（基于信号特征）

    Attributes:
        sampling_strategies: 支持的采样策略字典

    Example:
        sampler = DataSampler()
        sampled = sampler.sample(points, strategy="change_based")
    """

    def __init__(self):
        """初始化采样器"""
        self.sampling_strategies = {
            "time_based": TimeBasedSampler(),
            "change_based": ChangeBasedSampler(),
            "statistical": StatisticalSampler(),
            "smart": SmartSampler(),
        }

    def sample(
        self,
        points: List["DataPoint"],
        strategy: str = "time_based",
    ) -> List["DataPoint"]:
        """采样数据点

        Args:
            points: 原始数据点列表
            strategy: 采样策略名称

        Returns:
            采样后的数据点列表
        """
        sampler = self.sampling_strategies.get(strategy)
        if sampler is None:
            logger.warning(f"Unknown sampling strategy: {strategy}, using time_based")
            sampler = self.sampling_strategies["time_based"]
        return sampler.sample(points)

    def register_strategy(
        self,
        name: str,
        sampler: "BaseSampler",
    ) -> None:
        """注册自定义采样策略

        Args:
            name: 策略名称
            sampler: 采样器实例
        """
        self.sampling_strategies[name] = sampler


class BaseSampler:
    """采样器基类"""

    def sample(self, points: List["DataPoint"]) -> List["DataPoint"]:
        """采样数据点

        Args:
            points: 原始数据点列表

        Returns:
            采样后的数据点列表
        """
        raise NotImplementedError


class TimeBasedSampler(BaseSampler):
    """定时采样

    所有点都保留，适用于低频数据或需要完整数据流的场景。
    """

    def sample(self, points: List["DataPoint"]) -> List["DataPoint"]:
        """采样数据点

        所有点都保留。

        Args:
            points: 原始数据点列表

        Returns:
            原始数据点列表（未修改）
        """
        return points


class ChangeBasedSampler(BaseSampler):
    """变化采样

    当值变化超过阈值时保留点，用于减少稳定信号的数据量。

    Attributes:
        threshold: 变化阈值（相对变化率），默认0.01 (1%)
    """

    def __init__(self, threshold: float = 0.01):
        """初始化变化采样器

        Args:
            threshold: 变化阈值（相对变化率），默认0.01
        """
        self.threshold = threshold
        self._last_values: Dict[str, float] = {}

    def sample(self, points: List["DataPoint"]) -> List["DataPoint"]:
        """采样数据点

        仅当值变化超过阈值时保留点。

        Args:
            points: 原始数据点列表

        Returns:
            采样后的数据点列表
        """
        sampled = []
        for point in points:
            key = f"{point.equipment_id}:{point.parameter_name}"
            last_value = self._last_values.get(key)

            if last_value is None:
                # 第一个点总是保留
                sampled.append(point)
            else:
                # 计算相对变化率
                if last_value != 0:
                    relative_change = abs(point.value - last_value) / abs(last_value)
                else:
                    relative_change = abs(point.value - last_value) if point.value != 0 else 0

                if relative_change > self.threshold:
                    sampled.append(point)

            self._last_values[key] = point.value

        return sampled

    def reset(self) -> None:
        """重置采样器状态"""
        self._last_values.clear()


class StatisticalSampler(BaseSampler):
    """统计采样

    对高频数据进行聚合，当窗口满时输出统计值（均值）。

    Attributes:
        window_size: 窗口大小，默认100
    """

    def __init__(self, window_size: int = 100):
        """初始化统计采样器

        Args:
            window_size: 窗口大小
        """
        self.window_size = window_size
        self._windows: Dict[str, Deque["DataPoint"]] = {}

    def sample(self, points: List["DataPoint"]) -> List["DataPoint"]:
        """采样数据点

        当窗口满时，输出统计值（均值）。

        Args:
            points: 原始数据点列表

        Returns:
            采样后的数据点列表
        """
        sampled = []

        for point in points:
            key = f"{point.equipment_id}:{point.parameter_name}"

            if key not in self._windows:
                self._windows[key] = deque(maxlen=self.window_size)

            self._windows[key].append(point)

            # 当窗口满时，输出统计值
            if len(self._windows[key]) >= self.window_size:
                window_values = [p.value for p in self._windows[key]]
                sampled.append(DataPoint(
                    equipment_id=point.equipment_id,
                    chamber_id=point.chamber_id,
                    parameter_name=point.parameter_name,
                    value=statistics.mean(window_values),
                    unit=point.unit,
                    timestamp=point.timestamp,
                ))
                self._windows[key].clear()

        return sampled

    def reset(self) -> None:
        """重置采样器状态"""
        self._windows.clear()

    def get_window_size(self, key: str) -> int:
        """获取指定key的当前窗口大小

        Args:
            key: 窗口key

        Returns:
            当前窗口大小
        """
        return len(self._windows.get(key, []))


class SmartSampler(BaseSampler):
    """智能采样

    基于信号特征的采样，变化快时增加采样，变化慢时减少。

    Attributes:
        min_interval: 最小采样间隔
        max_interval: 最大采样间隔
    """

    def __init__(
        self,
        min_interval: float = 0.1,
        max_interval: float = 10.0,
    ):
        """初始化智能采样器

        Args:
            min_interval: 最小采样间隔
            max_interval: 最大采样间隔
        """
        self.min_interval = min_interval
        self.max_interval = max_interval
        self._derivatives: Dict[str, List[float]] = {}

    def sample(self, points: List["DataPoint"]) -> List["DataPoint"]:
        """采样数据点

        基于信号变化率自适应采样。

        Args:
            points: 原始数据点列表

        Returns:
            采样后的数据点列表
        """
        sampled = []

        for i, point in enumerate(points):
            key = f"{point.equipment_id}:{point.parameter_name}"

            if key not in self._derivatives:
                self._derivatives[key] = []

            # 始终保留第一个点
            if i == 0:
                sampled.append(point)
                self._derivatives[key].append(point.value)
                continue

            # 计算导数近似（使用最近几个值）
            derivatives = self._derivatives[key]
            should_sample = False

            if derivatives:
                # 计算差分
                delta_value = point.value - sampled[-1].value

                # 计算平均导数
                if len(derivatives) > 1:
                    avg_derivative = sum(
                        derivatives[j] - derivatives[j - 1]
                        for j in range(1, len(derivatives))
                    ) / (len(derivatives) - 1)
                else:
                    avg_derivative = derivatives[0]

                # 如果当前变化大于平均导数的最小间隔，则保留
                threshold = abs(avg_derivative) * self.min_interval if avg_derivative != 0 else 0
                if abs(delta_value) > max(threshold, 0.001):
                    should_sample = True

                # 如果是最后一个点，也保留
                if i == len(points) - 1:
                    should_sample = True

                # 如果值完全相同，也保留（可能是状态变化）
                if delta_value == 0 and point.value != sampled[-1].value:
                    should_sample = True

            if should_sample:
                sampled.append(point)

            self._derivatives[key].append(point.value)
            # 保持历史记录在合理范围内
            if len(self._derivatives[key]) > 100:
                self._derivatives[key] = self._derivatives[key][-50:]

        return sampled

    def reset(self) -> None:
        """重置采样器状态"""
        self._derivatives.clear()
