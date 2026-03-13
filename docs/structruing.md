# Python 知识图谱系统架构方案

## 1. 目标

构建一个基于 Python 的单机知识图谱系统，并最终封装为一个可安装的 `pip package`。使用者在实例化时传入持久化目录、内存上限、物理存储上限，即可获得图谱的存储、加载、查询与资源治理能力。

本系统满足以下要求：

- 使用本地文件作为数据持久化介质
- 图谱运行态以“内存优先”方式提供查询与读写能力
- 可配置内存上限，当内存逼近上限时，根据读写时间、使用频次、重要程度自动淘汰低价值数据
- 可配置物理存储上限，当持久化目录逼近上限时，执行压缩、归档或清理策略
- 通过 Python 函数 API 按关键词查询实体、关系并返回 `0~1` 权重值
- 实体与关系都支持自定义结构的 `metadata` 数据包

## 2. 产品形态

最终形态建议如下：

- 交付方式：`pip package`
- 运行方式：单机、单进程、本地嵌入式调用
- 使用方式：业务代码中直接 `import` 后实例化
- 初始化方式：传入持久化目录、内存上限、物理存储上限及可选配置

示意接口：

```python
from endbrain import EndBrain

eb = EndBrain(
    storage_dir="./data_store",
    memory_limit_mb=512,
    storage_limit_mb=2048,
)
```

说明：

- `storage_dir` 是唯一必填核心参数
- `memory_limit_mb` 控制运行时活跃图内存占用上限
- `storage_limit_mb` 控制持久化目录磁盘占用上限
- 包内部负责目录初始化、文件加载、索引构建、持久化、淘汰与存储整理
- 不考虑集群、分布式、远程服务等场景

## 3. 总体设计原则

- 单机优先：只针对单机程序优化，不做分布式复杂设计
- 内存优先：查询和图遍历尽量全部在内存完成
- 文件可恢复：本地目录是持久化来源，实例重启后可恢复
- 包化交付：API 设计保持简洁，面向库调用而不是面向服务调用
- 自定义友好：实体和关系允许挂载任意结构的 `metadata`
- 双层约束：同时治理内存占用和物理存储占用
- 可控淘汰：不是简单 LRU，而是多因子综合淘汰

## 4. 需求解释与关键取舍

你的需求实际上包含两类资源限制：

- 运行时内存限制
- 持久化目录的物理存储限制

如果只限制内存、不限制本地持久化目录，系统虽然能控制运行时内存，但磁盘数据会持续增长，最终仍然失控。

因此建议将系统运行语义定义为“双层配额模型”：

- 初始化时，系统尽可能从持久化目录全量加载图谱进入内存
- 正常运行时，查询优先从内存完成
- 当内存超限时，系统会把低价值对象从活跃内存图中移除
- 被移除对象仍然保留在本地持久化目录中，必要时允许重新装入内存
- 当物理存储超限时，系统执行快照压缩、旧日志清理、低价值冷数据归档或删除策略

也就是说：

- 内存淘汰解决“运行态容量问题”
- 存储整理解决“持久化容量问题”

这个解释更适合单机包的长期运行模式，也更完整地覆盖你的真实需求。

## 5. 推荐目录结构

作为 `pip package`，建议工程内部按如下方式组织：

```text
project/
  docs/
    structruing.md
  src/
    endbrain/
      __init__.py
      graph.py
      config.py
      model/
      storage/
      index/
      memory/
      query/
      utils/
```

使用者传入的持久化目录建议结构：

```text
storage_dir/
  metadata.json
  graph_snapshot.json
  entities.jsonl
  relations.jsonl
  wal/
    000001.log
  archive/
```

说明：

- `metadata.json`：系统配置、版本、统计信息
- `graph_snapshot.json`：最近一次图快照
- `entities.jsonl`：实体记录
- `relations.jsonl`：关系记录
- `wal/*.log`：增量变更日志
- `archive/`：可选冷数据归档区

## 6. 核心对象模型

## 6.1 Entity 实体模型

建议字段：

- `id`：唯一 ID
- `name`：实体主名称
- `entity_type`：实体类型
- `keywords`：关键词列表
- `weight`：基础权重，范围 `0~1`
- `importance`：重要度，范围 `0~1`
- `metadata`：自定义结构数据包，类型建议为 `dict[str, Any]`
- `created_at`
- `updated_at`
- `last_access_at`
- `access_count`

其中 `metadata` 用于承载用户业务侧自由扩展字段，例如：

```python
{
    "source": "manual",
    "tags": ["language", "backend"],
    "confidence": 0.88,
    "extra": {
        "owner": "team-a"
    }
}
```

## 6.2 Relation 关系模型

建议字段：

- `id`
- `source_id`
- `target_id`
- `relation_type`
- `keywords`
- `weight`：基础权重，范围 `0~1`
- `importance`：重要度，范围 `0~1`
- `metadata`：自定义结构数据包，类型建议为 `dict[str, Any]`
- `created_at`
- `updated_at`
- `last_access_at`
- `access_count`

## 6.3 元信息模型

建议维护图谱级元数据：

