# 契约与运行

所有路径相对本 Skill 根目录，Python 3.10+；先在自己的环境安装 requirements.txt。三份 schemas 使用 JSON Schema 2020-12，无远程 $ref。脚本还做引用、版本、同意状态与六项保真检查；Schema 正确不代表业务事实正确。

Skill 版本为 0.2.0，契约的 `schema_version` 仍为 `1.0`。用户可以只给主题，但传入 CLI 前必须由 Agent 准备结构化结果及来源。CLI 不直接把主题扩写成研究结论。

## Request

查看 [RAG 请求示例](../evals/fixtures/rag-request.json) 和 [请求 Schema](../schemas/presentation-request.schema.json)。prepare 补齐目标和空学习信号，但必须明确 history_status：first、available、unavailable。available 时 baseline.result 是上一完整结果快照；first 与 unavailable 时 baseline=null。有历史无法获取，应生成 needs_input Spec，不交付伪造差异。

result.blocks 为 text（data.content）、comparison（columns 与同列的 rows）、series（unit 与 label/value 点，缺失 value=null）、relations（带 id/label 节点和 from/to/label 边）、steps（字符串 items）。空来源合法，但核验视图显示来源缺失。所有引用和限制 ID 必须解析，数值不得是 NaN 或 Infinity。

学习信号必须来自宿主给出的当前 session_refs；信号可有 block_ids 定位困惑。preferred_depth 是有来源信号或 null。check_consent 是 not_asked、accepted、declined，不从用户行为推断同意。

## Spec

参考 [文字 Spec](../evals/fixtures/rag-markdown-spec.json)、[图解 Spec](../evals/fixtures/rag-svg-spec.json)、[HTML Spec](../evals/fixtures/rag-html-spec.json)、[视频 Spec](../evals/fixtures/rag-mp4-spec.json) 和 [Schema](../schemas/presentation-spec.schema.json)。Agent 阅读 prepared Request 后规划 Spec；脚本不取代语义规划或自行创作教学反例。

selected 时六项字段必填。其他 decision 用 issues 列出 code/message/required_action，省略 selected 字段并保持 interactions=[]。source_field 只允许 result.summary；普通 section 引用块，生成教学辅助还用 learning_aid_ids。教学辅助所属概念必须可核验。

`python3 scripts/presentation.py changes prepared.json --spec spec.json -o change-set.json` 返回准确 change_set；把该对象放入 Spec。可先不传 --spec 计算变化，完成 goal_coverage 后重新计算 affected_goal_ids。

validate spec 必须传 --request，不能只用结构检查。需要新证据、明确格式不可用或历史缺失时选择对应阻塞状态。配套 CLI 的 `renderer_id` 与 `presentation.format` 必须一致，可为 `markdown`、`svg`、`html`、`mp4`，并出现在 Request 的 `capabilities.renderers` 中。实际依赖用 `doctor` 与渲染结果确认。

`writing` 可包含 `profile`、改写摘要 `summary`、按文本块 ID 的 `rewrites`、`glossary` 和句长上限。它不改变原始 result。`adaptation.explanation_overrides` 优先于通用写作改写。详细规则见[清晰表达](writing.md)。

MP4 必须提供 `video`：`narration_mode` 为 `local` 或 `silent`，并提供 1–12 个 `scenes`。每个场景包含唯一 `id`、`title`、`narration` 和恰好一个 `source_block_ids`，可选 `highlight_node_ids`、`duration_seconds`、`on_screen_text`；场景必须覆盖展示的所有结果块。详细限制与工具要求见[媒体制作](media.md)。

```sh
python3 scripts/presentation.py doctor
python3 scripts/presentation.py prepare evals/fixtures/rag-request.json -o /tmp/rag-prepared.json
python3 scripts/presentation.py validate spec evals/fixtures/rag-html-spec.json --request /tmp/rag-prepared.json
python3 scripts/presentation.py render /tmp/rag-prepared.json evals/fixtures/rag-html-spec.json --out-dir /tmp/rag-html
```

## Render Receipt

render 保存 `presentation.md`、`presentation.svg`、`presentation.html` 或 `presentation.mp4`，以及 `writing-report.json`、`continuations.json`、`baseline.json`、`receipt.json`。SVG 和 MP4 另附 `guide.html`；MP4 还保存 `presentation.srt`、`storyboard.json` 和 `video-checks.json`。视频带内嵌字幕轨，`local` 模式还必须有语音轨。重新呈现使用新的输出目录；不能覆盖不同内容的已有产物。基线只含结果与产物引用，不含用户学习信号。

Receipt 为 generated，因为人工语义与视觉检查仍需真实执行；validation_results 中对此标为 not_checked。Agent 打开并核验后可在交付说明中报告实际检查结果，不能随意把字段改成 passed。外部宿主 Renderer 按同一契约提供真实产物、保存回读与检查证据。

提供已有产物的基线文件时，宿主仅在具有读取授权且恢复验证通过后传回 baseline。不得只凭路径名称猜测版本。
