"""设备插件测试"""

import pytest

from myeap.device.plugins.base import EquipmentPlugin, PluginRegistry
from myeap.device.plugins.cleaner import CleanerPlugin
from myeap.device.plugins.cvd import CvdPlugin


class MockPlugin(EquipmentPlugin):
    """测试用模拟插件"""

    @property
    def equipment_type(self) -> str:
        return "mock"

    async def initialize(self, config):
        self._config = config
        self._initialized = True

    async def on_connected(self):
        pass

    async def on_disconnected(self):
        pass

    async def handle_message(self, message):
        return None

    async def start_process(self, recipe_id, chamber_id, params):
        return "mock-process-001"

    async def pause_process(self, process_id):
        return True

    async def resume_process(self, process_id):
        return True

    async def abort_process(self, process_id):
        return True

    async def get_process_status(self, process_id):
        return {"process_id": process_id}


class TestPluginRegistry:
    """插件注册表测试"""

    def test_register(self):
        """测试注册插件"""
        registry = PluginRegistry()
        plugin = MockPlugin()

        registry.register(plugin)
        assert "mock" in registry.get_supported_types()

    def test_unregister(self):
        """测试注销插件"""
        registry = PluginRegistry()
        plugin = MockPlugin()

        registry.register(plugin)
        registry.unregister("mock")
        assert "mock" not in registry.get_supported_types()

    def test_get(self):
        """测试获取插件"""
        registry = PluginRegistry()
        plugin = MockPlugin()

        registry.register(plugin)
        retrieved = registry.get("mock")
        assert retrieved is not None
        assert retrieved.equipment_type == "mock"

    def test_get_nonexistent(self):
        """测试获取不存在的插件"""
        registry = PluginRegistry()
        assert registry.get("nonexistent") is None


class TestCleanerPlugin:
    """清洗设备插件测试"""

    @pytest.fixture
    def plugin(self):
        """创建插件实例"""
        return CleanerPlugin()

    def test_equipment_type(self, plugin):
        """测试设备类型"""
        assert plugin.equipment_type == "cleaner"

    @pytest.mark.asyncio
    async def test_initialize(self, plugin):
        """测试初始化"""
        config = {
            "max_chambers": 4,
            "recipes": {
                "standard_clean": {
                    "name": "Standard Clean",
                    "steps": [
                        {"name": "Pre-clean", "duration": 30},
                        {"name": "Main clean", "duration": 120},
                        {"name": "Rinse", "duration": 60},
                    ],
                },
            },
        }

        await plugin.initialize(config)
        assert plugin.is_initialized

    @pytest.mark.asyncio
    async def test_start_process(self, plugin):
        """测试启动工艺"""
        plugin._initialized = True
        plugin._recipes = {
            "clean_1": {
                "name": "Clean 1",
                "steps": [
                    {"name": "Step 1", "duration": 60},
                ],
            },
        }

        process_id = await plugin.start_process(
            "clean_1",
            "ch-01",
            {"wafer_ids": ["W001", "W002"]},
        )
        assert process_id.startswith("cleaner-")
        assert process_id in plugin._processes

    @pytest.mark.asyncio
    async def test_validate_recipe(self, plugin):
        """测试配方验证"""
        valid_recipe = {
            "name": "Valid Recipe",
            "steps": [
                {"name": "Step 1", "duration": 60},
                {"name": "Step 2", "duration": 120},
            ],
        }
        assert await plugin.validate_recipe(valid_recipe)

        invalid_recipe = {
            "name": "Invalid Recipe",
            "steps": [],  # 空步骤
        }
        assert not await plugin.validate_recipe(invalid_recipe)

        invalid_recipe2 = {
            # 缺少 name
            "steps": [{"name": "Step 1", "duration": 60}],
        }
        assert not await plugin.validate_recipe(invalid_recipe2)

    @pytest.mark.asyncio
    async def test_pause_resume_process(self, plugin):
        """测试暂停和恢复工艺"""
        plugin._initialized = True
        plugin._recipes = {
            "test": {
                "name": "Test",
                "steps": [{"name": "Step 1", "duration": 60}],
            },
        }

        process_id = await plugin.start_process("test", "ch-01", {})

        assert await plugin.pause_process(process_id)
        assert await plugin.resume_process(process_id)

    @pytest.mark.asyncio
    async def test_abort_process(self, plugin):
        """测试中止工艺"""
        plugin._initialized = True
        plugin._recipes = {
            "test": {
                "name": "Test",
                "steps": [{"name": "Step 1", "duration": 60}],
            },
        }

        process_id = await plugin.start_process("test", "ch-01", {})
        assert await plugin.abort_process(process_id)

        status = await plugin.get_process_status(process_id)
        assert status["state"] == "ABORTED"

    @pytest.mark.asyncio
    async def test_chemical_management(self, plugin):
        """测试药液管理"""
        await plugin.set_chemical_level("H2SO4", 85.5)
        levels = await plugin.get_chemical_levels()
        assert levels["H2SO4"] == 85.5

    @pytest.mark.asyncio
    async def test_ultrasonic_control(self, plugin):
        """测试超声控制"""
        await plugin.set_ultrasonic_power("ch-01", 75.0)
        power = await plugin.get_ultrasonic_power("ch-01")
        assert power == 75.0

        # 测试边界值
        await plugin.set_ultrasonic_power("ch-01", 150.0)  # 超过100
        power = await plugin.get_ultrasonic_power("ch-01")
        assert power == 100.0


