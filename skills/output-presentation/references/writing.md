# 清晰表达

`writing.profile` 支持 `plain` 与 `ste-inspired`。前者用于一般讲解；后者借鉴受控语言的短句、术语一致和明确动作原则。`ste-inspired` 不是 ASD-STE100 认证或完整规范检查，工具不会验证官方词典及全部语法规则。

## 改写内容

先写结论，再解释关系、原因与限制。每句尽量表达一个主要意思；过程说明使用明确的主体和动作。相同概念使用相同术语，首次出现时用 `glossary` 给出适合本主题的定义。消除不明确的指代，保留必要条件、概率措辞、数值、单位和否定。

由 Agent 把改写放入 `writing.summary` 和以文本块 ID 为键的 `writing.rewrites`。改写不替换 `result`；原文仍在基线和核验内容中。结构化图形事实应留在原始块中，不通过文字改写改变节点、边或数据值。根据用户困惑生成的 `adaptation.explanation_overrides` 优先于通用改写。

工具不自动把冗长文本改成短句。它只检查 Agent 已准备的文本，包括有效摘要、选中块的解释、步骤，以及视频旁白。需要保留术语表的定义唯一；同一术语不能出现多个定义。

## 句长检查

默认英文上限为 `plain` 25 词、`ste-inspired` 20 词；含中文句子的默认上限为 70 个非空白字符。可在 Spec 中设置 `max_sentence_words`（10–40）及 `max_sentence_chars`（30–120），适配读者和内容。

```json
{
  "writing": {
    "profile": "ste-inspired",
    "summary": "检索器先找到资料。模型再根据资料生成回答。回答仍需核验。",
    "rewrites": {
      "overview": "检索器寻找相关资料。生成模型使用资料与问题生成回答。"
    },
    "glossary": [
      {"term": "检索器", "definition": "寻找与问题相关资料的组件。"}
    ]
  }
}
```

检查命令：

```sh
python3 scripts/presentation.py lint-writing prepared.json spec.json -o writing-report.json
```

指定 `writing` 时，`render` 会拒绝超过所配置句长的内容。修正相应句子后再渲染，避免单纯调高阈值掩盖表达问题。报告中的 `semantic_review: requires_review` 提醒执行者核对语义；句子短并不能证明容易理解，也不能证明事实正确。
