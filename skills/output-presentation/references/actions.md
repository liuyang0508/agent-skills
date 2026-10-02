# 语义续接

四类 operation：compare 比较一致维度；inspect_evidence 查证依据；change_assumption 独立假设场景；challenge 检查结论与边界。每项绑定目标 block_ids、goal_ids、声明参数约束及交付方式。

配套 CLI 实现 prompt 模式。`continue` 生成包含原始目标数据、证据、限制、参数和结果版本的完整任务，不执行网络访问、业务研究或外部动作。把任务交给上游 Agent 时仍遵循用户授权。产物不包含失效按钮。

```sh
python3 scripts/presentation.py continue prepared.json spec.json a1 -o follow-up.json
```

parameter_constraints 的每项为允许值数组或局部 JSON Schema；未声明参数拒绝，Schema 不支持远程引用。required_parameters 声明必要参数，default_parameters 提供本次产物的具体初始值。change_assumption 必须有至少一个必填参数，通常为 assumption 字符串；为了直接渲染可用任务，需要同时提供具体默认假设。continue 的 --params 可覆盖默认值；缺失必填参数时停止，不交付空的假设任务。输出独立 scenario_id 并保留真实结果。CLI 只准备续接，不把假设任务当作已完成的模拟或重算。

宿主提供 local/agent 通道时按其工具实现，注册 artifact_id 与 result_ref/spec_id 并检查事件来源、允许列表、参数和版本。配套 CLI 不声称支持这些通道。用户明确要求自动执行时，prompt 降级不能满足该要求，必须报告 unsupported。
