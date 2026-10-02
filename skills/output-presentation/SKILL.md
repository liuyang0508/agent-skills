---
name: output-presentation
description: 将主题或任务结果转为清晰文字、SVG 图解、交互 HTML 或带字幕与本地配音的 MP4 讲解；用于复杂概念解释、关系与方案比较、结果更新或换一种形式理解。只给主题时先准备有来源的内容。支持核验、反例、续接和当前会话的理解适配；不用于简单事实或已有 UI 修复。
metadata:
  author: liuyang
  version: "0.2.0"
---

# Output Presentation

根据用户要理解的主题或已有任务结果，选择合适的讲解形式。文字帮助读懂，图解表达关系，网页支持探索，视频组织随时间展开的讲解。每种形式都保留事实、引用、单位和限制；六项理解能力共同贯穿其中。

配套工具需要 Python 3.10+ 与 `requirements.txt` 中的依赖。视频还需要本地媒体工具、字体与所选语言的语音。没有工具环境时可按指令规划，但应明确尚未生成或验证的产物。

## 开始

先确定用户要理解、核验或完成的具体任务、读者背景及指定格式。用户已有分析时，保留其结论与依据；用户只给主题时，由执行本 Skill 的 Agent 使用可用资料与研究工具准备有来源的内容，再进入呈现流程。明确区分来源事实、推断和教学假设；不能让渲染脚本补造内容。资料仍不足时先完成必要取证，或报告缺失项。

简单事实直接回答。复杂任务把准备好的内容整理为 Request；[契约说明](references/contracts.md)定义输入、输出、示例与命令。CLI 接受结构化 Request，不直接联网研究主题。用户指定格式优先；通常生成一个主产物，只有比较介质或用户明确要求时才生成多个。

配套工具路径以本 Skill 根目录为基准。先检查依赖；`doctor` 检查工具是否存在，实际渲染还要验证字体、语音与编码结果。

```sh
python3 scripts/presentation.py doctor
python3 scripts/presentation.py prepare request.json -o prepared.json
```

首次生成必须明确提供 `history_status: first`；有历史时为 `available` 并传 baseline，或为 `unavailable` 并报告无法比较。工具不会把漏传历史当作首次。

## 选择讲解形式

| 需要解决的问题 | 配套输出 | 规划重点 |
| --- | --- | --- |
| 读懂概念、说明和步骤 | `markdown` | 选择 `plain` 或 `ste-inspired`，改写短句并统一术语 |
| 看清依赖、流程或数据 | `svg` | 从依据提取节点、边、步骤或数值，实际生成图形 |
| 自己探索内容与依据 | `html` | 提供节点说明、搜索、对照和解释／核验切换 |
| 跟随过程逐步理解 | `mp4` | 为本次主题编排场景、画面、旁白和字幕 |

写作时读取[清晰表达](references/writing.md)；制作图解、网页或视频时读取[媒体制作](references/media.md)。`ste-inspired` 是启发式写作模式，不声明 ASD-STE100 合规。MP4 Renderer 提供内容驱动的二维关系、流程、图表和文字动画；三维、物理仿真或更复杂的视觉叙事需要适合的外部制作工具。

## 规划六项能力

1. **理解目标**：建立非空 `comprehension_goals`，区分用户目标和根据任务拟定的目标；把每个目标映射到内容区块和可观察的检查方法。内容覆盖不能冒充用户实际理解。
2. **双视图**：同一结果版本提供 explain 与 verify。核验视图包含原值、单位、来源、计算说明和不确定性；缺失依据明确展示。HTML 使用视图切换与原始结果区；Markdown 附依据与基线；SVG 和视频随附 `guide.html`。
3. **对照反例**：复杂且容易误解的内容，提供具体对照、反例或类比失效说明。生成辅助必须标注“教学示例”或“假设示例”，列出假设并绑定目标概念；不可用作事实证据。简单任务可为空并说明理由。
4. **语义续接**：在适用目标上提供 compare、inspect_evidence、change_assumption、challenge。HTML 可在本地展示对照或已有依据；默认仍可生成含版本、目标内容、依据与假设的完整任务。改变假设创建独立 scenario，需要补证或重算时交给 Agent；自动回调由宿主接入并核验。
5. **增量呈现**：比较授权的上一结果与当前版本，先展示结论、证据和限制的变化，再呈现完整结果。保留稳定 ID；不知道变化原因就明确写“原因未提供”。首次建立可恢复基线，有历史却无法读取时不能声称差异完整。
6. **理解适配**：仅用当前会话中有来源的已知概念、困惑、深度偏好和反馈，调整重点与解释深度。可针对反馈写 `explanation_overrides`，始终保留原文可核验。适用教学场景可提供理解检查，用户接受后再展示问题；允许跳过，不推断长期画像。

按实际需要读取：[呈现选择与信息组织](references/presentation-policy.md)、[教学与理解适配](references/learning.md)、[语义续接](references/actions.md)、[版本更新](references/versions.md)。不要默认加载全部参考资料。

## 验证与交付

生成 Presentation Spec 后运行：

```sh
python3 scripts/presentation.py validate spec spec.json --request prepared.json
python3 scripts/presentation.py render prepared.json spec.json --out-dir artifacts
```

配套 Renderer 支持 `markdown`、`svg`、`html`、`mp4`。指定 `writing` 时执行句长检查，生成 `writing-report.json`；视频还检查画面、字幕和所需语音流。其他格式或自动 Agent 回调由实际可用的宿主工具接入。

`plan` 模式交付有效 Spec。`render` 模式交付真实产物、六项适用检查、可恢复基线与可用续接任务。工具会保存 receipt、baseline、continuations 和产物。Receipt 区分工具检查与语义、视觉检查；实际打开产物、操作交互或播放视频后，才能报告相应验证结果。

核验事实、引用、不确定性与学习示例标识；确认任务目标被覆盖、变化没有遗漏、用户反馈真实影响了说明。发布或发送由宿主按用户授权执行，本 Skill 不扩大权限。

失败时保留已有结果，报告 needs_input、needs_upstream_work 或 unsupported，不无限重试，也不把指定格式未满足报告为完成。[评测说明](references/evaluation.md)列出行为验收与真实用户效果边界。
