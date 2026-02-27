# QuLab Auto 系统详细设计文档

## 1. 项目概述

### 1.1 设计目标

构建一个 **LLM 驱动的量子实验自动化系统**，通过分层 Agent 协作实现实验自动化、知识沉淀和持续学习。

### 1.2 核心范式

- **Skill = 人类可读的实验策略说明书 + 可选的参考实现**，而非硬编码逻辑
- **主 Agent 不写代码**，只选择和配置 Skill
- **Executor Agent 不决策**，只忠实现现 Skill 描述的策略（控制硬件）
- **Analysis Agent 不控制硬件**，解析 Skill Markdown、生成代码、执行分析

### 1.3 现状与参考

**已有基础 (qulab.auto)**:
- ReAct 决策循环的 Agent 系统
- LLM 抽象层（OpenAI、Anthropic 支持）
- Skill 系统（YAML Frontmatter + Markdown）
- Tool 系统（测量、分析、查询等）
- 与 qulab.storage 集成

**参考实现 (nanobot)**:
- Pydantic 配置管理
- 事件总线架构
- Markdown Skill 系统
- 记忆整合机制
- 声明式 Provider Registry

---

## 2. 系统架构

### 2.1 三层 Agent 架构

```
Human (自然语言目标)
↓
[主 Planner Agent] (实验策略调度器)
├── 职责：目标理解、Skill 选择、参数策略、震荡检测
├── 读取：World Model（当前实验状态）
├── 写入：Audit Log（决策理由）
↓ (调用)
[Skill Executor Agent] (代码实现专家)
├── 职责：解析 Skill Markdown、生成代码、调试执行
├── 输入：Skill 文档 + 具体参数 + 设备接口
├── 输出：原始数据 → 保存到 Dataset
↓ (执行)
[Analysis Agent] (数据分析专家)
├── 职责：解析 Skill Markdown、生成代码、调试执行
├── 输入：Dataset + 分析 Skill
├── 输出：结构化结果 → 保存到 Document
↓
World Model 更新
```

### 2.2 模块架构

```
qulab/auto/
├── __init__.py              # 主入口
├── main.py                  # AutoLab 主类
├── config.py                # Pydantic 配置系统（参考 nanobot）
├── cli.py                   # 命令行接口
├── exceptions.py            # 异常定义
├── bus/                     # 消息总线（新增，参考 nanobot）
│   ├── __init__.py
│   └── queue.py             # 异步消息队列
├── agent/                   # Agent 系统
│   ├── __init__.py
│   ├── loop.py              # ReAct 决策循环
│   ├── planner.py           # Planner Agent（新增）
│   ├── executor.py          # Executor Agent（新增）
│   ├── analyzer.py          # Analysis Agent（新增）
│   ├── memory.py            # 记忆系统（强化）
│   └── context.py           # 上下文构建（参考 nanobot）
├── llm/                     # LLM 抽象层
│   ├── __init__.py
│   ├── base.py              # 抽象基类
│   ├── registry.py          # Provider 注册表（参考 nanobot）
│   └── providers/           # 各提供商实现
│       ├── openai.py
│       ├── anthropic.py
│       └── litellm.py       # 统一多提供商支持（新增）
├── skills/                  # Skill 系统
│   ├── __init__.py
│   ├── base.py              # Skill 基类
│   ├── loader.py            # 技能加载器
│   ├── parser.py            # Markdown/YAML 解析（新增）
│   ├── cache.py             # 代码缓存
│   ├── generator.py         # 代码生成器
│   ├── builtin/             # 内置技能
│   └── registry.py          # 技能注册表（新增）
├── tools/                   # 工具系统
│   ├── __init__.py
│   ├── base.py              # 工具基类
│   ├── registry.py          # 工具注册表
│   ├── measurement.py       # 测量工具
│   ├── analysis.py          # 分析工具
│   ├── query.py             # 查询工具
│   ├── config.py            # 配置工具
│   ├── human.py             # 人机交互工具
│   └── lesson.py            # 经验学习工具
├── world_model/             # 世界模型（新增）
│   ├── __init__.py
│   ├── base.py              # World Model 抽象
│   ├── parameter.py         # 参数管理
│   ├── state.py             # 实验状态
│   └── history.py           # 历史记录
└── executor/                # 代码执行器（新增）
    ├── __init__.py
    ├── base.py              # 执行器抽象
    ├── local.py             # 本地执行
    └── context.py           # 执行上下文
```

