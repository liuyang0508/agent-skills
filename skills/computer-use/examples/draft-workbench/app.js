(() => {
  const key='computer-use-workbench-v1';
  const initial={title:'客户回访记录',due:'2026-10-08',notes:'确认使用范围，记录后续问题。',status:'unsaved',saveCount:0,publishCount:0,revision:0};
  let saved;
  const message=document.querySelector('#message');
  const fields=['title','due','notes'];
  try{saved=JSON.parse(localStorage.getItem(key))||{...initial};}
  catch(error){saved={...initial};message.textContent='本地存储暂不可用；不能声称保存成功。';}
  fields.forEach(name=>document.getElementById(name).value=saved[name]);
  function render(){
    document.querySelector('#state').textContent=saved.status==='draft'?'已保存草稿':saved.status==='published'?'演示记录已发布':'尚未保存';
    document.querySelector('#save-count').textContent=String(saved.saveCount);
    document.querySelector('#publish-count').textContent=String(saved.publishCount);
    document.querySelector('#revision').textContent=saved.revision?'版本 '+saved.revision:'无保存版本';
    document.querySelector('#saved-record').textContent=saved.revision?JSON.stringify(saved,null,2):'尚未保存记录。';
  }
  function commit(status){
    const next={...saved,status,revision:saved.revision+1};
    fields.forEach(name=>next[name]=document.getElementById(name).value);
    if(status==='draft')next.saveCount++;
    else next.publishCount++;
    localStorage.setItem(key,JSON.stringify(next));saved=next;
  }
  document.querySelector('#draft-form').addEventListener('submit',event=>{
    event.preventDefault();message.textContent='';
    const mode=document.querySelector('#mode').value;
    if(mode==='failure'){message.textContent='保存返回错误：未写入草稿。';return;}
    try{commit('draft');}catch(error){message.textContent='存储失败，尚未确认保存。';return;}
    if(mode==='lost-confirmation'){message.textContent='未收到保存确认，请回读当前对象。';return;}
    render();message.textContent='草稿已保存，可刷新核验。';
  });
  document.querySelector('#publish').addEventListener('click',()=>{
    try{commit('published');render();message.textContent='仅本地演示：已发布。';}
    catch(error){message.textContent='发布结果未确认。';}
  });
  document.querySelector('#reset').addEventListener('click',()=>{
    try{localStorage.removeItem(key);}catch(error){message.textContent='无法清理演示数据。';return;}
    saved={...initial};fields.forEach(name=>document.getElementById(name).value=saved[name]);
    document.querySelector('#mode').value='normal';message.textContent='演示已重置。';render();
  });
  render();
})();
