(() => {
  if (!window.matchMedia('(pointer: fine)').matches) return;
  const dot=document.createElement('i'), ring=document.createElement('i');
  dot.className='atlas-dot'; ring.className='atlas-ring'; document.body.append(dot,ring);
  let x=-80,y=-80,rx=-80,ry=-80;
  addEventListener('mousemove',e=>{x=e.clientX;y=e.clientY;dot.style.transform=`translate(${x}px,${y}px)`});
  (function tick(){rx+=(x-rx)*.16;ry+=(y-ry)*.16;ring.style.transform=`translate(${rx}px,${ry}px)`;requestAnimationFrame(tick)})();
  document.querySelectorAll('a,button,select,.row').forEach(n=>{n.onmouseenter=()=>document.body.classList.add('atlas-hover');n.onmouseleave=()=>document.body.classList.remove('atlas-hover')});
})();