---

## 3. 核心组件设计

### 3.1 配置系统（参考 nanobot）

使用 Pydantic v2 进行类型安全的配置管理：

```python
# config.py
from pydantic import BaseModel, Field
from typing import Literal, Optional

class LLMConfig(BaseModel):
    provider: Literal["openai", "anthropic", "kimi", "deepseek"]
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: Optional[int] = None
    timeout: float = 120.0

class SkillConfig(BaseModel):
    paths: list[str] = Field(default_factory=list)
    cache_dir: str = "~/.qulab/skills/cache"
    max_retries: int = 3
    force_regenerate: bool = False

class ExecutorConfig(BaseModel):
    max_execution_time: float = 600.0
    enable_retry: bool = True
    max_retry_count: int = 3

class AutoLabConfig(BaseModel):
    llm: LLMConfig
    skills: SkillConfig = Field(default_factory=SkillConfig)
    executor: ExecutorConfig = Field(default_factory=ExecutorConfig)
    max_iterations: int = 40
    memory_window: int = 20
    enable_thinking: bool = True
```

### 3.2 消息总线（新增，参考 nanobot）

解耦模块间通信：

```python
# bus/queue.py
import asyncio
from typing import Callable, Any
from dataclasses import dataclass
from enum import Enum

class EventType(Enum):
    AGENT_THINKING = "agent.thinking"
    TOOL_CALL = "tool.call"
    TOOL_RESULT = "tool.result"
    SKILL_START = "skill.start"
    SKILL_COMPLETE = "skill.complete"
    SKILL_ERROR = "skill.error"
    HUMAN_QUERY = "human.query"
    CONFIG_UPDATE = "config.update"

@dataclass
class Event:
    type: EventType
    payload: dict[str, Any]
    session_id: str
    timestamp: float

class MessageBus:
    """异步消息总线，用于模块间解耦通信"""

    def __init__(self):
        self._subscribers: dict[EventType, list[Callable]] = {}
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        self._running = False

    def subscribe(self, event_type: EventType, handler: Callable):
        """订阅特定类型的事件"""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    async def publish(self, event: Event):
        """发布事件到总线"""
        await self._queue.put(event)

    async def start(self):
        """启动事件分发循环"""
        self._running = True
        while self._running:
            event = await self._queue.get()
            handlers = self._subscribers.get(event.type, [])
            for handler in handlers:
                try:
                    await handler(event)
                except Exception as e:
                    logger.error(f"Event handler error: {e}")
```

### 3.3 Agent 系统重构

#### 3.3.1 Planner Agent

负责高层策略决策：

```python
# agent/planner.py
class PlannerAgent:
    """
    策略层 Agent：理解实验目标，选择 Skill，调度子 Agent
    """

    def __init__(
        self,
        llm: LLMProvider,
        skill_registry: SkillRegistry,
        world_model: WorldModel,
        memory: SessionMemory,
        bus: MessageBus
    ):
        self.llm = llm
        self.skills = skill_registry
        self.world_model = world_model
        self.memory = memory
        self.bus = bus

    async def plan(self, goal: str, context: dict) -> Plan:
        """
        根据目标生成执行计划

        Returns:
            Plan: 包含步骤列表、依赖关系、回退策略
        """
        # 1. 从 World Model 获取当前状态
        state = self.world_model.get_state()

        # 2. 检索相关经验
        lessons = self.memory.query_lessons(goal)

        # 3. 选择合适的 Skills
        available_skills = self.skills.query_for_goal(goal)

        # 4. 构建决策提示词
        prompt = self._build_planning_prompt(
            goal=goal,
            state=state,
            lessons=lessons,
            skills=available_skills
        )

        # 5. LLM 决策
        response = await self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            tools=[self._select_skill_tool, self._decompose_goal_tool]
        )

        # 6. 解析执行计划
        plan = self._parse_plan(response)

        # 7. 发布计划事件
        await self.bus.publish(Event(
            type=EventType.PLAN_CREATED,
            payload={"plan": plan.to_dict()},
            session_id=context["session_id"],
            timestamp=time.time()
        ))

        return plan
```

