# 版本差异与基线

result_id 标识同一任务结果，revision 标识不可变快照。修改任何结果内容、证据或限制时使用新 revision。只根据当前反馈重新解释同一结果，可保留原 revision，但产生新的 spec_id 和输出目录。

首次 history_status=first；有可读取授权快照为 available；有历史但快照缺失为 unavailable。不能把未提供 baseline 当作首次。不同 result_id 的版本关系必须用一对一 id_map 显式说明；不要用文本相似度推测身份。

compute_changes 同时检查块、摘要、证据和不确定性。结论未改但来源撤回或限制新增，也要显示。每项 subject_ids 定位真正改变的记录，产物展示其旧值与新值，不能只展示未改变的关联块。summary_changed 是实施中补充的变化类型，用于无块绑定的上游摘要。affected_goal_ids 由覆盖映射计算，不能猜测影响。change_reasons 由上游提供，不存在时写“原因未提供”。

render 保存 baseline.json 并实际恢复比对。下一次由宿主读取该文件，把完整对象作为 Request.baseline，history_status 改为 available。文件路径只是产物定位，恢复后的内容才是依据。

产物默认先展示差异，再展示完整最新结果。静态文件可以重建，但保留内容 ID 和差异，不能因此丢掉增量体验。新增、删除、证据变动与局部理解反馈都需测试。baseline 不保存用户学习信号；宿主按自己的授权范围维护历史，不在本 Skill 内构建长期存储系统。