class TestCvdPlugin:
    """CVD设备插件测试"""

    @pytest.fixture
    def plugin(self):
        """创建插件实例"""
        return CvdPlugin()

    def test_equipment_type(self, plugin):
        """测试设备类型"""
        assert plugin.equipment_type == "cvd"

    @pytest.mark.asyncio
    async def test_initialize(self, plugin):
        """测试初始化"""
        config = {
            "max_chambers": 4,
            "max_temperature": 900,
            "recipes": {
                "sio2_deposition": {
                    "name": "SiO2 Deposition",
                    "steps": [
                        {
                            "name": "Pre-deposition",
                            "duration": 60,
                            "parameters": {"temperature": 400, "pressure": 5},
                        },
                        {
                            "name": "Deposition",
                            "duration": 300,
                            "parameters": {"temperature": 400, "pressure": 5},
                        },
                    ],
                },
            },
        }

        await plugin.initialize(config)
        assert plugin.is_initialized

    @pytest.mark.asyncio
    async def test_start_process(self, plugin):
        """测试启动工艺"""
        plugin._initialized = True
        plugin._recipes = {
            "sio2": {
                "name": "SiO2",
                "steps": [
                    {
                        "name": "Deposition",
                        "duration": 60,
                        "parameters": {"temperature": 400, "pressure": 5},
                    },
                ],
            },
        }

        process_id = await plugin.start_process(
            "sio2",
            "ch-01",
            {"wafer_ids": ["W001"], "thickness_target": 1000},
        )
        assert process_id.startswith("cvd-")

    @pytest.mark.asyncio
    async def test_validate_recipe(self, plugin):
        """测试配方验证"""
        valid_recipe = {
            "name": "Valid CVD Recipe",
            "steps": [
                {
                    "name": "Step 1",
                    "duration": 60,
                    "parameters": {"temperature": 400, "pressure": 5},
                },
            ],
        }
        assert await plugin.validate_recipe(valid_recipe)

        # 缺少温度参数
        invalid_recipe = {
            "name": "Invalid Recipe",
            "steps": [
                {
                    "name": "Step 1",
                    "duration": 60,
                    "parameters": {"pressure": 5},  # 缺少 temperature
                },
            ],
        }
        assert not await plugin.validate_recipe(invalid_recipe)

    @pytest.mark.asyncio
    async def test_gas_flow_control(self, plugin):
        """测试气体流量控制"""
        flows = {
            "SiH4": 100,
            "N2O": 200,
            "N2": 500,
        }
        await plugin.set_gas_flows("ch-01", flows)
        retrieved = await plugin.get_gas_flows("ch-01")
        assert retrieved["SiH4"] == 100

    @pytest.mark.asyncio
    async def test_temperature_control(self, plugin):
        """测试温度控制"""
        await plugin.set_temperature("zone_1", 400.0)
        temps = await plugin.get_temperatures()
        assert temps["zone_1"] == 400.0

    @pytest.mark.asyncio
    async def test_pressure_control(self, plugin):
        """测试压力控制"""
        await plugin.set_pressure(10.5)
        assert await plugin.get_pressure() == 10.5

    @pytest.mark.asyncio
    async def test_rf_power_control(self, plugin):
        """测试RF功率控制"""
        await plugin.set_rf_power(1500.0)
        assert await plugin.get_rf_power() == 1500.0

    @pytest.mark.asyncio
    async def test_capabilities(self, plugin):
        """测试获取设备能力"""
        plugin._initialized = True
        plugin._config = {"max_chambers": 4}

        caps = await plugin.get_capabilities()
        assert caps["supports_plasma"]
        assert caps["max_chambers"] == 4
        assert "SiO2" in caps["supported_films"]