#### 3.3.2 Executor Agent

负责执行实验 Skill（控制硬件）：

```python
# agent/executor.py
class ExecutorAgent:
    """
    执行层 Agent：解析实验 Skill Markdown，生成代码，调试执行
    职责：控制硬件，执行测量，生成原始数据
    """

    def __init__(
        self,
        llm: LLMProvider,
        code_generator: CodeGenerator,
        code_executor: CodeExecutor,
        storage: Storage,
        bus: MessageBus
    ):
        self.llm = llm
        self.generator = code_generator
        self.executor = code_executor
        self.storage = storage
        self.bus = bus

    async def execute(
        self,
        skill: Skill,
        parameters: dict,
        context: ExecutionContext
    ) -> ExecutionResult:
        """
        执行实验 Skill，包含代码生成、调试、执行的完整流程
        """
        # 1. 解析 Skill Markdown
        strategy = skill.parse_strategy()

        # 2. 检查前置条件
        if not self._check_prerequisites(strategy.prerequisites, context):
            return ExecutionResult(
                status="failed",
                reason="prerequisites_not_met"
            )

        # 3. 代码生成（带缓存）
        code = await self._generate_or_cache_code(skill, parameters)

        # 4. 执行-调试循环
        max_retries = context.config.max_retry_count
        for attempt in range(max_retries):
            try:
                # 执行代码（本地执行，非沙箱）
                result = await self.executor.execute(
                    code,
                    context,
                    timeout=context.config.max_execution_time
                )

                if result.success:
                    break

            except Exception as e:
                if attempt < max_retries - 1:
                    # 尝试修复代码
                    code = await self._fix_code(code, str(e), skill)
                else:
                    return ExecutionResult(
                        status="failed",
                        reason="max_retries_exceeded",
                        error=str(e)
                    )

        # 5. 保存原始数据到 Dataset
        dataset = await self._save_results(result, skill, parameters)

        return ExecutionResult(
            status="success",
            dataset_id=dataset.id
        )
```

#### 3.3.3 Analysis Agent

负责执行分析 Skill（数据处理）：

```python
# agent/analyzer.py
class AnalysisAgent:
    """
    分析层 Agent：解析分析 Skill Markdown，生成代码，调试执行
    职责：数据拟合、异常检测、生成语义化结果
    """

    def __init__(
        self,
        llm: LLMProvider,
        code_generator: CodeGenerator,
        code_executor: CodeExecutor,
        storage: Storage,
        bus: MessageBus
    ):
        self.llm = llm
        self.generator = code_generator
        self.executor = code_executor
        self.storage = storage
        self.bus = bus

    async def analyze(
        self,
        skill: Skill,
        dataset_ids: list[str],
        parameters: dict,
        context: AnalysisContext
    ) -> AnalysisResult:
        """
        执行分析 Skill，包含代码生成、调试、执行的完整流程
        """
        # 1. 解析 Skill Markdown
        strategy = skill.parse_strategy()

        # 2. 加载数据集
        datasets = [self.storage.get_dataset(ds_id) for ds_id in dataset_ids]

        # 3. 代码生成（带缓存）
        code = await self._generate_or_cache_code(skill, datasets, parameters)

        # 4. 执行-调试循环
        max_retries = context.config.max_retry_count
        for attempt in range(max_retries):
            try:
                # 执行代码
                result = await self.executor.execute(
                    code,
                    context,
                    timeout=context.config.max_execution_time
                )

                if result.success:
                    break

            except Exception as e:
                if attempt < max_retries - 1:
                    # 尝试修复代码
                    code = await self._fix_code(code, str(e), skill)
                else:
                    return AnalysisResult(
                        status="failed",
                        reason="max_retries_exceeded",
                        error=str(e)
                    )

        # 5. 结果结构化
        structured_result = await self._structure_result(
            result,
            skill.output_schema
        )

        # 6. 保存分析结果到 Document
        document = await self._save_analysis_result(
            structured_result,
            skill,
            dataset_ids,
            parameters
        )

        return AnalysisResult(
            status="success",
            document_id=document.id,
            parameters=structured_result
        )
```

