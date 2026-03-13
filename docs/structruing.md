# Python 知识图谱系统架构方案

## 1. 目标

构建一个基于 Python 的单机知识图谱系统，并最终封装为一个可安装的 `pip package` 名称为：endbrain（端脑）。使用者在实例化时传入持久化目录、内存上限，即可获得图谱的存储、加载、查询与内存治理能力。

本系统满足以下要求：

- 使用本地文件作为数据持久化介质
- 图谱运行态以“内存优先”方式提供查询与读写能力
- 可配置内存上限，但数据淘汰不只在超限时触发，而是持续综合评估数据价值
- 数据价值评估综合考虑访问时间、访问频次、权重、重要程度等因素
- 被判定淘汰的数据，需要同时从内存和本地持久化中移除
- 磁盘中的数据集合与内存中的数据集合保持一一映射与一致性
- 通过 Python 函数 API 按关键词查询实体、关系并返回 `0~1` 权重值
- 实体与关系都支持自定义结构的 `metadata` 数据包

## 2. 产品形态

最终形态建议如下：

- 交付方式：`pip package`
- 运行方式：单机、单进程、本地嵌入式调用
- 使用方式：业务代码中直接 `import` 后实例化
- 初始化方式：传入持久化目录、内存上限及可选配置

示意接口：

```python
from endbrain import EndBrain

eb = EndBrain(
    storage_dir="./data_store",
    memory_limit_mb=512,
)
```

说明：

- `storage_dir` 是唯一必填核心参数
- `memory_limit_mb` 控制运行时活跃图内存占用上限
- 磁盘数据与内存数据始终保持一致，不单独设计磁盘容量配额
- 包内部负责目录初始化、文件加载、索引构建、持久化与淘汰
- 不考虑集群、分布式、远程服务等场景

## 3. 总体设计原则

- 单机优先：只针对单机程序优化，不做分布式复杂设计
- 内存优先：查询和图遍历尽量全部在内存完成
- 文件一致：本地目录中的数据状态与内存中的图状态保持一致
- 包化交付：API 设计保持简洁，面向库调用而不是面向服务调用
- 自定义友好：实体和关系允许挂载任意结构的 `metadata`
- 主动治理：系统持续评估数据价值，而不是只在超限后被动淘汰
- 可控淘汰：基于多因子综合评分决定是否淘汰

## 4. 需求解释与关键取舍

你的需求现在可以归纳为三个关键点：

- 系统只控制内存大小，不单独控制磁盘大小
- 数据是否淘汰，不能只看是否超出限制，而要综合评估数据价值
- 一旦淘汰，内存和磁盘中的对应数据都必须同步删除，始终保持一致

因此，建议将运行语义定义为：

- 初始化时，系统从持久化目录加载图谱进入内存
- 内存中的图对象是运行态主视图
- 磁盘中的持久化文件是内存状态的镜像结果，而不是独立的冷存储池
- 系统持续根据对象的访问时间、访问频率、基础权重、重要程度、结构连接度综合判断是否保留
- 当对象被判定为应淘汰时，需要同时从活跃内存图和本地持久化中移除
- 当内存逼近阈值时，系统会提高淘汰动作的执行优先级，但淘汰判断本身不依赖于“是否超限”这一单一条件

也就是说：

- 内存限制决定治理压力
- 综合评分决定是否淘汰哪个对象
- 磁盘与内存一一映射，淘汰结果在两侧保持同步

