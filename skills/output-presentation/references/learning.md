# 教学与理解适配

comprehension_goals 描述看完应能做什么，并用 success_criteria 描述可观察行为。goal_coverage 把目标绑定到实际 sections。实际用户回答与模型代理评分必须区分。

适用概念教学使用 contrast、counterexample、analogy_limit。generated 教学辅助必须标为教学示例或假设示例，带 assumptions，且 evidence_ids=[]；source 教学辅助必须带真实证据。所有辅助绑定 target_block_ids，并在解释 section 用 learning_aid_ids 放置。

用户要求教学对照时 intent.learning_aids_required=true；不能用“无需反例”逃避任务。不同概念的反例需由执行 Skill 的 Agent 基于已有内容创作和核验，不使用通用模板代替真实推理。

learner_context 的每条 known_concepts、confusions、feedback 和 preferred_depth 都有 source_ref，必须在当前会话可信 session_refs 中。只引用明确表达，不估计人格、能力或长期偏好。

针对 block_ids 定位的困惑或反馈，adaptation 必须引用信号、重点对应块，并在 explanation_overrides 写有针对性的新解释。覆盖只在 explain 生效，verify 始终展示原始数据。Agent 应判断改写是否忠于事实；脚本只能验证绑定和内容保留。

check_consent=accepted 时可以提供 questions（goal_id、question、answer_criteria）；declined 时不显示测验。offered 只能提供邀请，不提前展示问题。用户回答可用 feedback 命令记录本轮信号，下一次运行必须重新规划，而非原封不动使用旧 Spec。

```sh
python3 scripts/presentation.py feedback prepared.json --id f1 --text '还是不理解信息流方向' --source-ref message-2 --blocks b1 -o feedback-request.json
```

message-2 先由宿主作为当前用户消息加入 session_refs；不能由工具凭空认定它可信。未接受理解检查不妨碍正常解释与反馈适配。