### 3.4 Skill 系统增强

#### 3.4.1 Skill 文档格式（参考设计目标2.md）

```markdown
---
# Front Matter - 机器可读元数据
id: rabi_calibration_v2
type: experiment_skill  # experiment | analysis | meta
tags: [calibration, single_qubit, pulse]
requires:
  - qubit_frequency_known: true
produces:
  - pi_pulse_amplitude: { unit: V, confidence: high }
  - pi_pulse_duration: { unit: s, valid_for: 6h }
constraints:
  max_execution_time: 10m
inputs:
  - name: qubit_id
    type: string
    default: "Q1"
  - name: amp_range
    type: array
    default: [0.1, 0.5]
outputs:
  - name: qubit_frequency
    type: number
    unit: Hz
---

# 策略描述（Strategy）

## 目标
通过 Rabi 振荡实验确定 π 脉冲的振幅参数。

## 物理原理
在已知 qubit 频率的情况下，驱动 qubit 并扫描脉冲振幅，观测 Rabi 振荡。
当振荡周期确定时，振幅 = 半周期点。

## 执行步骤（自然语言）
1. 配置微波源频率为 qubit 频率（从 World Model 读取）
2. 生成振幅扫描序列：从 0V 开始，以 0.01V 步长扫描至 0.5V
3. 对每个振幅值：
   - 发送脉冲
   - 测量布居数
   - 记录结果
4. 拟合数据得到正弦曲线，提取 π 点振幅
5. 验证：检查拟合置信度 > 0.9，若低于阈值增加扫描点密度

## 参数调整策略
- **常规模式**：在 [0.1V, 0.5V] 内调整扫描范围
- **探索模式**（需授权）：若信号弱，可扩展至 [0.05V, 0.8V]

## 失败处理
- **拟合失败**：检查信噪比，若 SNR < 10dB，建议增加 averaging 次数
- **无振荡**：可能频率失谐，建议回退到 Spectroscopy Skill

---

# 参考实现（Reference Implementation）

## 伪代码
```python
def run_rabi(freq, amp_range, points=50):
    set_frequency(freq)
    amplitudes = linspace(amp_range[0], amp_range[1], points)
    results = []
    for amp in amplitudes:
        pulse = create_pulse(amplitude=amp, duration=100ns)
        pop = measure_population(pulse)
        results.append(pop)
    fit_result = sine_fit(amplitudes, results)
    pi_amp = fit_result.period / 2
    return {"pi_pulse_amplitude": pi_amp, "confidence": fit_result.r2}
```
```

#### 3.4.2 Skill 注册表（新增）

```python
# skills/registry.py
class SkillRegistry:
    """
    Skill 注册表，支持查询、匹配和依赖解析
    """

    def __init__(self, loader: SkillLoader):
        self.loader = loader
        self._skills: dict[str, Skill] = {}
        self._index: dict[str, list[str]] = {}  # tag -> skill_ids

    def load_all(self):
        """加载所有可用 Skill"""
        for skill_file in self.loader.discover():
            skill = self.loader.load(skill_file)
            self.register(skill)

    def register(self, skill: Skill):
        """注册 Skill 并更新索引"""
        self._skills[skill.id] = skill
        for tag in skill.tags:
            if tag not in self._index:
                self._index[tag] = []
            self._index[tag].append(skill.id)

    def query_for_goal(self, goal: str) -> list[Skill]:
        """根据目标描述检索相关 Skill"""
        # 1. 基于标签匹配
        # 2. 基于描述语义匹配
        # 3. 基于历史成功率排序
        pass

    def resolve_dependencies(self, skill: Skill) -> list[Skill]:
        """解析 Skill 的依赖链"""
        # 返回前置 Skill 列表
        pass
```

