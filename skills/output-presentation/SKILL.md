---
name: output-presentation
description: 将已有任务结果转为适合用户理解、核验和继续使用的呈现；用于复杂关系解释、比较、结果更新或用户要求换一种形式表达。支持理解目标、解释与核验视图、对照反例、语义续接、版本差异及当前会话的理解适配。不用于原始业务研究、简单事实或已有 UI 修复。
metadata:
  author: liuyang
  version: "0.1.1"
---

# Output Presentation

接收已经形成的任务结果，根据用户目标、事实结构和实际可用能力组织呈现。保留业务事实、引用、单位和限制。下面六项都是首版能力；按任务适用性使用，不能用“不适用”掩盖能力缺失。

配套工具需要 Python 3.10+ 和 jsonschema 4；没有工具环境时仍可按指令规划，但需明确未执行验证。

## 开始

先确定用户要理解、核验或完成的具体任务，以及已有结果。不要为呈现引入新的业务结论。用户指定格式优先；不可用时报告缺失能力。通常生成一个主产物，带简短入口与必要核验内容。

简单事实不需要激活完整流程。复杂任务先把内容整理为 Request；[契约说明](references/contracts.md)定义输入、输出、示例与命令。处理自然语言结果时只提取明确提供的信息。

配套工具的路径以本 Skill 根目录为基准。调用前确认依赖，不能把未经检查的工具声明当作可用能力。

```sh
python3 scripts/presentation.py prepare request.json -o prepared.json
```

首次生成必须明确提供 `history_status: first`；有历史时为 `available` 并传 baseline，或为 `unavailable` 并报告无法比较。工具不会把漏传历史当作首次。

## 规划六项能力

1. **理解目标**：建立非空 `comprehension_goals`，区分用户目标和根据任务拟定的目标；把每个目标映射到内容区块和可观察的检查方法。内容覆盖不能冒充用户实际理解。
2. **双视图**：同一结果版本提供 explain 与 verify。核验视图包含原值、单位、来源、计算说明和不确定性；缺失依据明确展示。HTML 可用锚点与详情区，Markdown 用稳定编号，不必生成两个产物。
3. **对照反例**：复杂且容易误解的内容，提供具体对照、反例或类比失效说明。生成辅助必须标注“教学示例”或“假设示例”，列出假设并绑定目标概念；不可用作事实证据。简单任务可为空并说明理由。
4. **语义续接**：在适用目标上提供 compare、inspect_evidence、change_assumption、challenge。默认生成完整可复制任务，含版本、目标内容、依据与假设。改变假设创建独立 scenario，不覆盖真实结果；需要补证或重算时交回上游。支持自动回调的宿主需自行接入并核验；默认工具不会伪装发送事件。
5. **增量呈现**：比较授权的上一结果与当前版本，先展示结论、证据和限制的变化，再呈现完整结果。保留稳定 ID；不知道变化原因就明确写“原因未提供”。首次建立可恢复基线，有历史却无法读取时不能声称差异完整。
6. **理解适配**：仅用当前会话中有来源的已知概念、困惑、深度偏好和反馈，调整重点与解释深度。可针对反馈写 `explanation_overrides`，始终保留原文可核验。适用教学场景可提供理解检查，用户接受后再展示问题；允许跳过，不推断长期画像。

按实际需要读取：[呈现选择与信息组织](references/presentation-policy.md)、[教学与理解适配](references/learning.md)、[语义续接](references/actions.md)、[版本更新](references/versions.md)。不要默认加载全部参考资料。

## 验证与交付

生成 Presentation Spec 后运行：

```sh
python3 scripts/presentation.py validate spec spec.json --request prepared.json
python3 scripts/presentation.py render prepared.json spec.json --out-dir artifacts
```

配套 Renderer 只支持 Markdown 与离线 HTML。其他格式可由宿主已存在的 Renderer 实现；必须按其实际工具验证，不宣称配套 CLI 支持 PDF、视频或 Agent 回调。默认不生成完整候选产物竞赛。

`plan` 模式只交付有效 Spec。`render` 模式需要真实产物、六项适用检查、可恢复基线与可用续接任务。工具会生成 receipt、baseline、continuations 与产物，并回读核对保存结果。Receipt 区分静态保真检查和人工语义、视觉检查；后两项未经实际检查不能声称通过。

核验事实、引用、不确定性与学习示例标识；确认任务目标被覆盖、变化没有遗漏、用户反馈真实影响了说明。发布或发送由宿主按用户授权执行，本 Skill 不扩大权限。

失败时保留已有结果，报告 needs_input、needs_upstream_work 或 unsupported，不无限重试，也不把指定格式未满足报告为完成。[评测说明](references/evaluation.md)列出行为验收与真实用户效果边界。