这个定义最符合你现在的目标。

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
```

说明：

- `metadata.json`：系统配置、版本、统计信息
- `graph_snapshot.json`：最近一次图快照
- `entities.jsonl`：实体记录
- `relations.jsonl`：关系记录
- `wal/*.log`：增量变更日志

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
- 协调索引、持久化与淘汰

## 7.2 Storage 持久化层

职责：

- 将实体和关系写入本地文件
- 提供启动恢复能力
- 在淘汰和删除时同步更新持久化状态
- 保证磁盘状态与内存状态一致

建议采用“快照 + WAL + 记录文件”的本地文件方案：

- `entities.jsonl`
- `relations.jsonl`
- `graph_snapshot.json`
- `wal/*.log`

优势：

- 不依赖数据库
- 适合打包成轻量库
- 文本格式便于调试和迁移
- 方便保证内存与磁盘的一致性

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

## 7.5 Lifecycle Manager 生命周期治理层

职责：

- 估算当前对象内存占用
- 统计对象访问时间、访问频次、重要度和权重
- 定期计算对象综合保留分
- 判断对象是否应进入淘汰候选集
- 触发内存删除与持久化删除

## 8. 持久化设计

## 8.1 持久化原则

- 本地文件是内存图状态的持久化镜像
- 内存是运行态主视图
- 每次修改先记日志，再更新内存和持久化状态
- 定期生成快照减少恢复时间
- 被判定淘汰的数据，要从持久化文件中同步移除
- 磁盘中存在的数据，应与内存中当前保留的数据保持一致

## 8.2 文件格式建议

建议第一版采用：

- `JSONL` 保存实体和关系
- `JSON` 保存系统元信息和快照

原因：

- 兼容自定义 `metadata`
- 对 Python 非常友好
- 易于人工查看和问题排查

## 8.3 metadata 的持久化要求

由于实体和关系都支持自定义 `metadata` 数据包，存储层需要满足：

- 支持任意 JSON 可序列化结构
- 保持字段原样写入
- 读取后结构不丢失
- 不对业务字段做强约束

建议边界：

- 第一版只保证 `metadata` 为 JSON 可序列化对象
- 不支持函数、类实例、二进制对象等不可直接序列化内容

## 8.4 持久化删除策略

当对象被判定为淘汰时，持久化层需要同步执行删除动作。建议策略如下：

1. 在 WAL 中写入删除记录
2. 从内存对象表和索引中移除对象
3. 在下一次 `compact()` 或快照重建时，从实体和关系持久化文件中清除该对象
4. 清理其相关邻接关系和冗余索引记录

这样可以同时保证：

- 删除操作具备可恢复性
- 持久化最终状态与内存状态一致
- 文件不会长期累积已经淘汰的数据

## 9. 内存控制与淘汰设计

## 9.1 内存上限

实例化时传入，例如：

```python
eb = EndBrain(
    storage_dir="./data_store",
    memory_limit_mb=512,
)
```

建议提供两种配置：

- `memory_limit_mb`：用户可读配置
- 内部统一转换为 `memory_limit_bytes`

## 9.2 触发机制

淘汰不应只在超限时发生，建议采用“两级机制”：

- 常规巡检：周期性评估对象是否应该淘汰
- 压力触发：当内存逼近阈值时，立即加快淘汰执行

也就是说：

- 平时系统也会判断数据是否陈旧、低频、低价值
- 超限时只是让淘汰动作更积极，而不是改变淘汰逻辑本身

## 9.3 综合淘汰评分模型

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

- `recency_score`：最近访问时间，越陈旧越低
- `frequency_score`：访问次数，越低越容易淘汰
- `importance_score`：业务重要度，越低越容易淘汰
- `base_weight_score`：对象基础权重，越低越容易淘汰
- `topology_score`：图连接重要性，例如度数

淘汰策略：

- `retain_score` 越低，越优先淘汰
- 长期未访问、访问频次低、权重低、重要度低的数据优先淘汰
- 关系优先于实体淘汰
- 孤立实体优先于高连接实体淘汰

## 9.4 淘汰后的语义

淘汰表示对象被系统认定为不再保留。

淘汰动作包含：

- 从内存对象表移除
- 从索引移除
- 从邻接表移除
- 在 WAL 中写删除记录
- 在持久化整理阶段彻底移除对象记录
- 记录淘汰统计

因此，被淘汰对象最终不会继续保留在持久化中。

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
8. 启动后台或定时生命周期评估
9. 若内存压力过高，提高淘汰优先级

## 12.2 写入流程

1. 接收实体或关系写请求
2. 校验基础字段
3. 校验 `metadata` 是否可 JSON 序列化
4. 先写 WAL
5. 更新内存对象
6. 更新索引与邻接表
7. 更新对象生命周期统计
8. 检查内存压力
9. 必要时执行淘汰评估
10. 对被淘汰对象同步执行删除流程

## 12.3 查询流程

1. 接收关键词
2. 标准化关键词
3. 命中倒排索引
4. 计算候选对象权重
5. 更新访问时间与访问次数
6. 将对象重新纳入生命周期评分
7. 返回排序结果

## 13. 第一版实现建议

建议分三步推进：

### 阶段 1

- 完成包结构搭建
- 完成实体、关系、metadata 数据模型
- 完成本地目录初始化
- 完成 JSONL 持久化
- 完成内存加载与关键词查询

### 阶段 2

- 增加权重计算
- 增加访问统计
- 增加内存估算器
- 增加综合生命周期评分模型
- 增加淘汰判定与持久化删除流程

### 阶段 3

- 增加 WAL
- 增加快照
- 增加恢复与压缩能力
- 完善 pip package 对外接口

## 14. 建议你确认的点

在正式编码前，建议你确认下面几点：

1. 是否接受“被淘汰数据最终从持久化中彻底删除”
2. 是否接受持久化格式为 `JSONL + Snapshot + WAL`
3. `metadata` 是否只要求支持 JSON 可序列化结构
4. 第一版是否需要中文分词能力
5. 查询结果中是否需要原样返回 `metadata`

## 15. 推荐结论

基于你当前的约束，我建议第一版采用以下方案：

- 形态：单机、单进程、`pip package`
- 初始化：实例化时传入 `storage_dir`、`memory_limit_mb`
- 存储：本地文件 `JSONL + Snapshot + WAL`
- 生命周期治理：按访问时间、访问频次、权重、重要程度、连接度综合评分
- 淘汰语义：淘汰后同时从内存与持久化中移除
- 一致性要求：磁盘与内存中的数据集合一一映射并保持一致
- 查询：纯 Python 函数 API
- 数据扩展：实体和关系都支持自定义 `metadata` 数据包

如果你确认这份方案，我下一步就可以继续为你细化为：

- 包结构设计文档
- 数据模型定义文档
- API 规格文档
- 然后再开始编码实现