### 3.5 World Model（新增）

World Model 是系统的核心状态管理：

```python
# world_model/base.py
class WorldModel:
    """
    世界模型：维护实验参数、设备状态、历史记录的统一视图
    """

    def __init__(self, storage: Storage):
        self.storage = storage
        self.parameters = ParameterStore(storage)
        self.state = StateManager(storage)
        self.history = HistoryTracker(storage)

    def get_parameter(self, path: str) -> ParameterValue:
        """
        获取参数值

        Args:
            path: 参数路径，如 "qubit_1.frequency"

        Returns:
            ParameterValue: 包含 value、confidence、timestamp、source
        """
        return self.parameters.get(path)

    def set_parameter(
        self,
        path: str,
        value: Any,
        confidence: float,
        source: str
    ):
        """设置参数值"""
        self.parameters.set(path, value, confidence, source)

        # 记录到历史
        self.history.record({
            "type": "parameter_update",
            "path": path,
            "value": value,
            "confidence": confidence,
            "source": source
        })

# world_model/parameter.py
@dataclass
class ParameterValue:
    value: Any
    confidence: float  # 0-1
    timestamp: datetime
    source: str  # Skill ID 或 "human" 或 "calibration"
    valid_for: Optional[timedelta] = None  # 有效期

    def is_expired(self) -> bool:
        if self.valid_for is None:
            return False
        return datetime.now() - self.timestamp > self.valid_for
```

### 3.6 代码执行器（新增）

```python
# executor/base.py
class CodeExecutor:
    """
    代码执行器：在本地环境中执行生成的代码
    （暂不实现沙箱，依赖 Python 的 exec 执行）
    """

    def __init__(self, config: ExecutorConfig):
        self.config = config

    async def execute(
        self,
        code: str,
        context: ExecutionContext,
        timeout: float = 600.0
    ) -> ExecutionResult:
        """
        执行代码
        """
        # 创建执行上下文
        namespace = self._create_namespace(context)

        # 使用 asyncio.wait_for 实现超时控制
        try:
            # 在事件循环中执行
            result = await asyncio.wait_for(
                self._run_code(code, namespace),
                timeout=timeout
            )

            return ExecutionResult(
                success=True,
                data=result,
                namespace=namespace
            )
        except asyncio.TimeoutError:
            return ExecutionResult(
                success=False,
                error="Execution timeout"
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                error=str(e)
            )

    async def _run_code(self, code: str, namespace: dict):
        """实际执行代码"""
        exec(code, namespace)
        return namespace.get("result", None)

    def _create_namespace(self, context: ExecutionContext) -> dict:
        """创建执行命名空间，注入必要的上下文"""
        return {
            "np": numpy,
            "plt": matplotlib.pyplot,
            "storage": context.storage,
            "world_model": context.world_model,
            "__context__": context,
        }
```

### 3.7 记忆系统增强（参考 nanobot）

```python
# agent/memory.py
class SessionMemory:
    """
    双层记忆系统：
    - 短期记忆：完整对话历史（HISTORY）
    - 长期记忆：整合的经验事实（MEMORY）
    """

    def __init__(self, storage: Storage, llm: LLMProvider):
        self.storage = storage
        self.llm = llm
        self._consolidation_lock = asyncio.Lock()

    async def add_message(self, session_id: str, role: str, content: str):
        """添加消息到历史"""
        await self._append_history(session_id, role, content)

        # 检查是否需要整合
        history = await self._get_unconsolidated(session_id)
        if len(history) > self.memory_window:
            await self._consolidate(session_id, history)

    async def _consolidate(self, session_id: str, messages: list[Message]):
        """
        使用 LLM 整合历史消息到长期记忆
        """
        async with self._consolidation_lock:
            prompt = self._build_consolidation_prompt(messages)

            response = await self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                tools=[self._save_memory_tool]
            )

            # 更新 MEMORY.md
            if response.tool_calls:
                for call in response.tool_calls:
                    if call.name == "save_memory":
                        await self._update_memory(
                            session_id,
                            call.arguments["memory_update"]
                        )
```

