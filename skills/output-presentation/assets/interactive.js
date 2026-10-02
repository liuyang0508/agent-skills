'use strict';
const data=JSON.parse(document.querySelector('#presentation-data').textContent);
const result=data.result,blocks=new Map(data.blocks.map(b=>[b.id,b]));
const task=document.querySelector('#task'),status=document.querySelector('#status');
let activeTask=null;
function setView(view){['explain','verify'].forEach(name=>{document.querySelector('#'+name).hidden=name!==view;document.querySelector('#'+name+'-tab').setAttribute('aria-selected',String(name===view));});}
['explain','verify'].forEach(name=>document.querySelector('#'+name+'-tab').addEventListener('click',()=>setView(name)));
document.querySelectorAll('[role=tab]').forEach(tab=>tab.addEventListener('keydown',event=>{if(event.key==='ArrowLeft'||event.key==='ArrowRight'){const next=tab.id==='explain-tab'?'verify':'explain';setView(next);document.querySelector('#'+next+'-tab').focus();}}));
function inspectNode(element){
  document.querySelectorAll('.diagram-node').forEach(node=>node.classList.toggle('selected',node===element));
  const block=blocks.get(element.dataset.blockId);if(!block)return;
  const detail=document.querySelector('#node-detail');detail.replaceChildren();
  const node=(block.data.nodes||[]).find(n=>n.id===element.dataset.nodeId);
  const heading=document.createElement('strong');heading.textContent=node?node.label:element.getAttribute('aria-label');detail.append(heading);
  if(node&&typeof node.definition==='string'){const paragraph=document.createElement('p');paragraph.textContent=node.definition;detail.append(paragraph);}
  (block.data.edges||[]).filter(e=>e.from===element.dataset.nodeId||e.to===element.dataset.nodeId).forEach(edge=>{const names=new Map((block.data.nodes||[]).map(n=>[n.id,n.label]));const p=document.createElement('p');p.textContent=names.get(edge.from)+' → '+names.get(edge.to)+'：'+edge.label;detail.append(p);});
  const refs=document.createElement('p');refs.textContent='来源：'+(result.evidence.filter(e=>block.evidence_ids.includes(e.id)).map(e=>e.title).join('；')||'未提供');detail.append(refs);
  result.uncertainties.filter(u=>block.uncertainty_ids.includes(u.id)||u.affected_block_ids.length===0).forEach(u=>{const p=document.createElement('p');p.textContent='限制：'+u.text;detail.append(p);});
}
document.querySelectorAll('.diagram-node').forEach(node=>{node.addEventListener('click',()=>inspectNode(node));node.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();inspectNode(node);}});});
document.querySelector('#search').addEventListener('input',event=>{const term=event.target.value.trim().toLocaleLowerCase();document.querySelectorAll('.content-card,.data-row').forEach(element=>element.hidden=Boolean(term)&&!element.textContent.toLocaleLowerCase().includes(term));document.querySelectorAll('.diagram-node').forEach(node=>node.style.opacity=!term||node.getAttribute('aria-label').toLocaleLowerCase().includes(term)?'1':'.2');status.textContent=term?'已筛选匹配内容；核验视图保留完整原始数据。':'';});
function previewTask(){task.value=activeTask?JSON.stringify(activeTask,null,2):'';}
document.querySelectorAll('.task-button').forEach(button=>button.addEventListener('click',()=>{
  const declaration=data.spec.interactions.find(a=>a.id===button.dataset.action);
  const continuation=data.continuations.find(c=>c.id===button.dataset.action);
  if(!declaration||!continuation)return;
  activeTask=JSON.parse(JSON.stringify(continuation.task));document.querySelectorAll('.task-button').forEach(b=>b.classList.toggle('active',b===button));
  const label=document.querySelector('#assumption-label');label.hidden=declaration.operation!=='change_assumption'||!('assumption' in declaration.parameter_constraints);
  document.querySelector('#assumption').value=activeTask.parameters.assumption||'';
  const comparison=document.querySelector('#comparison');comparison.hidden=declaration.operation!=='compare';comparison.replaceChildren();
  if(declaration.operation==='compare'){
    comparison.className='comparison-grid';declaration.target_block_ids.forEach(id=>{const block=blocks.get(id);if(!block)return;const article=document.createElement('article');const heading=document.createElement('strong');heading.textContent=block.kind==='text'?block.data.content.slice(0,45):{'relations':'关系与依赖','steps':'执行步骤','series':'数据系列','comparison':'比较记录'}[block.kind];const content=document.createElement('pre');content.textContent=JSON.stringify(block.data,null,2);article.append(heading,content);comparison.append(article);});
  }
  if(declaration.operation==='inspect_evidence'){setView('verify');document.querySelector('#verify').scrollIntoView({block:'start',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});}
  status.textContent=declaration.delivery_mode==='local'?'已在当前结果上展示所选内容。':'已准备完整后续任务；复制后交给上游 Agent。';previewTask();
}));
document.querySelector('#assumption').addEventListener('input',event=>{
  if(!activeTask||activeTask.operation!=='change_assumption')return;
  const declaration=data.spec.interactions.find(a=>a.operation==='change_assumption'&&a.target_block_ids.join()===activeTask.target_block_ids.join());
  const rule=declaration&&declaration.parameter_constraints.assumption;
  const value=event.target.value;
  if(!rule||!value.trim()||(Array.isArray(rule)&&!rule.includes(value))||(rule.type&&rule.type!=='string')||(rule.minLength&&value.length<rule.minLength)||(rule.maxLength&&value.length>rule.maxLength)){status.textContent='请按声明范围输入一个具体假设。';task.value='';return;}
  activeTask.parameters.assumption=value;activeTask.scenario_id='scenario-local-'+Date.now().toString(36);activeTask.preserve_original_result=true;status.textContent='假设已更新，真实结果保持不变；此处尚未执行重算。';previewTask();
});
document.querySelector('#copy-task').addEventListener('click',async()=>{
  if(!task.value){status.textContent='先选择一个思考操作。';return;}
  try{await navigator.clipboard.writeText(task.value);status.textContent='完整后续任务已复制。';}catch(error){document.querySelector('#task-details').open=true;task.focus();task.select();status.textContent='任务已选中，请使用系统复制快捷键。';}
});
if(data.continuations.length){activeTask=data.continuations[0].task;previewTask();}
