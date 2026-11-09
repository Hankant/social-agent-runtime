# social-agent-runtime

面向现有 LLM 多 agent 框架的工程稳健性支援 Skill。

用于接入和维护并发调度、限流控制、预算台账、成功缓存、断点恢复、日志诊断与离线故障测试。它源于多 agent 模拟项目的实际工程经验，不依赖 SocioVerse2，也不设计研究题目、人群或行为机制。

## 定位与当前能力

采用 **Skill 操作流程 + 小型可复用代码组件 + 离线测试** 的形式。

| 能力 | 当前交付形式 |
|---|---|
| 工程接入、执行一致性和状态所有权检查 | Skill 与参考文档 |
| 有界滚动并发、稳定返回、失败收尾 | `assets/bounded_batch.py` 可运行组件 |
| 规范化请求日志的吞吐与 token 汇总 | `scripts/summarize_events.py` 可运行工具 |
| 限流、预算、持久缓存和断点恢复 | 接口合同、实现要求及故障矩阵；需适配目标项目 |
| 分层验证器：真值隔离、负对照、恢复检查与真人留出边界 | [接入规范](references/validator.md)及[验证计划模板](assets/validation-plan.md)，需适配指标和生成器；未附通用统计引擎 |
| 基础组件正确性 | 12 项标准库离线测试 |

当前不是完整的生产运行引擎。没有附带 API 客户端、持久预算存储、限流器或完整检查点管理器；不承诺安装后自动获得这些能力。也尚未完成多个独立框架的集成验证。

## 安装到 Codex

在终端中执行（已安装 Git）：

```sh
git clone https://github.com/Hankant/social-agent-runtime.git ~/.codex/skills/social-agent-runtime
```

Windows PowerShell：

```powershell
git clone https://github.com/Hankant/social-agent-runtime.git "$env:USERPROFILE\.codex\skills\social-agent-runtime"
```

如果使用自定义 `CODEX_HOME`，将仓库放在该目录的 `skills/social-agent-runtime`。目标已存在时，先检查现有内容，不直接覆盖。

若当前会话未发现新 skill，打开新会话后显式调用。

## 使用

```text
使用 $social-agent-runtime 检查当前框架的并发、限流、预算、缓存、恢复和日志。
保持已有模型规则，先给代码与日志证据，再实施工程修改并离线验证。
```

也可以针对具体问题：

- “增加有界并发，保留串行版本的提交顺序和恢复语义。”
- “排查 429 后长期降速，检查同波失败、SDK 重试和恢复门控。”
- “检查重启是否重复调用已成功任务，以及预算和尝试次数是否继承。”
- “分析实际请求中的 token，分开输入、输出、重试、缓存和未知 usage。”
- “为项目接入验证器，分离生成器、被测系统与评价器，先测零效应误报和已知差异恢复，不把合成显著性当现实证明。”

Skill 默认先检查已有项目，不会因为审查请求而自动启动付费任务。是否继续真实请求、如何处理个人失败和未决结果，遵守用户及目标项目的授权。

## 测试

代码组件与工具仅使用 Python 标准库，支持 Python 3.10+。在仓库根目录运行：

```sh
python -B -m unittest discover -s scripts -p "test_*.py" -v
```

测试不访问模型、网络或凭据。覆盖：串行/并发顺序、输入隔离、实际并行与在途上限、滚动补位、全局失败后不补位、成功结果收尾、写入失败、缓存复用示例、用量未知、缓存重放计数和命令行工具。

这些是基础组件测试，不是目标项目的生产集成证明。完整故障矩阵见 [verification.md](references/verification.md)。

## 仓库结构

```text
SKILL.md                         Skill 入口
agents/openai.yaml               显示名称与调用提示
assets/bounded_batch.py          有界并发基础组件
assets/validation-plan.md        目标项目验证计划模板
scripts/summarize_events.py      规范化 JSONL 离线汇总
scripts/test_*.py                离线测试
references/architecture-review.md 工程接入检查
references/runtime-contract.md  执行、恢复、限流及预算合同
references/verification.md      故障矩阵、性能与用量测量
references/validator.md         验证器接入、合成检查与证据分层
references/origin.md            来源与维护边界
```

`summarize_events.py` 需要按文档规范化后的逐请求 JSONL，不能直接解析任意框架日志。具体字段和示例见 [verification.md](references/verification.md)。

## 维护与贡献

工程组件与题目规则分离；新增 adapter 应有假客户端与故障测试，不需要真实 Key。同步和异步系统分别保持其原有语义，不为了复用而强制改写。

提交改动时说明接口变化、故障证据、测试与兼容性。不提交真实账户资料、实验请求、密钥、认证头、DPAPI 凭据或本机运行缓存。报告问题时提供已筛查的最小复现和错误元数据。

许可：[MIT](LICENSE)。本仓库不附带第三方模拟框架。