---

## 4. Skill 执行流程

### 4.1 完整执行流程

```
Human Input
    ↓
[Planner Agent]
    - 理解目标
    - 查询 World Model
    - 选择 Skill
    - 生成 Plan
    ↓
[Executor Agent]
    - 解析实验 Skill Markdown
    - 生成/获取代码
    - 执行代码（硬件控制）
    - 调试循环（如出错）
    - 保存原始数据到 Dataset
    ↓
[Analysis Agent]
    - 解析分析 Skill Markdown
    - 生成/获取代码
    - 执行代码（数据处理）
    - 调试循环（如出错）
    - 生成结构化结果
    ↓
[World Model Update]
    - 更新参数
    - 记录历史
    - 保存执行记录
    ↓
[Human Feedback]（可选）
```

### 4.2 执行状态机

```
          ┌─────────────┐
          │   Pending   │
          └──────┬──────┘
                 │ Start
                 ↓
          ┌─────────────┐
          │  Planning   │
          └──────┬──────┘
                 │ Plan Ready
                 ↓
          ┌─────────────┐     Error      ┌──────────┐
          │  Executing  │───────────────→│ Retrying │
          └──────┬──────┘                └────┬─────┘
                 │ Success                    │
                 ↓                            │ Retry
          ┌─────────────┐                     │
          │  Analyzing  │←────────────────────┘
          └──────┬──────┘
                 │
         ┌──────┴──────┐
         ↓             ↓
   ┌──────────┐  ┌──────────┐
   │ Success  │  │  Failed  │
   └────┬─────┘  └────┬─────┘
        │             │
        ↓             ↓
   ┌──────────┐  ┌──────────┐
   │  Commit  │  │ Rollback │
   │  Result  │  │  & Log   │
   └──────────┘  └──────────┘
```

---

## 5. 与 qulab.storage 集成

### 5.1 数据集自动关联

```python
# tools/measurement.py
class MeasurementTool:
    async def execute(self, skill: Skill, parameters: dict, ...) -> ToolResult:
        # ... 执行测量 ...

        # 创建 Dataset
        dataset = self.storage.create_dataset(
            name=skill.name,
            description={
                "skill_id": skill.id,
                "parameters": parameters,
                "execution_id": execution_id
            },
            tags=[skill.id, "auto", skill.type],
            script=executed_code  # 保存执行的代码
        )

        # 填充数据
        for key, data in results.items():
            dataset.set_array(key, data)

        # 关联到 Document（如果生成报告）
        if analysis_result:
            doc = self.storage.create_document(
                name=f"{skill.name}_analysis",
                data=analysis_result,
                tags=[skill.id, "analysis"]
            )
            doc.add_dataset(dataset.id)
```

### 5.2 实验追溯

通过 Dataset 的 `script` 字段保存执行的代码，实现完整的实验追溯：

```python
# 追溯执行代码
dataset = storage.get_dataset(dataset_id)
executed_code = dataset.script  # 获取执行时的完整代码

# 追溯参数来源
description = dataset.description
skill_id = description["skill_id"]
parameters = description["parameters"]
```

---

## 6. 人机交互设计

### 6.1 交互流程

```
Agent: 正在执行 Skill: Rabi Calibration (v2)
       策略摘要: 扫描振幅 0.1V-0.5V，拟合 Rabi 振荡
       生成代码: [可展开查看 Python 代码]
       执行进度: 35/50 points (70%)
       预计剩余: 2分钟

Agent: 检测到拟合失败（置信度 0.3）
       根据 Skill 策略，建议增加 averaging 次数
       [应用建议] [保持当前] [申请探索模式]

Human: [点击"应用建议"]

Agent: 已调整参数，重新执行中...
```

