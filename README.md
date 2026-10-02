# Agent Skills

把复杂任务变成可复用的能力。由 [liuyang](https://github.com/liuyang0508) 创作的个人 Skill 合集，每个 Skill 都有动态讲解、完整示例和独立安装包。

[![Output Presentation：六步动态讲解](skills/output-presentation/showcase/demo.gif)](https://liuyang0508.github.io/agent-skills/skills/output-presentation/showcase/)

**[观看动态讲解 ↗](https://liuyang0508.github.io/agent-skills/skills/output-presentation/showcase/) · [浏览 Skill 合集 ↗](https://liuyang0508.github.io/agent-skills/)**

| Skill | 用途 | 版本 |
| --- | --- | --- |
| [output-presentation](skills/output-presentation/SKILL.md) | 让结果被看懂：解释、核验、继续思考与版本更新 | 0.1.1 |

## 安装

克隆仓库后，将 `skills/output-presentation` 目录复制到你所用 Agent 的 Skill 搜索目录。实际搜索路径以该 Agent 的配置为准。只需安装这个目录，不必安装整个合集。

```sh
git clone https://github.com/liuyang0508/agent-skills.git
cd agent-skills
python3 -m venv .venv
.venv/bin/python -m pip install -r skills/output-presentation/requirements.txt
```

Skill 指令可由兼容 `SKILL.md` 的 Agent 读取。配套 Python 工具负责确定性契约、差异、续接与呈现；信息架构、反例创作和解释改写由执行 Skill 的 Agent 完成。

## 运行示例

```sh
.venv/bin/python skills/output-presentation/scripts/presentation.py prepare skills/output-presentation/evals/fixtures/architecture-request.json -o /tmp/presentation-request.json
.venv/bin/python skills/output-presentation/scripts/presentation.py render /tmp/presentation-request.json skills/output-presentation/evals/fixtures/architecture-spec.json --out-dir /tmp/presentation-demo
.venv/bin/python -m unittest discover -s skills/output-presentation/evals -v
```

产物包括 Markdown、离线 HTML、完整后续任务和版本基线。自动连接上游 Agent 的回调，由你的运行环境接入。

另有 [教学与版本更新请求](skills/output-presentation/evals/fixtures/learning-update-request.json) 和 [完整 Spec](skills/output-presentation/evals/fixtures/learning-update-spec.json)，演示来源修订、限制新增、具体教学反例、四类续接、接受理解检查和反馈后的局部重讲。这些内容是教学示例，不是实测业务结论。

## 六项能力

| 能力 | 帮你完成什么 |
| --- | --- |
| 理解目标 | 先明确看完需要理解的关系和判断 |
| 解释与核验 | 读懂结论，也能找到原始依据和限制 |
| 对照与反例 | 识别容易混淆的概念，看到边界在哪里 |
| 继续思考 | 比较、核验、改变假设、检查薄弱环节 |
| 版本更新 | 先看新旧差异，再看完整最新结果 |
| 理解适配 | 围绕当前困惑重讲，跳过已经懂的背景 |

每个 Skill 的 `showcase/` 都包含动画预览、静态封面和可暂停的交互讲解页；完整目录可以独立复制使用。

本仓库采用 MIT 许可证。
