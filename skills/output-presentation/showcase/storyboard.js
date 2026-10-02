window.SKILL_STORY = [
  {
    "title": "先明确看懂什么",
    "description": "把“解释一下”变成具体目标：分清哪个关系、找到什么依据、完成哪个判断。目标决定内容怎样组织。",
    "label": "GOAL",
    "english": "Give understanding a direction.",
    "visual": "<div class=\"flow\"><div class=\"floating-card\"><span class=\"card-title\">YOUR RESULT</span><h3>已有一份完整结果</h3><div class=\"line\"></div><div class=\"line short\"></div><div class=\"line medium\"></div></div><span class=\"arrow\">→</span><div class=\"floating-card blue\"><span class=\"card-title\">YOUR UNDERSTANDING</span><h3>你需要看懂什么？</h3><p>识别差异<br>找到依据<br>完成判断</p></div></div>"
  },
  {
    "title": "讲清楚，也能核验",
    "description": "解释视图帮你看懂结论；核验视图保留原始数据、引用和限制。两种视图，始终来自同一份结果。",
    "label": "VERIFY",
    "english": "Explain the result. Keep the evidence.",
    "visual": "<div class=\"dual\"><div class=\"floating-card\"><span class=\"card-title\">EXPLAIN</span><h3>看懂结论</h3><div class=\"line\"></div><div class=\"line medium\"></div><div class=\"line short\"></div><p>关系 · 比较 · 说明</p></div><div class=\"floating-card\"><span class=\"card-title\">VERIFY</span><h3>核验依据</h3><span class=\"check\">✓ 同一份结果</span><p>原始数据 · 来源 · 适用限制</p></div></div>"
  },
  {
    "title": "用一个反例，照亮边界",
    "description": "容易混淆的概念放在一起比较。用标注明确的教学反例，说明一种理解在哪里成立、在哪里失效。",
    "label": "CONTRAST",
    "english": "A counterexample makes the boundary clear.",
    "visual": "<div class=\"dual\"><div class=\"floating-card\"><span class=\"card-title\">THE MISUNDERSTANDING</span><div class=\"quote\">有输入，<br>就已成功？</div><p>输入相同，执行状态仍可能不同。</p></div><div class=\"floating-card blue\"><span class=\"card-title\">THE BOUNDARY</span><h3>有输入 ≠ 已执行<br>已调用 ≠ 已成功</h3><p>需要核对调用后的实际结果。<br>教学示例，不构成业务证据。</p></div></div>"
  },
  {
    "title": "接住下一步思考",
    "description": "比较、核验、改变假设、检查薄弱点。每一个操作都保留目标与上下文，生成可继续使用的完整任务。",
    "label": "CONTINUE",
    "english": "Turn the result into your next move.",
    "visual": "<div class=\"actions\"><div class=\"action\"><b>↔</b>比较两个方案</div><div class=\"action\"><b>◎</b>核验结论依据</div><div class=\"action\"><b>△</b>改变一个假设</div><div class=\"action\"><b>↗</b>检查薄弱环节</div></div>"
  },
  {
    "title": "更新时，先看真正的变化",
    "description": "结论改变、来源修订、限制新增，都能看见前后对照。沿用稳定定位，先理解变化，再查看完整新结果。",
    "label": "UPDATE",
    "english": "See what changed. Understand why it matters.",
    "visual": "<div class=\"diff\"><div class=\"diff-row\"><small>v1</small>展示上下文与工具的信息关系</div><div class=\"diff-row new\"><small>v2 +</small>成功结果仍需独立验证</div><div class=\"diff-row new\"><small>v2 +</small>来源说明已经修订</div></div>"
  },
  {
    "title": "围绕你的困惑重讲",
    "description": "已经懂的背景简化，还没看懂的关系重点解释。只使用当前会话中的明确反馈；理解检查可以接受，也可以跳过。",
    "label": "ADAPT",
    "english": "Re-explain the part that did not click.",
    "visual": "<div class=\"conversation\"><div class=\"bubble\">我懂输入，但为什么它不能证明成功？</div><div class=\"bubble answer\">相同的输入，可能尚未执行，也可能执行失败。要看调用之后的实际结果。</div></div>"
  }
];