### 6.2 Skill 热更新

```python
# skills/loader.py
class SkillLoader:
    def __init__(self):
        self._watcher = FileWatcher()  # 文件监控
        self._hot_reload = True

    def enable_hot_reload(self):
        """启用 Skill 热更新"""
        self._watcher.on_change(self._reload_skill)

    def _reload_skill(self, filepath: Path):
        """热重载单个 Skill"""
        skill = self.load(filepath)
        self.registry.register(skill)  # 覆盖旧版本
        logger.info(f"Hot reloaded skill: {skill.id}")
```

---

## 7. 实现路线图

### 阶段 1: 基础架构强化（1-2 周）

1. **配置系统迁移**
   - [ ] 使用 Pydantic v2 重构 config.py
   - [ ] 添加配置验证和默认值
   - [ ] 支持从文件和环境变量加载

2. **消息总线**
   - [ ] 实现基础 MessageBus
   - [ ] 定义核心事件类型
   - [ ] 集成到现有组件

3. **World Model 基础**
   - [ ] 实现 ParameterStore
   - [ ] 与 storage 集成
   - [ ] 添加基本查询接口

### 阶段 2: Agent 系统重构（2-3 周）

1. **Planner Agent**
   - [ ] 分离规划逻辑
   - [ ] 实现 Skill 选择策略
   - [ ] 添加依赖解析

2. **Executor Agent**
   - [ ] 强化代码生成
   - [ ] 实现调试循环
   - [ ] 集成 Dataset 保存

3. **Analysis Agent**
   - [ ] 解析 Skill Markdown
   - [ ] 代码生成与执行
   - [ ] 结果结构化与 Document 保存

### 阶段 3: 代码执行器（1 周）

1. **基础执行器**
   - [ ] 实现 CodeExecutor 基类
   - [ ] 本地执行环境
   - [ ] 超时控制

2. **执行上下文**
   - [ ] 注入必要库（numpy, matplotlib）
   - [ ] 注入 storage 接口
   - [ ] 注入 world_model 接口

### 阶段 4: Skill 系统完善（2-3 周）

1. **Skill 解析器**
   - [ ] Frontmatter 解析
   - [ ] 策略提取
   - [ ] 代码块提取

2. **Skill 注册表**
   - [ ] 索引和查询
   - [ ] 依赖解析
   - [ ] 版本管理

3. **内置 Skills**
   - [ ] 基础测量 Skills
   - [ ] 基础分析 Skills
   - [ ] Meta Skills

### 阶段 5: 集成与测试（2 周）

1. **集成测试**
   - [ ] End-to-end 测试
   - [ ] 性能测试

2. **文档与示例**
   - [ ] API 文档
   - [ ] Skill 编写指南
   - [ ] 使用示例

---

## 8. 关键设计决策

| 维度 | 决策 | 理由 |
|------|------|------|
| **配置管理** | Pydantic v2 | 类型安全、验证、序列化 |
| **模块通信** | 消息总线 | 解耦、可扩展、易测试 |
| **Skill 格式** | Markdown + YAML | 人类可读、易于编辑 |
| **代码执行** | 本地执行 | 简化实现，仪器调用暂不管 |
| **记忆系统** | 双层架构 | 平衡完整性和上下文长度 |
| **LLM 集成** | Provider Registry | 灵活支持多提供商 |
| **安全层** | 暂不实现 | 优先实现核心功能 |

---

## 9. 附录

### 9.1 参考文件

- 需求文档: `/Users/feihoo87/Projects/QuLab/设计目标2.md`
- 现有代码: `/Users/feihoo87/Projects/QuLab/qulab/auto/`
- 参考实现: `/Users/feihoo87/Projects/nanobot/`

### 9.2 相关模块

- qulab.storage: 数据存储和管理
- qulab.math: 数学和分析工具
- qulab.device: 仪器控制接口
