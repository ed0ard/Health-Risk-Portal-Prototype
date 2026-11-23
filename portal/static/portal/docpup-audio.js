/* Decode ahead, then schedule consecutive buffers on one audio clock. */
(() => {
  if(window.DocPupAudio)return;
  window.DocPupAudio={
    supported(){return typeof window.AudioContext==='function'&&typeof AudioContext.prototype.decodeAudioData==='function';},
    async play(units,load,signal,onState){
      const context=new AudioContext(),sources=new Set(),pending=new Map(),ends=[];
      let cursor=0,finished=false;
      const check=()=>{if(signal.aborted)throw new DOMException('Cancelled','AbortError');};
      const stop=()=>{for(const source of sources){try{source.stop();}catch(_){}};context.close().catch(()=>{});};
      signal.addEventListener('abort',stop,{once:true});
      const decode=index=>{
        if(index>=units.length)return;
        if(!pending.has(index))pending.set(index,(async()=>{try{const item=await load(units[index]);check();if(item.error)throw item.error;return {buffer:await context.decodeAudioData(await item.blob.arrayBuffer())};}catch(error){return {error};}})());
        return pending.get(index);
      };
      const monitor=setInterval(()=>{if(!finished&&!signal.aborted)onState(cursor>context.currentTime?'reading':'processing');},100);
      try{
        await context.resume();check();decode(0);decode(1);
        for(let i=0;i<units.length;i++){
          const item=await decode(i);check();if(item.error)throw item.error;
          const source=context.createBufferSource();source.buffer=item.buffer;source.connect(context.destination);sources.add(source);
          ends[i]=new Promise(resolve=>{source.onended=()=>{sources.delete(source);source.disconnect();resolve();};});
          const when=Math.max(context.currentTime+.01,cursor);source.start(when);cursor=when+item.buffer.duration;
          onState('reading');pending.delete(i);decode(i+2);
          // Keep at most two scheduled buffers and one decoded look-ahead.
          if(i>0)await ends[i-1];
        }
        await ends.at(-1);check();
      }finally{finished=true;clearInterval(monitor);signal.removeEventListener('abort',stop);stop();pending.clear();}
    }
  };
})();
