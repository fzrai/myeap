# EAP (Equipment Automation Program) 系统设计规范

**版本**: v1.0  
**日期**: 2025-05-14  
**作者**: CIM Engineering Team  
**状态**: 草稿

---

## 目录

1. [系统概述](#1-系统概述)
2. [架构设计](#2-架构设计)
3. [功能模块详述](#3-功能模块详述)
4. [数据模型](#4-数据模型)
5. [接口定义](#5-接口定义)
6. [技术选型](#6-技术选型)
7. [安全设计](#7-安全设计)
8. [部署架构](#8-部署架构)
9. [实施计划](#9-实施计划)
10. [附录](#10-附录)

---

## 1. 系统概述

### 1.1 项目背景

本项目旨在为半导体制造工厂设计并实现一套企业级EAP（Equipment Automation Program）系统，实现对全类型半导体制造设备的高效、可靠、智能化控制与管理。

### 1.2 设计目标

| 目标 | 描述 |
|------|------|
| **高可用** | 99.99%+ 系统可用性，支持故障自动转移 |
| **高性能** | 2000+设备同时接入，毫秒级响应 |
| **智能化** | AI/ML驱动的预测性维护与工艺优化 |
| **标准化** | 完全符合SEMI标准（SECS/GEM/HSMS） |
| **可扩展** | 插件化架构，支持新设备类型快速接入 |
| **合规性** | 满足FDA 21 CFR Part 11、GDPR等法规要求 |

### 1.3 系统边界

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              半导体Fab                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│    ┌─────────┐                               ┌─────────┐                    │
│    │   MES   │◄─────────────────────────────►│   EAP   │                    │
│    │ System  │      MQTT / REST / Kafka     │ System  │                    │
│    └─────────┘                               └────┬────┘                    │
│                                                  │                          │
│    ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────┴─────┐                  │
│    │ Cleaner │  │   CVD   │  │ Etcher  │  │Lithography│  ...              │
│    │  (50+)  │  │  (100+) │  │  (80+)  │  │   (40+)  │                  │
│    └─────────┘  └─────────┘  └─────────┘  └───────────┘                  │
│         │            │            │              │                        │
│         └────────────┴────────────┴──────────────┘                        │
│                          SECS/GEM over HSMS                                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Kubernetes Cluster (多可用区)                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                          Ingress Layer                               │  │
│  │                  Nginx Ingress + Cert-Manager (TLS)                  │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                       MES Integration Layer                          │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │  │
│  │  │   MQTT      │  │   REST      │  │   Kafka     │  │  Config     │  │  │
│  │  │   Adapter   │  │   Gateway   │  │  Consumer   │  │  Registry   │  │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                       Shared Services Layer                          │  │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌─────────────────────┐   │  │
│  │  │  Recipe   │ │  Alarm    │ │  Data     │ │       Audit         │   │  │
│  │  │  Manager  │ │  Handler  │ │ Collector │ │       Logger        │   │  │
│  │  └───────────┘ └───────────┘ └───────────┘ └─────────────────────┘   │  │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌─────────────────────┐   │  │
│  │  │  State    │ │  Event    │ │  Trace    │ │        Auth        │   │  │
│  │  │  Manager  │ │  Router   │ │  Service  │ │   (OAuth/LDAP)     │   │  │
│  │  └───────────┘ └───────────┘ └───────────┘ └─────────────────────┘   │  │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌─────────────────────┐   │  │
│  │  │   SPC     │ │   FDC     │ │ Digital   │ │    Predictive       │   │  │
│  │  │  Engine   │ │  Engine   │ │   Twin    │ │    Maintenance     │   │  │
│  │  └───────────┘ └───────────┘ └───────────┘ └─────────────────────┘   │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                       Device Control Layer                            │  │
│  │                                                                       │  │
│  │  ┌─────────────────────────────────────────────────────────────┐     │  │
│  │  │              Device Supervisor (每设备一个Pod)                 │     │  │
│  │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐     │     │  │
│  │  │  │   SECS/GEM  │  │  Equipment   │  │    Process      │     │     │  │
│  │  │  │   Driver    │  │    State     │  │   Controller    │     │     │  │
│  │  │  │  (pycomm3)  │  │   Machine    │  │                 │     │     │  │
│  │  │  └─────────────┘  └─────────────┘  └─────────────────┘     │     │  │
│  │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐     │     │  │
│  │  │  │  FDC Agent  │  │    Wafer    │  │   Adaptive     │     │     │  │
│  │  │  │  (边缘计算)  │  │   Tracker   │  │   Controller   │     │     │  │
│  │  │  └─────────────┘  └─────────────┘  └─────────────────┘     │     │  │
│  │  └─────────────────────────────────────────────────────────────┘     │  │
│  │                                                                       │  │
│  │  [Cleaner-001] [Cleaner-002] ... [CVD-001] [CVD-002] ... [Etcher] │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                         Data Layer                                   │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────┐  │  │
│  │  │    Redis     │  │  PostgreSQL  │  │   TimescaleDB │  │MinIO  │  │  │
│  │  │   Cluster    │  │   (Citus)    │  │   (时序数据)  │  │(S3)   │  │  │
│  │  │ (状态/缓存)  │  │  (事务/历史)  │  │   (FDC/SPC)  │  │(配方) │  │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └───────┘  │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │  │
│  │  │ Elasticsearch │  │   Kafka      │  │   Prometheus/Grafana    │  │  │
│  │  │   (日志)      │  │  (消息队列)   │  │      (监控告警)          │  │  │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────┘  │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 核心设计原则

1. **微服务架构** - 每个服务职责单一，独立部署和扩展
2. **事件驱动** - 通过Kafka实现服务间松耦合通信
3. **插件化设备支持** - 新设备类型通过插件方式接入
4. **边缘计算** - 设备端边缘节点实现低延迟响应
5. **AI/ML原生** - 内置机器学习平台，支持预测性分析

---

## 3. 功能模块详述

### 3.1 MES Integration Layer

#### 3.1.1 工单管理 (Work Order Management)

| 功能 | 描述 | 优先级 |
|------|------|--------|
| 工单接收 | 从MES接收工单（MQTT/REST/Kafka） | P0 |
| 工单验证 | 校验晶圆数量、配方匹配、设备能力 | P0 |
| 工单拆分 | 大工单拆分为多个批次处理 | P1 |
| 工单合并 | 多个小工单合并处理 | P1 |
| 工单调度 | 根据优先级、设备状态智能调度 | P1 |
| 工单跟踪 | 实时跟踪工单处理进度 | P0 |
| 工单暂停/恢复 | 支持人工干预工单执行 | P1 |
| 工单历史 | 完整工单执行记录追溯 | P0 |

#### 3.1.2 MES适配器

```python
# MES适配器接口
class MESAdapter(ABC):
    @abstractmethod
    async def receive_work_order(self) -> WorkOrder: ...
    
    @abstractmethod
    async def report_equipment_status(self, status: EquipmentStatus): ...
    
    @abstractmethod
    async def report_alarm(self, alarm: Alarm): ...
    
    @abstractmethod
    async def report_completion(self, completion: JobCompletion): ...
    
    @abstractmethod
    async def report_yield(self, yield_data: YieldData): ...

# 实现类
class MQTTAdapter(MESAdapter): ...
class RESTAdapter(MESAdapter): ...
class KafkaAdapter(MESAdapter): ...
```

---

### 3.2 SECS/GEM Protocol Layer

#### 3.2.1 支持的消息流

| 消息流 | 功能 | SEMI标准 |
|--------|------|----------|
| S1 | Communications | E5 |
| S2 | Equipment Status | E5 |
| S3 | Equipment Control | E5 |
| S4 | Material Status | E5 |
| S5 | Alarm Management | E5 |
| S6 | Data Collection | E5 |
| S7 | Recipe Management | E5, E37 |
| S8 | Calendar | E5 |
| S9 | Error Messages | E5 |
| S10 | Remote Terminal Interface | E5 |
| S11 | Service Access | E84 |
| S12 | Object Factory | E157 |
| S13 | Equipment Constants | E164 |
| S14 | Equipment Object Performance | E179 |
| S15 | Substrate Tracking | E84, E90 |
| S17 | Process Job Management | E87, E90 |

#### 3.2.2 SECS协议栈架构

```python
# SECS协议栈
class SecsStack:
    """SECS-II协议栈核心"""
    
    async def connect(self, host: str, port: int, mode: HSMSMode): ...
    async def send_message(self, header: SecsHeader, body: SecsBody): ...
    async def receive_message(self) -> SecsMessage: ...
    
# 消息处理管道
class MessagePipeline:
    """消息处理管道"""
    
    async def handle_incoming(self, message: SecsMessage): ...
    async def handle_outgoing(self, message: SecsMessage): ...
    
# GEM标准实现
class GemHandler:
    """GEM标准消息处理器"""
    
    # S1 - Communications
    async def on_establish_communication_request(self, msg): ...
    async def on_are_you_remember_request(self, msg): ...
    
    # S2 - Equipment Status
    async def on_equipment_status_request(self, msg): ...
    async def on_equipment_constant_request(self, msg): ...
    async def on_new_equipment_status(self, msg): ...
    
    # S5 - Alarm Management
    async def on_alarm_report_request(self, msg): ...
    async def on_enable_disable_alarm_request(self, msg): ...
    
    # S6 - Data Collection
    async def on_data_collection_request(self, msg): ...
    async def on_triggered_data_request(self, msg): ...
    
    # S7 - Recipe Management
    async def on_process_program_request(self, msg): ...
    async def on_process_program_send(self, msg): ...
    async def on_process_program_load_inquire(self, msg): ...
```

---

### 3.3 Process Control Layer

#### 3.3.1 工艺流程引擎

```python
class ProcessFlowEngine:
    """工艺流程引擎"""
    
    async def load_recipe(self, recipe_id: str) -> Recipe: ...
    async def execute_sequence(self, sequence: ProcessSequence): ...
    async def pause(self): ...
    async def resume(self): ...
    async def abort(self): ...

class ProcessSequence:
    """工艺序列定义"""
    
    steps: List[ProcessStep]
    transitions: List[StateTransition]
    guards: List[TransitionGuard]

class ProcessStep:
    """工艺步骤"""
    
    name: str
    parameters: Dict[str, ParameterValue]
    duration: Optional[Duration]
    endpoints: List[EndpointSpec]
    fdc_limits: Dict[str, FdcLimit]
```

#### 3.3.2 腔体控制

```python
class ChamberController:
    """腔体控制器"""
    
    async def pump_down(self, chamber_id: str): ...
    async def purge(self, chamber_id: str, gas: str): ...
    async def heat(self, chamber_id: str, target_temp: float): ...
    async def stabilize_pressure(self, chamber_id: str, target: float): ...
    async def ignite_plasma(self, chamber_id: str, power: float): ...
    async def execute_step(self, step: ProcessStep): ...

class ChamberState:
    """腔体状态"""
    
    chamber_id: str
    status: ChamberStatus  # PUMPED, PURGED, HEATING, STABLE, PROCESSING, VENTING
    temperature: float
    pressure: float
    gas_flows: Dict[str, float]  # MFC ID -> sccm
    plasma: bool
    current_step: Optional[str]
```

#### 3.3.3 自适应控制器

```python
class AdaptiveController:
    """自适应工艺控制器"""
    
    async def adjust_parameters(self, 
                               chamber_id: str,
                               deviations: Dict[str, float]) -> Dict[str, float]:
        """
        基于实时数据调整工艺参数
        Returns: 调整后的参数
        """
        # PID自适应调整
        # 预测模型更新
        # 约束满足检查
        ...
    
    async def predict_outcome(self, 
                             parameters: Dict[str, float]) -> ProcessPrediction:
        """预测工艺结果"""
        ...
    
    async def optimize_parameters(self, objective: str) -> Dict[str, float]:
        """优化工艺参数"""
        ...
```

---

### 3.4 Quality Management Layer

#### 3.4.1 SPC Engine

```python
class SPCEngine:
    """统计过程控制引擎"""
    
    # 控制图类型
    async def create_control_chart(self, 
                                   chart_type: ChartType,
                                   parameters: SPCParameters) -> ControlChart:
        """
        支持的控制图类型:
        - X_BAR_R: X-bar and R chart
        - X_BAR_S: X-bar and S chart
        - X_MR: Individual and Moving Range
        - C: C chart (defects)
        - U: U chart (defects per unit)
        - P: P chart (proportion)
        - NP: NP chart
        - MULTIVARIATE: Hotelling T²
        """
        ...
    
    async def evaluate_rule(self, 
                           data_point: float,
                           chart_id: str) -> List[SPCViolation]:
        """评估SPC规则"""
        # Westgard规则
        # 连续N点递增/递减
        # 连续N点在中心线同一侧
        # 超出控制限
        ...
    
    async def calculate_capability(self, 
                                   data: List[float]) -> ProcessCapability:
        """计算过程能力指数"""
        return ProcessCapability(
            cp=...,  # 短期能力
            cpk=...,  # 偏移能力
            pp=...,   # 长期能力
            ppk=...,  # 长期偏移能力
            sigma=...,
            mean=...,
            usl=...,
            lsl=...
        )

class ControlChart:
    """控制图"""
    
    chart_id: str
    chart_type: ChartType
    parameters: SPCParameters
    control_limits: ControlLimits  # UCL, LCL, CL
    specification_limits: SpecLimits  # USL, LSL
    data_points: List[DataPoint]
    violations: List[SPCViolation]
    
    async def add_point(self, value: float, timestamp: datetime) -> SPCViolation: ...
    async def get_trend(self) -> TrendAnalysis: ...
```

#### 3.4.2 FDC Engine

```python
class FDCEngine:
    """故障检测与分类引擎"""
    
    async def start_monitoring(self, chamber_id: str): ...
    async def stop_monitoring(self, chamber_id: str): ...
    
    async def process_data(self, 
                          chamber_id: str,
                          data: ProcessData) -> FDCResult:
        """处理工艺数据，返回异常检测结果"""
        ...
    
    async def extract_features(self, 
                              raw_data: TimeSeriesData) -> FeatureVector:
        """提取特征"""
        features = {
            'mean': np.mean(raw_data.values),
            'std': np.std(raw_data.values),
            'slope': linear_slope(raw_data),
            'variance_trend': variance_trend(raw_data),
            'peak_count': count_peaks(raw_data),
            'drift': detect_drift(raw_data),
            'oscillation': detect_oscillation(raw_data),
            'pattern_match': match_template(raw_data),
        }
        return FeatureVector(features)
    
    async def classify_fault(self, 
                           features: FeatureVector,
                           chamber_id: str) -> FaultClassification:
        """分类故障类型"""
        # 温度异常
        # 压力异常
        # 气体流量异常
        # 等离子体不稳定
        # 膜厚异常
        # 颗粒污染
        ...

class FDCResult:
    """FDC检测结果"""
    
    chamber_id: str
    timestamp: datetime
    is_anomaly: bool
    anomaly_score: float  # 0-1
    fault_type: Optional[FaultType]
    confidence: float
    affected_parameters: List[str]
    recommendations: List[str]

class FaultClassifier:
    """故障分类器（支持多种算法）"""
    
    # 统计方法
    def classify_statistical(self, features: FeatureVector) -> FaultClassification: ...
    
    # 机器学习方法
    def classify_ml(self, features: FeatureVector) -> FaultClassification: ...
    
    # 深度学习方法
    def classify_dl(self, time_series: TimeSeriesData) -> FaultClassification: ...
```

---

### 3.5 AI/ML Intelligence Layer

#### 3.5.1 预测性维护

```python
class PredictiveMaintenanceEngine:
    """预测性维护引擎"""
    
    async def predict_failure(self, 
                             equipment_id: str,
                             horizon: Duration) -> FailurePrediction:
        """
        预测设备故障
        """
        # 收集设备历史数据
        data = await self.collect_equipment_data(equipment_id)
        
        # 特征工程
        features = self.extract_maintenance_features(data)
        
        # 预测模型推理
        prediction = await self.model.predict(features)
        
        return FailurePrediction(
            equipment_id=equipment_id,
            failure_probability=prediction.probability,
            predicted_failure_time=prediction.time,
            confidence_interval=prediction.confidence,
            risk_factors=prediction.risk_factors,
            recommended_actions=prediction.actions
        )
    
    async def calculate_rul(self, 
                          equipment_id: str) -> RemainingUsefulLife:
        """计算剩余使用寿命"""
        ...
    
    async def generate_maintenance_plan(self) -> MaintenanceSchedule:
        """生成维护计划"""
        ...

class MaintenancePredictor:
    """维护预测模型"""
    
    # 模型类型
    model_type: Literal["lstm", "transformer", "prophet", "ensemble"]
    
    async def train(self, historical_data: List[EquipmentHistory]): ...
    async def predict(self, features: FeatureVector) -> Prediction: ...
    async def update(self, new_data: EquipmentHistory): ...  # 在线学习
```

#### 3.5.2 良率预测

```python
class YieldPredictionEngine:
    """良率预测引擎"""
    
    async def predict_yield(self,
                           lot_id: str,
                           current_process: str) -> YieldPrediction:
        """
        基于当前工艺参数预测批次良率
        """
        # 获取工艺参数
        params = await self.get_process_parameters(lot_id)
        
        # 获取历史相似批次
        similar_lots = await self.find_similar_lots(params)
        
        # 预测模型
        prediction = await self.model.predict(params, similar_lots)
        
        return YieldPrediction(
            lot_id=lot_id,
            predicted_yield=prediction.yield_rate,
            confidence=prediction.confidence,
            risk_factors=prediction.risk_factors,
            recommendations=prediction.recommendations
        )
```

#### 3.5.3 根因分析

```python
class RootCauseAnalyzer:
    """根因分析引擎"""
    
    async def analyze(self, 
                     anomaly: AnomalyEvent) -> RootCauseAnalysis:
        """
        分析异常根因
        """
        # 收集相关数据
        context = await self.gather_context(anomaly)
        
        # 因果推断
        causal_graph = await self.causal_inference(context)
        
        # 生成报告
        return RootCauseAnalysis(
            primary_cause=causal_graph.root_cause,
            contributing_factors=causal_graph.factors,
            evidence=causal_graph.evidence,
            recommended_fixes=causal_graph.fixes,
            similar_incidents=causal_graph.historical_similar
        )
```

---

### 3.6 Digital Twin Layer

```python
class DigitalTwin:
    """设备数字孪生"""
    
    # 实时同步
    async def sync_state(self, equipment_state: PhysicalState): ...
    async def get_virtual_state(self) -> VirtualState: ...
    
    # 仿真模拟
    async def simulate_process(self, 
                             recipe: Recipe,
                             iterations: int = 1) -> SimulationResult:
        """仿真工艺执行"""
        ...
    
    async def what_if_analysis(self,
                              scenario: WhatIfScenario) -> WhatIfResult:
        """What-If分析"""
        ...
    
    # 健康监测
    async def assess_health(self) -> TwinHealth: ...
    
    # 预测
    async def predict_future_state(self, 
                                  horizon: Duration) -> PredictedState: ...
```

---

### 3.7 Recipe Management Layer

```python
class RecipeManager:
    """配方管理器"""
    
    # 配方存储
    async def create_recipe(self, recipe: Recipe) -> str: ...
    async def get_recipe(self, recipe_id: str) -> Recipe: ...
    async def update_recipe(self, recipe_id: str, recipe: Recipe): ...
    async def delete_recipe(self, recipe_id: str): ...
    
    # 配方版本
    async def create_version(self, recipe_id: str) -> RecipeVersion: ...
    async def compare_versions(self, v1: str, v2: str) -> VersionDiff: ...
    async def rollback_version(self, recipe_id: str, version: str): ...
    
    # 配方操作
    async def upload_to_equipment(self, recipe_id: str, equipment_id: str): ...
    async def download_from_equipment(self, equipment_id: str) -> Recipe: ...
    async def select_recipe(self, equipment_id: str, recipe_id: str): ...
    
    # 配方比对
    async def compare_with_equipment(self, 
                                    recipe_id: str,
                                    equipment_id: str) -> RecipeDiff: ...
    async def verify_recipe(self, recipe: Recipe) -> VerificationResult: ...

class Recipe:
    """配方定义"""
    
    recipe_id: str
    name: str
    equipment_type: str
    version: str
    parameters: List[RecipeParameter]
    steps: List[RecipeStep]
    fdc_limits: Dict[str, FdcLimit]
    metadata: RecipeMetadata
    
    # 支持参数化配方
    template_parameters: List[TemplateParameter] = []

class RecipeParameter:
    """配方参数"""
    
    name: str
    value: ParameterValue
    unit: str
    min_value: Optional[float]
    max_value: Optional[float]
    adjustable: bool = True
```

---

### 3.8 Alarm Management Layer

```python
class AlarmManager:
    """报警管理器"""
    
    async def raise_alarm(self, alarm: Alarm): ...
    async def acknowledge_alarm(self, alarm_id: str, user: str): ...
    async def clear_alarm(self, alarm_id: str): ...
    async def suppress_alarm(self, alarm_id: str, duration: Duration): ...
    
    # 报警升级
    async def escalate_alarm(self, alarm: Alarm): ...
    async def notify(self, alarm: Alarm, channels: List[NotifyChannel]): ...
    
    # 统计分析
    async def get_alarm_statistics(self, 
                                  time_range: TimeRange) -> AlarmStatistics: ...
    async def find_alarm_patterns(self) -> List[AlarmPattern]: ...

class Alarm:
    """报警定义"""
    
    alarm_id: str
    code: str
    severity: AlarmSeverity  # CRITICAL, MAJOR, MINOR, WARNING, INFO
    text: str
    equipment_id: str
    timestamp: datetime
    acknowledged_by: Optional[str]
    acknowledged_at: Optional[datetime]
    cleared_by: Optional[str]
    cleared_at: Optional[datetime]

class AlarmEscalationPolicy:
    """报警升级策略"""
    
    severity: AlarmSeverity
    initial_delay: Duration
    escalation_interval: Duration
    max_escalations: int
    notification_channels: List[NotifyChannel]
    assignees: List[User]
```

---

### 3.9 Tracking & Genealogy Layer

```python
class TrackingService:
    """追踪服务"""
    
    # 载具管理
    async def register_carrier(self, carrier: Carrier) -> str: ...
    async def get_carrier_info(self, carrier_id: str) -> CarrierInfo: ...
    async def move_carrier(self, carrier_id: str, destination: str): ...
    
    # 晶圆追踪
    async def track_wafer(self, wafer_id: str) -> WaferHistory: ...
    async def record_process_event(self, event: ProcessEvent): ...
    
    # 追溯查询
    async def trace_lot(self, lot_id: str) -> LotTrace: ...
    async def find_affected_lots(self, 
                                 equipment_id: str,
                                 time_range: TimeRange) -> List[str]: ...

class Carrier:
    """载具"""
    
    carrier_id: str
    carrier_type: CarrierType  # FOUP, FOSB, Magazine
    capacity: int
    wafers: List[str]  # wafer IDs
    current_location: str
    status: CarrierStatus

class WaferHistory:
    """晶圆历史"""
    
    wafer_id: str
    lot_id: str
    events: List[ProcessEvent]  # 按时间排序
    
class ProcessEvent:
    """工艺事件"""
    
    event_id: str
    event_type: EventType
    equipment_id: str
    chamber_id: Optional[str]
    timestamp: datetime
    recipe_id: str
    parameters: Dict[str, Any]
    result: ProcessResult
    wafer_position: int
```

---

### 3.10 Security & Audit Layer

```python
class SecurityService:
    """安全服务"""
    
    # 认证授权
    async def authenticate(self, credentials: Credentials) -> AuthToken: ...
    async def authorize(self, token: AuthToken, action: Action) -> bool: ...
    
    # LDAP集成
    async def sync_with_ldap(self): ...
    
    # OAuth2/JWT
    def create_access_token(self, user: User) -> str: ...
    def verify_token(self, token: str) -> User: ...
    
class AuditLogger:
    """审计日志"""
    
    async def log_operation(self, 
                          user: str,
                          action: str,
                          resource: str,
                          details: Dict[str, Any]): ...
    
    async def log_recipe_change(self,
                               user: str,
                               recipe_id: str,
                               old_version: str,
                               new_version: str,
                               reason: str,
                               signature: str): ...
    
    async def log_data_access(self,
                             user: str,
                             data_type: str,
                             data_id: str): ...
    
    async def query_audit_log(self, 
                             filter: AuditFilter) -> List[AuditEntry]: ...

class ElectronicSignature:
    """电子签名 (21 CFR Part 11)"""
    
    async def request_signature(self, 
                              document: SignableDocument,
                              signatories: List[User]) -> SignatureRequest: ...
    
    async def sign(self, 
                  request_id: str,
                  user: str,
                  signature: str,
                  meaning: str) -> Signature: ...
    
    async def verify_signature(self, signature: Signature) -> bool: ...
```

---

### 3.11 Operations & Monitoring Layer

```python
class MonitoringDashboard:
    """监控仪表板"""
    
    async def get_fab_overview(self) -> FabOverview: ...
    async def get_equipment_status(self, 
                                  equipment_id: str) -> EquipmentDashboard: ...
    async def get_alarm_summary(self) -> AlarmSummary: ...
    async def get_throughput_metrics(self) -> ThroughputMetrics: ...
    
class ConfigManager:
    """配置管理器"""
    
    async def get_config(self, key: str) -> Any: ...
    async def set_config(self, key: str, value: Any): ...
    async def watch_config(self, key: str, callback: Callable): ...
    
class BackupManager:
    """备份管理器"""
    
    async def create_backup(self) -> str: ...  # 返回备份ID
    async def restore_backup(self, backup_id: str): ...
    async def list_backups(self) -> List[BackupInfo]: ...
    
class HAClusterManager:
    """高可用集群管理"""
    
    async def get_cluster_status(self) -> ClusterStatus: ...
    async def trigger_failover(self, reason: str): ...
    async def add_node(self, node: ClusterNode): ...
    async def remove_node(self, node_id: str): ...
```

---

## 4. 数据模型

### 4.1 核心实体

```sql
-- 设备
CREATE TABLE equipment (
    id UUID PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    equipment_type VARCHAR(50) NOT NULL,
    manufacturer VARCHAR(100),
    model VARCHAR(100),
    serial_number VARCHAR(100),
    ip_address VARCHAR(45),
    port INTEGER,
    status VARCHAR(20) DEFAULT 'UNKNOWN',
    capabilities JSONB,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 设备状态历史
CREATE TABLE equipment_status_history (
    id BIGSERIAL PRIMARY KEY,
    equipment_id UUID REFERENCES equipment(id),
    status VARCHAR(20) NOT NULL,
    sub_status VARCHAR(50),
    reason VARCHAR(255),
    timestamp TIMESTAMP DEFAULT NOW()
);

-- 工单
CREATE TABLE work_order (
    id UUID PRIMARY KEY,
    mes_id VARCHAR(100) UNIQUE NOT NULL,
    lot_id VARCHAR(100) NOT NULL,
    recipe_id UUID REFERENCES recipe(id),
    target_equipment_id UUID REFERENCES equipment(id),
    wafer_count INTEGER NOT NULL,
    priority INTEGER DEFAULT 5,
    status VARCHAR(20) DEFAULT 'PENDING',
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    metadata JSONB
);

-- 配方
CREATE TABLE recipe (
    id UUID PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    equipment_type VARCHAR(50) NOT NULL,
    version VARCHAR(20) NOT NULL,
    parent_version UUID REFERENCES recipe(id),
    parameters JSONB NOT NULL,
    steps JSONB NOT NULL,
    fdc_limits JSONB,
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    approved_by VARCHAR(100),
    approved_at TIMESTAMP,
    UNIQUE(name, equipment_type, version)
);

-- 报警
CREATE TABLE alarm (
    id UUID PRIMARY KEY,
    equipment_id UUID REFERENCES equipment(id),
    alarm_code VARCHAR(50) NOT NULL,
    alarm_text VARCHAR(500),
    severity VARCHAR(20) NOT NULL,
    raised_at TIMESTAMP DEFAULT NOW(),
    acknowledged_by VARCHAR(100),
    acknowledged_at TIMESTAMP,
    cleared_by VARCHAR(100),
    cleared_at TIMESTAMP,
    escalated BOOLEAN DEFAULT FALSE
);

-- 载具
CREATE TABLE carrier (
    id UUID PRIMARY KEY,
    carrier_id VARCHAR(100) UNIQUE NOT NULL,
    carrier_type VARCHAR(20) NOT NULL,
    capacity INTEGER NOT NULL,
    current_location VARCHAR(100),
    status VARCHAR(20) DEFAULT 'IDLE',
    created_at TIMESTAMP DEFAULT NOW()
);

-- 晶圆追踪
CREATE TABLE wafer_event (
    id BIGSERIAL PRIMARY KEY,
    wafer_id VARCHAR(100) NOT NULL,
    lot_id VARCHAR(100) NOT NULL,
    carrier_id UUID REFERENCES carrier(id),
    equipment_id UUID REFERENCES equipment(id),
    chamber_id VARCHAR(50),
    recipe_id UUID REFERENCES recipe(id),
    event_type VARCHAR(50) NOT NULL,
    wafer_position INTEGER,
    parameters JSONB,
    result JSONB,
    timestamp TIMESTAMP DEFAULT NOW()
);

-- 审计日志
CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id VARCHAR(100),
    details JSONB,
    ip_address VARCHAR(45),
    timestamp TIMESTAMP DEFAULT NOW()
);

-- SPC控制图数据
CREATE TABLE spc_data (
    id BIGSERIAL PRIMARY KEY,
    chart_id VARCHAR(100) NOT NULL,
    equipment_id UUID REFERENCES equipment(id),
    parameter_name VARCHAR(100) NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    timestamp TIMESTAMP DEFAULT NOW(),
    is_violation BOOLEAN DEFAULT FALSE,
    violation_rules VARCHAR(50)[]
);

-- FDC特征数据
CREATE TABLE fdc_features (
    id BIGSERIAL PRIMARY KEY,
    equipment_id UUID REFERENCES equipment(id),
    chamber_id VARCHAR(50),
    timestamp TIMESTAMP DEFAULT NOW(),
    features JSONB NOT NULL,
    anomaly_score DOUBLE PRECISION,
    is_anomaly BOOLEAN DEFAULT FALSE,
    fault_type VARCHAR(50)
);
```

### 4.2 时序数据（TimescaleDB）

```sql
-- 设备工艺数据（高频）
CREATE TABLE process_data (
    time TIMESTAMPTZ NOT NULL,
    equipment_id UUID NOT NULL,
    chamber_id VARCHAR(50),
    parameter_name VARCHAR(100) NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    unit VARCHAR(20)
);

SELECT create_hypertable('process_data', 'time', 
    chunk_time_interval => INTERVAL '1 hour');

-- 设备遥测数据
CREATE TABLE equipment_telemetry (
    time TIMESTAMPTZ NOT NULL,
    equipment_id UUID NOT NULL,
    temperature DOUBLE PRECISION,
    pressure DOUBLE PRECISION,
    humidity DOUBLE PRECISION,
    power_consumption DOUBLE PRECISION,
    vibration DOUBLE PRECISION
);

SELECT create_hypertable('equipment_telemetry', 'time',
    chunk_time_interval => INTERVAL '1 hour');
```

---

## 5. 接口定义

### 5.1 REST API

#### 设备管理
```
GET    /api/v1/equipment                    # 获取设备列表
GET    /api/v1/equipment/{id}              # 获取设备详情
POST   /api/v1/equipment                    # 注册设备
PUT    /api/v1/equipment/{id}               # 更新设备信息
DELETE /api/v1/equipment/{id}               # 删除设备
GET    /api/v1/equipment/{id}/status        # 获取设备状态
POST   /api/v1/equipment/{id}/command       # 发送设备命令
```

#### 工单管理
```
GET    /api/v1/work-orders                  # 获取工单列表
GET    /api/v1/work-orders/{id}             # 获取工单详情
POST   /api/v1/work-orders                  # 创建工单
PUT    /api/v1/work-orders/{id}             # 更新工单
POST   /api/v1/work-orders/{id}/pause       # 暂停工单
POST   /api/v1/work-orders/{id}/resume      # 恢复工单
POST   /api/v1/work-orders/{id}/cancel      # 取消工单
```

#### 配方管理
```
GET    /api/v1/recipes                      # 获取配方列表
GET    /api/v1/recipes/{id}                 # 获取配方详情
POST   /api/v1/recipes                      # 创建配方
PUT    /api/v1/recipes/{id}                 # 更新配方
DELETE /api/v1/recipes/{id}                 # 删除配方
POST   /api/v1/recipes/{id}/upload          # 上传配方到设备
POST   /api/v1/recipes/{id}/compare         # 比对配方版本
```

#### 报警管理
```
GET    /api/v1/alarms                       # 获取报警列表
GET    /api/v1/alarms/{id}                  # 获取报警详情
POST   /api/v1/alarms/{id}/acknowledge      # 确认报警
POST   /api/v1/alarms/{id}/clear            # 清除报警
POST   /api/v1/alarms/{id}/suppress         # 屏蔽报警
GET    /api/v1/alarms/statistics            # 报警统计
```

#### SPC/FDC
```
GET    /api/v1/spc/charts                   # 获取控制图列表
GET    /api/v1/spc/charts/{id}              # 获取控制图数据
POST   /api/v1/spc/charts                   # 创建控制图
GET    /api/v1/spc/capability/{param}       # 过程能力分析
GET    /api/v1/fdc/monitoring               # FDC监控状态
GET    /api/v1/fdc/anomalies                # 异常记录
POST   /api/v1/fdc/config                   # 配置FDC参数
```

#### 追踪
```
GET    /api/v1/tracking/wafer/{id}          # 晶圆追踪
GET    /api/v1/tracking/lot/{id}            # 批次追踪
GET    /api/v1/tracking/carrier/{id}        # 载具追踪
POST   /api/v1/tracking/carrier             # 注册载具
PUT    /api/v1/tracking/carrier/{id}/move   # 载具移动
```

#### 系统
```
GET    /api/v1/dashboard/overview           # 仪表板概览
GET    /api/v1/dashboard/equipment/{id}     # 设备仪表板
GET    /api/v1/system/health                # 系统健康状态
GET    /api/v1/system/metrics               # 系统指标
POST   /api/v1/system/backup               # 创建备份
```

### 5.2 WebSocket API

```javascript
// 实时事件订阅
const ws = new WebSocket('wss://eap.example.com/ws');

// 订阅设备状态变化
ws.send(JSON.stringify({
    action: 'subscribe',
    topic: 'equipment.status.*',
    equipmentIds: ['eq-001', 'eq-002']
}));

// 订阅报警
ws.send(JSON.stringify({
    action: 'subscribe',
    topic: 'alarm.#'
}));

// 订阅工艺数据
ws.send(JSON.stringify({
    action: 'subscribe',
    topic: 'process.data',
    equipmentId: 'eq-001',
    parameters: ['temperature', 'pressure']
}));

// 接收消息
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log(data.topic, data.payload);
};
```

### 5.3 Kafka Topic

```yaml
kafka_topics:
  # MES集成
  mes.work-order.received: "mes.work-order.received"
  mes.work-order.completed: "mes.work-order.completed"
  mes.equipment.status: "mes.equipment.status"
  mes.alarm.report: "mes.alarm.report"
  
  # 设备事件
  equipment.status.changed: "equipment.status.changed"
  equipment.alarm.raised: "equipment.alarm.raised"
  equipment.alarm.cleared: "equipment.alarm.cleared"
  equipment.process.started: "equipment.process.started"
  equipment.process.completed: "equipment.process.completed"
  
  # 工艺数据
  process.data.raw: "process.data.raw"
  process.data.fdc: "process.data.fdc"
  process.data.spc: "process.data.spc"
  
  # 追踪事件
  tracking.wafer.moved: "tracking.wafer.moved"
  tracking.carrier.arrived: "tracking.carrier.arrived"
  
  # 系统事件
  system.alert: "system.alert"
  system.health: "system.health"
```

---

## 6. 技术选型

### 6.1 核心框架

| 组件 | 技术选型 | 版本 | 说明 |
|------|----------|------|------|
| 语言 | Python | 3.11+ | async/await原生支持 |
| 框架 | FastAPI | 0.104+ | 高性能API框架 |
| 异步 | asyncio/aiohttp | - | 异步IO |
| ORM | SQLAlchemy 2.0 | 2.0+ | async ORM |
| 消息队列 | Apache Kafka | 3.6+ | 事件驱动架构 |
| 缓存 | Redis Cluster | 7.2+ | 状态缓存 |
| 时序数据库 | TimescaleDB | 2.12+ | 工艺数据存储 |
| 对象存储 | MinIO | 2023+ | S3兼容 |

### 6.2 SECS/GEM

| 组件 | 技术选型 | 说明 |
|------|----------|------|
| SECS库 | pycomm3 | 活跃维护的Python SECS库 |
| HSMS | 内置pycomm3 | 支持TCP/IP |
| GEM实现 | 自研 | 基于pycomm3封装 |

### 6.3 AI/ML

| 组件 | 技术选型 | 说明 |
|------|----------|------|
| 框架 | PyTorch | 深度学习模型 |
| 时序分析 | statsmodels | 统计SPC |
| 异常检测 | PyOD | 异常检测库 |
| 特征工程 | Featuretools | 自动特征工程 |
| 模型服务 | Triton | 高性能推理 |
| 实验跟踪 | MLflow | 实验管理 |

### 6.4 监控运维

| 组件 | 技术选型 | 说明 |
|------|----------|------|
| 容器编排 | Kubernetes | 1.28+ |
| 服务网格 | Istio | 流量管理 |
| 监控 | Prometheus + Grafana | 指标与可视化 |
| 日志 | Elasticsearch + Fluentd | 日志收集 |
| 追踪 | Jaeger | 分布式追踪 |
| CI/CD | ArgoCD | GitOps |

### 6.5 安全

| 组件 | 技术选型 | 说明 |
|------|----------|------|
| 认证 | OAuth2 + JWT | 访问控制 |
| LDAP | python-ldap | 目录集成 |
| 加密 | cryptography | 数据加密 |
| 证书 | cert-manager | TLS管理 |

---

## 7. 安全设计

### 7.1 认证授权架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Authentication Flow                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   User ──► OAuth2 Provider ──► Access Token ──► API Gateway        │
│              (LDAP/OIDC)                     │                        │
│                                               ▼                        │
│                                      ┌──────────────┐                │
│                                      │   JWT Token  │                │
│                                      │  Validation  │                │
│                                      └──────────────┘                │
│                                               │                        │
│                                               ▼                        │
│                                      ┌──────────────┐                │
│                                      │  Permission   │                │
│                                      │    Check      │                │
│                                      └──────────────┘                │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 7.2 零信任网络

- mTLS双向认证
- 设备证书管理
- 服务间认证
- 细粒度RBAC

### 7.3 合规支持

| 合规标准 | 支持功能 |
|----------|----------|
| FDA 21 CFR Part 11 | 电子签名、审计追踪、版本控制 |
| GDPR | 数据加密、访问控制、遗忘权 |
| SOC 2 | 安全日志、访问审计 |
| ISO 27001 | 信息安全管理系统 |

---

## 8. 部署架构

### 8.1 Kubernetes部署

```yaml
# 示例：设备Supervisor部署
apiVersion: apps/v1
kind: Deployment
metadata:
  name: equipment-supervisor-cleaner-001
  namespace: eap
spec:
  replicas: 2  # 主备模式
  selector:
    matchLabels:
      app: equipment-supervisor
      equipment: cleaner-001
  template:
    spec:
      containers:
      - name: supervisor
        image: eap/supervisor:latest
        env:
        - name: EQUIPMENT_ID
          value: "cleaner-001"
        - name: EQUIPMENT_TYPE
          value: "cleaner"
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchLabels:
                  equipment: cleaner-001
              topologyKey: kubernetes.io/hostname
```

### 8.2 高可用配置

```yaml
# Kafka集群配置
kafka:
  brokers: 3
  replication_factor: 3
  min_insync_replicas: 2

# PostgreSQL Citus分布式
postgresql:
  mode: distributed
  worker_nodes: 4
  replication_factor: 2

# Redis集群
redis:
  cluster_enabled: true
  shards: 6
  replicas_per_shard: 2
```

---

## 9. 实施计划

### Phase 1: 核心框架 (6个月)

| 周数 | 任务 | 交付物 |
|------|------|--------|
| 1-2 | 项目初始化、K8s集群搭建 | K8s集群 |
| 3-4 | SECS协议栈实现 | SECS库 |
| 5-8 | 设备连接管理 | 设备连接服务 |
| 9-12 | MES集成基础 | MES适配器 |
| 13-16 | 设备状态机 | 状态管理服务 |
| 17-20 | 基础报警管理 | 报警服务 |
| 21-24 | 测试与优化 | 核心系统 |

### Phase 2: 核心业务 (6个月)

| 周数 | 任务 | 交付物 |
|------|------|--------|
| 25-28 | 配方管理 | 配方服务 |
| 29-32 | 数据采集 | 数据收集服务 |
| 33-36 | 载具追踪 | 追踪服务 |
| 37-40 | 操作日志与审计 | 审计服务 |
| 41-44 | SPC引擎 | SPC服务 |
| 45-48 | 测试与集成 | 完整系统 |

### Phase 3: 高级功能 (6个月)

| 周数 | 任务 | 交付物 |
|------|------|--------|
| 49-52 | FDC引擎 | FDC服务 |
| 53-56 | 工艺流程引擎 | 流程服务 |
| 57-60 | 报警升级通知 | 通知服务 |
| 61-64 | 预测性维护基础 | 预测服务 |
| 65-68 | 良率预测基础 | 良率服务 |
| 69-72 | 数字孪生基础 | 孪生服务 |

### Phase 4: 企业级功能 (6个月)

| 周数 | 任务 | 交付物 |
|------|------|--------|
| 73-76 | AI模型训练平台 | ML平台 |
| 77-80 | 自适应控制 | 自适应服务 |
| 81-84 | 电子签名合规 | 合规模块 |
| 85-88 | 多Fab管理 | 多Fab支持 |
| 89-92 | 系统优化 | 性能调优 |
| 93-96 | 生产验证 | 生产部署 |

---

## 10. 附录

### 10.1 SEMI标准参考

| 标准 | 描述 |
|------|------|
| E4 | SEMI E4 - SEMI Equipment Communications Standard |
| E5 | SEMI E5 - SEMI Equipment Communications Standard 2 |
| E37 | SEMI E37 - HSMS Sideband Signal Server |
| E84 | SEMI E84 - Enhanced Carrier Handoff |
| E87 | SEMI E87 - Carrier Management |
| E90 | SEMI E90 - Substrate Tracking |
| E164 | SEMI E164 - E84 Extension for Equipment Constants |
| E179 | SEMI E179 - Equipment Performance Data Collection |
| E157 | SEMI E157 - Module Process Status |

### 10.2 参考商业产品

| 公司 | 产品 | 特色功能 |
|------|------|----------|
| Applied Materials | RAPID | AI驱动、数字孪生 |
| Brooks | Prima | 多设备协调、闭环控制 |
| KLA | Sigris | 良率管理、高级SPC |
| PDF Solutions | Genesis | 大数据分析、预测 |
| Inficon | Pilot | 薄膜设备专业控制 |

### 10.3 缩略语

| 缩写 | 全称 |
|------|------|
| EAP | Equipment Automation Program |
| SECS | Semiconductor Equipment Communication Standard |
| GEM | Generic Equipment Model |
| HSMS | High-Speed SECS Message Services |
| MES | Manufacturing Execution System |
| FDC | Fault Detection and Classification |
| SPC | Statistical Process Control |
| Cpk | Process Capability Index |
| RUL | Remaining Useful Life |
| MTBF | Mean Time Between Failures |
| MTTR | Mean Time To Repair |
| RDF | Rapid Defect Feedback |

---

*文档版本: 1.0*  
*最后更新: 2025-05-14*
