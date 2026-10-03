# Agent Skills

由 [liuyang](https://github.com/liuyang0508) 创作和维护的个人 Skill 合集。每个 Skill 独立组织，提供用途说明、动态讲解、示例与安装指引，可按需选择使用。

[浏览 Skill 合集 ↗](https://liuyang0508.github.io/agent-skills/)

## Skill 目录

| Skill | 用途 | 版本 | 演示与示例 |
| --- | --- | --- | --- |
| [output-presentation](skills/output-presentation/README.md) | 将复杂主题和任务结果转成易读、可核验的内容 | 0.2.0 | [动态讲解](https://liuyang0508.github.io/agent-skills/skills/output-presentation/showcase/) · [完整示例](https://liuyang0508.github.io/agent-skills/skills/output-presentation/examples/understanding/) |
| [computer-use](skills/computer-use/README.md) | 在授权范围内完成浏览器与桌面操作，并核验真实结果 | 0.1.2 | [动态讲解](https://liuyang0508.github.io/agent-skills/skills/computer-use/showcase/) · [实际工作台](https://liuyang0508.github.io/agent-skills/skills/computer-use/examples/draft-workbench/) |

## 安装

1. 获取合集仓库：

   ```sh
   git clone https://github.com/liuyang0508/agent-skills.git
   ```

2. 从目录中选择所需 Skill，阅读它自己的 README，确认用途、依赖与运行方式。
3. 将选定的 `skills/<skill-name>` 完整目录复制到你所用 Agent 的 Skill 搜索目录。实际搜索路径以该 Agent 的配置为准。

每个 Skill 可单独安装。工具依赖、环境配置与使用示例见各自 README。

## 目录约定

- `skills/<skill-name>/README.md`：面向使用者的介绍、演示、安装与示例。
- `skills/<skill-name>/SKILL.md`：面向 Agent 的触发条件与执行规范。
- 脚本、参考资料和示例按需放在同一 Skill 目录中，使完整目录可独立复制使用。

## 许可证

本合集采用 [MIT 许可证](LICENSE)。
