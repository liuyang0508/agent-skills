# 图解、网页与视频

三个 Renderer 使用同一 Request 中的结构化内容。Agent 先规划关系和说明，再渲染真实产物；更换主题时需要重新准备内容与 Spec。参考同主题的 [SVG](../evals/fixtures/rag-svg-spec.json)、[HTML](../evals/fixtures/rag-html-spec.json) 与 [MP4](../evals/fixtures/rag-mp4-spec.json) 示例。

## SVG 图解

设 `presentation.format` 与 `render_request.renderer_id` 为 `svg`。至少需要一个关系、步骤、数据系列或对比块；仅有自然语言段落时，先从已有依据中提取适合图解的结构，不能凭空增加因果关系。

关系块使用带 ID 与标签的节点，以及带方向和标签的边。可提供节点 `definition`，供 HTML 说明区展示。步骤转换为有顺序的节点；数据系列保留单位、正负值和缺失项。优先在 `diagram` 或 `chart` section 中指定希望绘制的块。

每个关系／步骤块最多 36 个节点，数据系列最多 80 个点。大图先按理解目标拆分；标签过长或比较表过宽时，检查实际排版再交付。产物是可独立打开的 `presentation.svg`，附带 `guide.html` 保存完整依据、限制、原始结果与续接。

## 交互 HTML

设格式和 Renderer 为 `html`。生成的 `presentation.html` 自带样式、脚本及数据，无需远程前端资源。浏览器提供：

- 节点点击与键盘选择，展示概念说明、相邻关系、来源和限制。
- 内容搜索、节点强调和表格筛选。
- 解释／核验视图切换，查看完整原始结果。
- 本地对照或来源查看，以及可复制的完整后续任务。

`local` 语义操作只支持 compare 与 inspect_evidence。改变假设与 challenge 使用 prompt 续接；修改假设不会自动研究或重算。浏览器剪贴板不可用时，页面选择任务文字以供系统复制。详细行为见[语义续接](actions.md)。

打开真实文件检查窄屏、长标签、键盘导航及交互。输入正文不会作为 HTML 或脚本执行；自带交互代码由页面内容安全策略允许。

## 场景驱动 MP4

设格式和 Renderer 为 `mp4`。Agent 把本次主题规划成 1–12 个场景，并为每个场景写出有依据的标题、旁白和内容引用。每场景绑定一个结果块，所有场景合起来必须覆盖展示的所有块。图形高亮必须引用该块中的真实节点 ID。

```json
{
  "video": {
    "narration_mode": "local",
    "fps": 24,
    "scenes": [
      {
        "id": "flow",
        "title": "资料怎样进入回答",
        "source_block_ids": ["flow"],
        "highlight_node_ids": ["retriever", "generator"],
        "narration": "检索器取得相关资料。模型使用资料与问题生成回答。",
        "duration_seconds": 6
      }
    ]
  }
}
```

这是单个场景的字段示意；完整 Spec 仍需覆盖所有展示块与六项理解能力。

Renderer 以 1280 × 720 生成二维讲解：关系与步骤使用连线和节点强调，数据系列使用柱形变化，文本与对比内容使用文字画面。可用 `on_screen_text` 提炼屏幕文字，旁白承担进一步解释。视频关系块最多 12 个节点；复杂过程拆成聚焦的内容块和场景。它不提供任意三维场景、物理仿真或写实视频生成。

帧率可选 12、24、30，默认 24。场景指定时长为 1–45 秒；本地旁白较长时自动延长画面，但单场景超过 45 秒会停止并要求拆分。旁白中的教学反例要明确说明是假设，避免画面使其看起来像实测事实。

### 本地依赖与语音

需要 `ffmpeg`、`ffprobe`、Pillow 与本机可用的 Unicode 字体。字体应覆盖产物语言；中文环境可用系统中文字体或 Noto CJK。`doctor` 检查工具存在性，首次使用还需要生成短片，确认编码器、字体与语音实际可用。

`narration_mode: local` 使用 macOS `say` 或 `espeak-ng`；可通过 `voice` 选择本机声音。macOS 会按内容语言选择已安装的声音；缺少适用声音时先处理依赖。`silent` 必须明确写入 Spec，仍保留屏幕文字和字幕。配套脚本不调用付费语音 API。

### 交付与检查

视频目录包含 `presentation.mp4`、`presentation.srt`、`storyboard.json`、`video-checks.json` 和 `guide.html`，以及通用 receipt、baseline、continuations 与写作报告。MP4 有内嵌字幕轨，local 模式有音轨；`storyboard.json` 记录实际时长与音频存在状态。

`ffprobe` 检查媒体流后，还应播放视频，核对旁白、字幕、画面内容与节奏。随视频提供 guide 入口，读者可在那里查看依据、限制、反例和原始结果。依赖缺失或渲染失败时说明真实状态；分镜计划、代码或宣传动画不能替代可播放的主题视频。
