/* Whole-pose keyframes preserve anatomy: no independently stretched body slices. */
(() => {
  if (window.DocPupRig) return;
  window.DocPupRig = class {
    constructor(root) {
      this.root = root;
      this.skin = root.querySelector('.pup-pose');
      this.skin.innerHTML = '<span class="pup-frame"></span>';
      this.frame = this.skin.firstChild;
      this.observer = new MutationObserver(() => this.update());
      this.observer.observe(root, {
        attributes: true,
        attributeFilter: ['data-state', 'data-motion', 'data-idle']
      });
      this.update();
    }
    update() {
      const state = this.root.dataset.state,
        motion = this.root.dataset.motion,
        idle = Number(this.root.dataset.idle) || 0,
        key = [state, motion, idle].join(':');
      if (this.key === key) return;
      this.key = key;
      clearTimeout(this.timer);
      const moving = motion === 'walking' || motion === 'running';
      const blink=!moving&&state==='idle'&&(idle===0||idle===1);
      if(blink){
        this.frame.style.backgroundImage="url('/static/portal/docpup-blink-v6.png')";
        this.frame.style.backgroundSize='400% 200%';
        const frames=[0,1,2,1],delays=[3000,60,90,60];let index=0;
        const next=()=>{this.frame.style.backgroundPosition=`${frames[index]*100/3}% ${idle*100}%`;const delay=delays[index];index=(index+1)%frames.length;this.timer=setTimeout(next,delay);};
        this.frame.style.backgroundPosition=`0% ${idle*100}%`;
        if(!matchMedia('(prefers-reduced-motion: reduce)').matches)next();
        return;
      }
      const pair = moving ? (motion === 'running' ? [6, 7] : [4, 5]) : ({
        idle: [
          [0, 1],
          [2, 3],
          [4, 5],
          [6, 7]
        ][idle % 4],
        reading: [8, 9],
        processing: [10, 11],
        analyzing: [10, 11],
        listening: [6, 7],
        waiting: [2, 3],
        accepting: [12, 13],
        rejecting: [14, 15]
      })[state] || [0, 1];
      this.frame.style.backgroundImage = moving ? "url('/static/portal/docpup-poses.png')" : "url('/static/portal/docpup-poses-v4.png')";
      this.frame.style.backgroundSize = moving ? '400% 300%' : '400% 400%';
      const pose = i => {
        this.frame.style.backgroundPosition = `${i%4*100/3}% ${Math.floor(i/4)*100/(moving?2:3)}%`;
      };
      pose(pair[0]);
      if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
      let alternate = false;
      const tick = () => {
        alternate = !alternate;
        pose(pair[Number(alternate)]);
        const delay = moving ? (motion === 'running' ? 150 : 320) : state === 'idle' ? (alternate ? (idle === 2 ? 1600 : 180) : (idle === 2 ? 1800 : 3000)) : state === 'reading' ? (alternate ? 220 : 360) : 900;
        this.timer = setTimeout(tick, delay);
      };
      this.timer = setTimeout(tick, moving ? 250 : state === 'idle' ? 2200 : 400);
    }
    dispose() {
      clearTimeout(this.timer);
      this.observer.disconnect();
    }
  };
})();
