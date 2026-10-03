# Codex-Harness：工具调用怎样执行？

沿 OpenAI Codex 固定公开提交 `da2e174a66a6572204a91373321b7d22d87fb12e`（2026-10-01），讲解模型调用、工具分派、命令执行检查与结果回流。用同一份来源生成文字、SVG、交互 HTML 和旁白视频。

[体验案例](https://liuyang0508.github.io/agent-skills/examples/codex-harness/) · [完整输入](source/request.json) · [文字](markdown/presentation.md)

这是源码讲解和教学示例，没有实际运行命令或修改文件。命令类工具仅作为重点路径；图中省略并行、取消、抢占与部分异常。模型提出调用、策略允许执行和业务目标完成需要分别核验。

在本 Skill 的目录（`output-presentation`）中、已准备 Python 与媒体依赖的环境下生成：

```sh
python3 examples/understanding/build.py \
  --source-dir examples/codex-harness/source \
  --out-dir /tmp/codex-harness-demo
```

输出目录必须是新目录，已有产物会保留。

[使用与安装说明](../../README.md)
