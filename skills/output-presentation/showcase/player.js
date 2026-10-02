const steps = window.SKILL_STORY;
const reduced = matchMedia('(prefers-reduced-motion: reduce)');
let current=0,playing=!reduced.matches,timer;
const panel=document.querySelector('#panel'),toggle=document.querySelector('#toggle');
function show(index){current=index;const s=steps[index];document.querySelector('#step').textContent=String(index+1).padStart(2,'0')+' / 06';document.querySelector('#title').textContent=s.title;document.querySelector('#description').textContent=s.description;panel.innerHTML=s.visual;panel.classList.remove('enter');requestAnimationFrame(()=>panel.classList.add('enter'));document.querySelectorAll('.chapter').forEach((button,i)=>button.setAttribute('aria-pressed',String(i===index)));}
function sync(){clearInterval(timer);toggle.textContent=playing?'暂停 II':'播放 ▶';toggle.setAttribute('aria-label',playing?'暂停自动讲解':'播放自动讲解');document.querySelectorAll('.hero-art *').forEach(e=>e.style.animationPlayState=playing?'running':'paused');if(playing&&!document.hidden)timer=setInterval(()=>show((current+1)%steps.length),4700);}
toggle.addEventListener('click',()=>{playing=!playing;sync();});document.querySelectorAll('.chapter').forEach(b=>b.addEventListener('click',()=>{playing=false;show(Number(b.dataset.step));sync();}));document.addEventListener('visibilitychange',sync);reduced.addEventListener('change',()=>{if(reduced.matches)playing=false;sync();});sync();