- `memory_limit_bytes`
- `current_memory_bytes`
- `storage_limit_bytes`
- `current_storage_bytes`
- `snapshot_version`
- `last_snapshot_at`
- `eviction_count`
- `compaction_count`
- `package_version`

## 7. 核心模块设计

## 7.1 Graph Core

这是对外暴露的核心类，例如 `EndBrain`。

职责：

- 初始化持久化目录
- 加载快照和日志
- 管理内存图对象
- 暴露增删改查 API
- 协调索引、持久化、内存淘汰与存储整理

## 7.2 Storage 持久化层

职责：

- 将实体和关系写入本地文件
- 提供启动恢复能力
- 在淘汰和重载时提供对象读取能力
- 监控持久化目录大小
- 执行压缩、归档和清理

建议采用“快照 + WAL + 记录文件”的本地文件方案：

- `entities.jsonl`
- `relations.jsonl`
- `graph_snapshot.json`
- `wal/*.log`
- `archive/*`

优势：

- 不依赖数据库
- 适合打包成轻量库
- 文本格式便于调试和迁移
- 方便后续增加归档和压缩策略

## 7.3 In-Memory Graph 内存图层

建议维护以下结构：

- `entities_by_id: dict[str, Entity]`
- `relations_by_id: dict[str, Relation]`
- `adj_out: dict[str, set[str]]`
- `adj_in: dict[str, set[str]]`
- `entity_keyword_index: dict[str, set[str]]`
- `relation_keyword_index: dict[str, set[str]]`

作用：

- O(1) 级别访问实体和关系
- 支持关键词倒排检索
- 支持基于邻接关系的图遍历

## 7.4 Query 查询层

职责：

- 标准化关键词
- 从索引中找出候选实体和关系
- 计算匹配权重
- 返回统一格式结果

## 7.5 Memory Manager 内存治理层

职责：

- 估算当前对象内存占用
- 监控内存阈值
- 超限时执行批量淘汰
- 维护访问时间、频次、重要度相关统计

## 7.6 Storage Manager 存储治理层

职责：

- 统计持久化目录当前占用
- 判断是否逼近 `storage_limit_mb`
- 优先清理过期日志和冗余快照
- 对低价值冷数据执行归档或删除
- 输出存储治理统计信息

## 8. 持久化设计

## 8.1 持久化原则

- 本地文件是持久化唯一来源
- 内存是运行态视图
- 每次修改先记日志，再更新内存
- 定期生成快照减少恢复时间
- 定期执行压缩和整理，防止磁盘无限膨胀

## 8.2 文件格式建议

建议第一版采用：

- `JSONL` 保存实体和关系
- `JSON` 保存系统元信息和快照
- 可选压缩归档文件保存冷数据

原因：

- 兼容自定义 `metadata`
- 对 Python 非常友好
- 易于人工查看和问题排查
- 后续可平滑增加压缩归档能力

## 8.3 metadata 的持久化要求

由于实体和关系都支持自定义 `metadata` 数据包，存储层需要满足：

- 支持任意 JSON 可序列化结构
- 保持字段原样写入
- 读取后结构不丢失
- 不对业务字段做强约束

建议边界：

- 第一版只保证 `metadata` 为 JSON 可序列化对象
- 不支持函数、类实例、二进制对象等不可直接序列化内容

## 8.4 存储超限处理策略

当持久化目录接近或超过 `storage_limit_mb` 时，建议按顺序处理：

1. 清理已过期或已合并的 WAL 日志
2. 删除冗余旧快照
3. 压缩历史归档文件
4. 将低价值冷数据移入 `archive/`
5. 若仍超限，再删除超过保留策略的数据

建议默认优先“压缩和归档”，最后才“删除”。

## 9. 内存控制与淘汰设计

## 9.1 内存上限

实例化时传入，例如：

```python
eb = EndBrain(
    storage_dir="./data_store",
    memory_limit_mb=512,
    storage_limit_mb=2048,
)
```

建议提供两种配置：

- `memory_limit_mb`：用户可读配置
- 内部统一转换为 `memory_limit_bytes`

## 9.2 双阈值机制

建议使用：

- 软阈值：`85%`
- 硬阈值：`100%`

处理方式：

- 达到软阈值时，系统可提前准备淘汰候选集
- 达到硬阈值时，立即触发批量淘汰
- 一次淘汰到 `75%` 以下再停止，避免频繁抖动

## 9.3 淘汰评分模型

建议使用综合保留分，而非单一 LRU。

示意公式：

```text
retain_score =
  a * recency_score +
  b * frequency_score +
  c * importance_score +
  d * base_weight_score +
  e * topology_score
```

评分维度：

- `recency_score`：最近访问时间
- `frequency_score`：访问次数
- `importance_score`：业务重要度
- `base_weight_score`：对象基础权重
- `topology_score`：图连接重要性，例如度数

淘汰策略：

- `retain_score` 越低，越优先淘汰
- 关系优先于实体淘汰
- 孤立实体优先于高连接实体淘汰

## 9.4 淘汰后的语义

淘汰表示从内存活跃图中移除，不等于从磁盘删除。

淘汰动作包含：

