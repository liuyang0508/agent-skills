(() => {
  const scenes=[
    {title:'先确定，要完成什么。',description:'应用、账户、对象和目标明确以后再操作。只保存草稿的任务，在草稿结果上结束。',left:'USER REQUEST',lead:'保留标题。\n修改摘要与日期。\n保存为草稿。',right:'THE TASK BOUNDARY',result:'目标明确\n范围一致\n不自行发布',note:'直接用户指令决定范围'},
    {title:'从新界面，找到正确对象。',description:'使用当前工具允许的DOM、可访问性或截图。核对目标唯一、可操作，坐标与实际图像空间一致。',left:'A FRESH OBSERVATION',lead:'当前窗口与账户\n目标字段与状态\n同一帧的坐标',right:'LOCATE THE TARGET',result:'唯一对象\n正确字段\n有效坐标',note:'旧截图与旧编号不自动沿用'},
    {title:'短组操作，顺序完成。',description:'已经观察清楚的聚焦与输入可合并。遇到导航、弹窗和未知状态先观察；前一步失败后停止依赖它的动作。',left:'A SHORT ACTION GROUP',lead:'定位字段 → 输入\n填写日期 → 保存\n返回新的观察',right:'STOP ON FAILURE',result:'依赖顺序\n失败停下\n重新判断',note:'调用完成不等于目标已完成'},
    {title:'结果不明确，先看发生了什么。',description:'保存或提交超时，不代表没有生效。先回读对象；确认没有发生后，再决定如何重试。',left:'AN UNCERTAIN RESULT',lead:'未收到成功提示。\n已保存，还是没保存？\n先回读实际对象。',right:'AVOID DUPLICATE EFFECTS',result:'重开对象\n检查版本\n核对实际变化',note:'没有证据时不盲目重复提交'},
    {title:'保存以后，重新核对。',description:'字段回读、对象重开或文件检查，为最终结果提供证据。把验证过的结果交付给用户。',left:'VERIFY THE RESULT',lead:'摘要与日期一致。\n标题得到保留。\n状态仍然是草稿。',right:'CHECKABLE OUTCOME',result:'字段一致\n保存可回读\n范围内完成',note:'示例核验通过不外推所有应用'},
    {title:'留下证据，继续得上。',description:'长任务保留目标、对象、已验证结果、待处理副作用与原始事件。摘要不升级网页内容的可信度，也不替代授权。',left:'A GROUNDED HANDOFF',lead:'目标与真实对象\n已完成与未决事项\n证据与下一步',right:'KEEP THE SOURCE',result:'回引原始事件\n保持访问限制\n核对当前环境',note:'对话状态不等于环境仍然存在'}
  ];
  const stage=document.querySelector('#stage');const chapters=[...document.querySelectorAll('.chapter')];
  let current=0;let paused=matchMedia('(prefers-reduced-motion: reduce)').matches;let timer;
  function pane(label,text,blue){const node=document.createElement('article');node.className='stage-card'+(blue?' blue':'');const small=document.createElement('small');small.textContent=label;const p=document.createElement('p');p.textContent=text;node.append(small,p);return node;}
  function render(index){current=index;const s=scenes[index];stage.replaceChildren(pane(s.left,s.lead,false),pane(s.right,s.result,true));const note=document.createElement('div');note.className='stage-note';note.textContent=s.note;stage.append(note);document.querySelector('#stage-title').textContent=s.title;document.querySelector('#stage-description').textContent=s.description;document.querySelector('#stage-number').textContent=String(index+1).padStart(2,'0')+' / 06';chapters.forEach((c,i)=>c.setAttribute('aria-pressed',String(i===index)));}
  function controls(){const toggle=document.querySelector('#toggle');toggle.textContent=paused?'播放 ▷':'暂停 II';toggle.setAttribute('aria-label',paused?'播放自动讲解':'暂停自动讲解');clearInterval(timer);if(!paused)timer=setInterval(()=>{if(!document.hidden)render((current+1)%scenes.length);},4200);}
  chapters.forEach((button,index)=>button.addEventListener('click',()=>{render(index);controls();}));
  document.querySelector('#toggle').addEventListener('click',()=>{paused=!paused;controls();});
  chapters.forEach((button,index)=>button.addEventListener('keydown',event=>{if(!['ArrowUp','ArrowDown','ArrowLeft','ArrowRight'].includes(event.key))return;event.preventDefault();const delta=['ArrowDown','ArrowRight'].includes(event.key)?1:-1;const next=(index+delta+chapters.length)%chapters.length;chapters[next].focus();render(next);controls();}));
  render(0);controls();
})();