- 从内存对象表移除
- 从索引移除
- 从邻接表移除
- 记录淘汰统计

数据仍在本地文件中保留，必要时允许重新装回内存。

## 10. 查询与权重设计

## 10.1 查询目标

系统提供通过关键词查询实体和关系的函数接口，并返回权重值 `0~1`。

## 10.2 查询 API 建议

```python
query_entities(keyword: str, top_k: int = 10) -> list[dict]
query_relations(keyword: str, top_k: int = 10) -> list[dict]
query_graph(keyword: str, top_k: int = 10) -> dict
```

## 10.3 权重组成

建议最终权重由三部分组成：

- 基础权重 `weight`
- 关键词匹配得分 `keyword_match_score`
- 重要度 `importance`

示意公式：

```text
final_weight = normalize(
  x * base_weight +
  y * keyword_match_score +
  z * importance
)
```

输出范围固定控制在 `0~1`。

## 10.4 实体评分维度

- 名称精确匹配
- 关键词精确匹配
- 前缀匹配
- 别名匹配
- `weight`
- `importance`

## 10.5 关系评分维度

- `relation_type` 命中
- 关系关键词命中
- 起点实体关键词相关性
- 终点实体关键词相关性
- `weight`
- `importance`

## 11. 包级 API 设计建议

面向 `pip package`，建议只暴露简洁的 Python API。

## 11.1 初始化 API

```python
EndBrain(
    storage_dir: str,
    memory_limit_mb: int = 512,
    storage_limit_mb: int = 2048,
    auto_load: bool = True,
)
```

## 11.2 写入 API

```python
add_entity(...)
add_relation(...)
update_entity(...)
update_relation(...)
delete_entity(...)
delete_relation(...)
```

## 11.3 查询 API

```python
query_entities(...)
query_relations(...)
query_graph(...)
get_entity(...)
get_relation(...)
```

## 11.4 运维型 API

```python
load()
flush()
compact()
archive()
get_stats()
```

## 11.5 返回结果建议

```python
[
    {
        "id": "entity_001",
        "name": "Python",
        "entity_type": "technology",
        "weight": 0.92,
        "metadata": {"source": "manual"},
        "match_reason": "keyword_exact"
    }
]
```

## 12. 启动与运行流程

## 12.1 初始化流程

1. 用户实例化 `EndBrain(storage_dir=...)`
2. 系统检查持久化目录是否存在，不存在则初始化
3. 读取 `metadata.json`
4. 加载快照与记录文件
5. 回放 WAL
6. 构建倒排索引和邻接表
7. 计算当前内存占用
8. 计算当前持久化目录占用
9. 若内存超限，执行一次冷启动淘汰
10. 若磁盘超限，执行一次启动整理

## 12.2 写入流程

1. 接收实体或关系写请求
2. 校验基础字段
3. 校验 `metadata` 是否可 JSON 序列化
4. 先写 WAL
5. 更新内存对象
6. 更新索引与邻接表
7. 检查内存阈值
8. 必要时执行淘汰
9. 检查存储阈值
10. 必要时执行压缩、归档或清理

## 12.3 查询流程

1. 接收关键词
2. 标准化关键词
3. 命中倒排索引
4. 计算候选对象权重
5. 更新访问时间与访问次数
6. 返回排序结果

## 13. 第一版实现建议

建议分三步推进：

### 阶段 1

- 完成包结构搭建
- 完成实体、关系、metadata 数据模型
- 完成本地目录初始化
- 完成 JSONL 持久化
- 完成内存加载与关键词查询
- 加入基础磁盘占用统计

### 阶段 2

- 增加权重计算
- 增加访问统计
- 增加内存估算器
- 增加多因子淘汰策略
- 增加存储上限监控

### 阶段 3

- 增加 WAL
- 增加快照
- 增加恢复与压缩能力
- 增加归档与清理策略
- 完善 pip package 对外接口

## 14. 建议你确认的点

在正式编码前，建议你确认下面几点：

1. 是否接受“淘汰后允许按需从本地文件重载”
2. 是否接受持久化格式为 `JSONL + Snapshot + WAL`
3. `metadata` 是否只要求支持 JSON 可序列化结构
4. 第一版是否需要中文分词能力
5. 查询结果中是否需要原样返回 `metadata`
6. 存储超限时是否优先归档而不是直接删除

## 15. 推荐结论

基于你当前的约束，我建议第一版采用以下方案：

- 形态：单机、单进程、`pip package`
- 初始化：实例化时传入 `storage_dir`、`memory_limit_mb`、`storage_limit_mb`
- 存储：本地文件 `JSONL + Snapshot + WAL`
- 内存结构：`dict + set + 倒排索引 + 邻接表`
- 内存治理：按访问时间、访问频次、重要程度、连接度综合评分淘汰
- 存储治理：按日志清理、快照压缩、冷数据归档、超限删除的顺序处理
- 查询：纯 Python 函数 API
- 数据扩展：实体和关系都支持自定义 `metadata` 数据包

如果你确认这份方案，我下一步就可以继续为你细化为：

- 包结构设计文档
- 数据模型定义文档
- API 规格文档
- 然后再开始编码实现
