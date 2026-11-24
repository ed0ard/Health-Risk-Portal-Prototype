(() => {
  'use strict';
  const fresh = document.getElementById('docpup');
  if (!fresh) return;
  if (window.docPup) {
    window.docPup.mount(fresh);
    return;
  }
  const root = fresh,
    button = root.querySelector('.pup-body'),
    bubble = root.querySelector('.pup-bubble');
  const life = new AbortController();
  let job = null,
    drag = null,
    suppress = false,
    panelStage = 0,
    pendingFile = null,
    navController = null;
  let policy = {
    enabled: true,
    auto_read: true,
    auto_asr: true,
    max_file_mb: 20,
    clarify_rounds: 2,
    file_rounds: 2,
    mic_seconds: 20
  };
  let lastPosition = null;
  let savedBubbleScroll=0;
  let taskState = 'idle';
  let rejectionTimer = null;
  const zh = () => document.documentElement.lang.startsWith('zh');
  const t = (cn, en) => zh() ? cn : en;
  const csrf = () => document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
  const labels = {
    idle: ['汪小医', 'Doc Pup'],
    reading: ['朗读中 · 点击停止', 'Reading · click to stop'],
    listening: ['聆听中 · 点击停止', 'Listening · click to stop'],
    processing: ['加载中…', 'Loading…'],
    analyzing: ['分析中…', 'Analyzing…'],
    accepting: ['收到文件', 'File received'],
    rejecting: ['暂不接收', 'Cannot accept'],
    waiting: ['等待补充文件', 'Waiting for another file']
  };

  function renderState(name) {
    root.dataset.state = name;
    root.querySelector('.pup-status').textContent = t(...(labels[name] || labels.idle));
  }

  function state(name) {
    taskState = name;
    // Audio/network callbacks continue updating the task underneath this feedback.
    renderState(rejectionTimer === null ? name : 'rejecting');
  }

  function localize() {
    button.removeAttribute('title');
    button.setAttribute('aria-label', t('汪小医', 'Doc Pup'));
    root.querySelector('[data-pup-close]').title = t('关闭', 'Close');
    root.querySelector('[data-pup-close]').setAttribute('aria-label', t('关闭', 'Close'));
    root.querySelector('[data-pup-skip]').textContent = t('跳过', 'Skip');
    renderState(rejectionTimer === null ? taskState : 'rejecting');
  }

  function show(text, files = false) {
    bubble.hidden = false;
    bubble.querySelector('p').textContent = String(text).replace(/\*\*|__|```/g, '').replace(/^#{1,6}\s+/gm, '');
    root.querySelector('[data-pup-skip]').hidden = !files;
    bubble.querySelector('.pup-bubble-scroll').scrollTop=0;savedBubbleScroll=0;
  }

  function hide() {
    bubble.hidden = true;
    root.querySelector('p').textContent = '';
    root.querySelector('[data-pup-skip]').hidden = true;
  }

  function idle() {
    state('idle');
    root.dataset.motion = 'standing';
    root.dataset.idle = String(Math.floor(Math.random() * 4));
  }

  function origin() {
    const rect = document.querySelector('.workspace')?.getBoundingClientRect();
    return {
      x: rect?.left || 0,
      y: document.querySelector('.topbar')?.getBoundingClientRect().bottom || 0
    };
  }

  function position() {
    if (!root.isConnected || root.hidden) return lastPosition || {
      x: Math.max(0, innerWidth - origin().x - 152),
      y: Math.max(0, innerHeight - origin().y - 180)
    };
    const r = root.getBoundingClientRect(),
      o = origin();
    lastPosition = {
      x: r.left - o.x,
      y: r.top - o.y
    };
    return {
      ...lastPosition
    };
  }

  function move(x, y) {
    const o = origin();
    root.style.left = Math.max(o.x, Math.min(innerWidth - root.offsetWidth, x)) + 'px';
    root.style.top = Math.max(o.y, Math.min(innerHeight - root.offsetHeight, y)) + 'px';
    root.style.right = 'auto';
    root.style.bottom = 'auto';
    lastPosition = {
      x: parseFloat(root.style.left) - o.x,
      y: parseFloat(root.style.top) - o.y
    };
  }

  function savePosition() {
    try {
      sessionStorage.setItem('docpup-position', JSON.stringify(position()));
    } catch (_) {}
  }

  function check(j) {
    if (job !== j || j.controller.signal.aborted) throw new DOMException('Cancelled', 'AbortError');
  }

  function cancel() {
    clearTimeout(rejectionTimer);
    rejectionTimer = null;
    if (job) {
      const j = job;
      job = null;
      j.controller.abort();
      j.cache.clear();
      fetch('/docpup/cancel/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrf()
        },
        body: JSON.stringify({
          task: j.id
        }),
        keepalive: true
      }).catch(() => {});
    }
    pendingFile = null;
    panelStage = 0;
    hide();
    idle();
    savePosition();
  }

  function context() {
    return {
      ...Object.fromEntries(new URLSearchParams(location.search)),
      page: root.dataset.page,
      kind: root.dataset.kind,
      subject: root.dataset.subject,
      lang: zh() ? 'zh' : 'en'
    };
  }

  function start(type) {
    cancel();
    job = {
      id: crypto.randomUUID(),
      type,
      context: context(),
      controller: new AbortController(),
      cache: new Map(),
      request: 0
    };
    return job;
  }
  async function api(action, data, j, file) {
    check(j);
    const payload = {
      ...j.context,
      ...data,
      task: j.id,
      request: String(++j.request)
    };
    let body = JSON.stringify(payload);
    const headers = {
      'X-CSRFToken': csrf()
    };
    if (file) {
      body = new FormData();
      body.append('data', JSON.stringify(payload));
      body.append('file', file, file.name || 'voice.webm');
    } else headers['Content-Type'] = 'application/json';
    const query = new URLSearchParams(j.context);
    const response = await fetch('/docpup/' + action + '/?' + query, {
      method: 'POST',
      headers,
      body,
      signal: j.controller.signal
    });
    check(j);
    if (response.redirected) throw Error(t('登录已过期，请重新登录。', 'Your session expired. Please sign in again.'));
    if (!response.ok) {
      const r = await response.json();
      const parts = String(r.error).split(' / ');
      throw Error(zh() ? parts.at(-1) : parts[0]);
    }
    const result = await (action === 'tts' ? response.blob() : response.json());
    check(j);
    return result;
  }
  async function run(fn, type = 'brief') {
    if (!policy.enabled) return;
    const j = start(type);
    try {
      await fn(j);
    } catch (e) {
      if (job === j && e.name !== 'AbortError') {
        reject(e.message);
      }
    } finally {
      if (job === j) {
        j.controller.abort();
        j.cache.clear();
        job = null;
        pendingFile = null;
        idle();
        savePosition();
      }
    }
  }

  function prepare(unit, j) {
    if (!j.cache.has(unit)) {
      const promise = api('tts', {
        text: unit.text,
        following: j.type === 'follow'
      }, j).then(blob => ({
        blob
      }), error => ({
        error
      }));
      j.cache.set(unit, promise);
    }
    return j.cache.get(unit);
  }
  async function travel(x, y, motion, j) {
    check(j);
    const r = root.getBoundingClientRect(),
      distance = Math.hypot(x - r.left, y - r.top),
      duration = Math.min(1400, Math.max(120, distance / (motion === 'running' ? 650 : 180) * 1000));
    root.dataset.motion = motion;
    await new Promise((resolve, reject) => {
      let frame;
      const begin = performance.now();
      const abort = () => {
        cancelAnimationFrame(frame);
        reject(new DOMException('Cancelled', 'AbortError'));
      };
      j.controller.signal.addEventListener('abort', abort, {
        once: true
      });

      function step(now) {
        const f = Math.min(1, (now - begin) / duration);
        move(r.left + (x - r.left) * f, r.top + (y - r.top) * f);
        if (f < 1) frame = requestAnimationFrame(step);
        else {
          j.controller.signal.removeEventListener('abort', abort);
          resolve();
        }
      }
      frame = requestAnimationFrame(step);
    });
    root.dataset.motion = 'standing';
  }
  async function play(unit, j, follow = false) {
    check(j);
    state('processing');
    root.dataset.motion = 'standing';
    const item = await prepare(unit, j);
    check(j);
    if (j.nextFile) return;
    if (item.error) throw item.error;
    const url = URL.createObjectURL(item.blob),
      audio = new Audio(url);
    audio.preload = 'auto';
    let watchdog;
    try {
      await new Promise((resolve, reject) => {
        let lastTime = 0,
          lastProgress = performance.now(),
          retries = 0;
        const abort = () => {
          audio.pause();
          reject(new DOMException('Cancelled', 'AbortError'));
        };
        j.controller.signal.addEventListener('abort', abort, {
          once: true
        });
        const done = () => {
          j.controller.signal.removeEventListener('abort', abort);
          resolve();
        };
        j.stopSpeech = () => {
          audio.pause();
          done();
        };
        audio.onended = done;
        audio.onerror = () => reject(Error(t('音频暂时不可播放，请重试。', 'Audio could not be played. Please retry.')));
        audio.onplaying = () => {
          j.speaking = true;
          state('reading');
          if (follow) root.dataset.motion = 'walking';
        };
        audio.onwaiting = audio.onstalled = () => {
          state('processing');
          root.dataset.motion = 'standing';
        };
        audio.ontimeupdate = () => {
          if (job !== j) return;
          if (audio.currentTime > lastTime) {
            lastTime = audio.currentTime;
            lastProgress = performance.now();
            state('reading');
            if (follow) {
              root.dataset.motion = 'walking';
              const range = unit.chars[Math.min(unit.chars.length - 1, Math.floor(unit.chars.length * audio.currentTime / (audio.duration || 1)))];
              if (range) {
                const r = range.getBoundingClientRect();
                move(r.left, r.bottom + 4);
              }
            }
          }
        };
        watchdog = setInterval(() => {
          if (audio.ended || job !== j) return;
          if (performance.now() - lastProgress > 8000) {
            state('processing');
            root.dataset.motion = 'standing';
            const at = audio.currentTime;
            if (++retries > 2) {
              reject(Error(t('音频加载超时，可重新拖动继续。', 'Audio loading timed out. Drag again to continue.')));
              return;
            }
            audio.load();
            audio.onloadedmetadata = () => {
              audio.currentTime = Math.min(at, audio.duration || at);
              audio.play().catch(reject);
            };
            lastProgress = performance.now();
          }
        }, 2000);
        audio.play().catch(reject);
      });
    } finally {
      clearInterval(watchdog);
      j.speaking = false;
      delete j.stopSpeech;
      audio.pause();
      audio.src = '';
      URL.revokeObjectURL(url);
      j.cache.delete(unit);
      if (job === j) root.dataset.motion = 'standing';
    }
  }
  async function speak(text, j) {
    if (!policy.auto_read) return;
    if(j.type==='brief'){
      // Keep sentences together; never create a new player at each full stop.
      const chunks=[];let remaining=String(text);
      while(remaining.length>480){let cut=remaining.lastIndexOf(' ',480);for(const mark of ['。','！','？','\n'])cut=Math.max(cut,remaining.lastIndexOf(mark,480)+1);if(cut<200)cut=480;chunks.push(remaining.slice(0,cut));remaining=remaining.slice(cut).trimStart();}
      if(remaining)chunks.push(remaining);
      const units=chunks.map(text=>({text}));
      if(window.DocPupAudio?.supported()){
        j.speaking=false;
        try{await window.DocPupAudio.play(units,unit=>prepare(unit,j),j.controller.signal,name=>{if(job===j){j.speaking=name==='reading';state(name);}});}
        finally{j.speaking=false;for(const unit of units)j.cache.delete(unit);}
      }else{for(let i=0;i<units.length;i++){prepare(units[i],j);if(units[i+1])prepare(units[i+1],j);await play(units[i],j);}}
      return;
    }
    const units = (String(text).match(/[^。！？.!?\n]+[。！？.!?\n]*|[。！？.!?\n]+/g) || [text]).flatMap(s => s.match(/[\s\S]{1,160}/g) || []).map(text => ({
      text
    }));
    for (let i = 0; i < units.length; i++) {
      if (j.nextFile) return;
      prepare(units[i], j);
      if (units[i + 1]) prepare(units[i + 1], j);
      await play(units[i], j);
    }
  }
  async function listen(j) {
    check(j);
    if (j.nextFile) return '';
    if (!navigator.mediaDevices?.getUserMedia) throw Error(t('麦克风需要 localhost 或 HTTPS', 'Microphone requires localhost or HTTPS'));
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: true
    });
    if (job !== j) {
      stream.getTracks().forEach(x => x.stop());
      check(j);
    }
    if (j.nextFile) {
      stream.getTracks().forEach(x => x.stop());
      return '';
    }
    state('listening');
    j.listening = true;
    show(t(`请回答，停顿后自动识别。`, `Please answer. \nRecognition starts after a pause.`));
    const chunks = [];
    let recorder, timer, frame, ctx;
    try {
      recorder = new MediaRecorder(stream);
      const blob = await new Promise((resolve, reject) => {
        const abort = () => {
          if (recorder.state !== 'inactive') recorder.stop();
          reject(new DOMException('Cancelled', 'AbortError'));
        };
        j.controller.signal.addEventListener('abort', abort, {
          once: true
        });
        recorder.ondataavailable = e => chunks.push(e.data);
        recorder.onstop = () => {
          j.controller.signal.removeEventListener('abort', abort);
          resolve(new Blob(chunks, {
            type: recorder.mimeType
          }));
        };
        recorder.onerror = () => reject(Error('Microphone error'));
        recorder.start();
        j.stopListening = () => {
          if (recorder.state !== 'inactive') recorder.stop();
        };
        timer = setTimeout(() => {
          if (recorder.state !== 'inactive') recorder.stop();
        }, policy.mic_seconds * 1000);
        ctx = new AudioContext();
        const analyser = ctx.createAnalyser();
        ctx.createMediaStreamSource(stream).connect(analyser);
        const samples = new Uint8Array(analyser.fftSize);
        let heard = false,
          last = performance.now();
        const tick = () => {
          analyser.getByteTimeDomainData(samples);
          const volume = Math.sqrt(samples.reduce((s, v) => s + (v - 128) ** 2, 0) / samples.length);
          if (volume > 5) {
            heard = true;
            last = performance.now();
          }
          if (heard && performance.now() - last > 1600) {
            if (recorder.state !== 'inactive') recorder.stop();
            return;
          }
          frame = requestAnimationFrame(tick);
        };
        tick();
      });
      j.listening = false;
      check(j);
      if (j.nextFile) return '';
      state('processing');
      return (await api('asr', {}, j, new File([blob], 'voice.webm'))).text;
    } finally {
      j.listening = false;
      delete j.stopListening;
      clearTimeout(timer);
      cancelAnimationFrame(frame);
      ctx?.close();
      stream.getTracks().forEach(x => x.stop());
      chunks.length = 0;
    }
  }

  function fields() {
    const form = document.querySelector('form[data-docpup-form]') || (root.dataset.page === 'entry' ? document.querySelector('.workspace form[method=post]') : null);
    if (!form) return [];
    const controls = [...form.querySelectorAll('input,select,textarea')].filter(e => e.name && !e.disabled && !['hidden', 'password', 'submit', 'reset', 'button', 'file'].includes(e.type) && !['replace', 'kind'].includes(e.name));
    return [...new Set(controls.map(e => e.name))].map(key => {
      const nodes = controls.filter(e => e.name === key),
        e = nodes[0],
        container = e.closest('[data-pup-key]') || e.closest('fieldset') || e.closest('label') || e.parentElement;
      const label = container.querySelector('legend') || container;
      const clone = label.cloneNode(true);
      clone.querySelectorAll('input,select,textarea,button').forEach(x => x.remove());
      const question = clone.textContent.trim() || e.getAttribute('aria-label') || key;
      const type = e.tagName === 'SELECT' ? (e.multiple ? 'multichoice' : 'choice') : e.type === 'radio' ? 'choice' : e.type === 'checkbox' ? (nodes.length > 1 ? 'multichoice' : 'boolean') : e.type === 'number' ? 'number' : e.type === 'date' ? 'date' : 'text';
      const options = e.tagName === 'SELECT' ? [...e.options].filter(o => o.value !== '').map(o => ({
        value: o.value,
        label: o.textContent.trim()
      })) : type === 'boolean' ? [{
        value: 'true',
        label: t('是', 'Yes')
      }, {
        value: 'false',
        label: t('否', 'No')
      }] : nodes.filter(x => ['radio', 'checkbox'].includes(x.type)).map(x => ({
        value: x.value,
        label: x.closest('label')?.textContent.trim() || x.value
      }));
      return {
        key,
        question,
        type,
        options,
        min: e.min ? (e.type === 'date' ? e.min : Number(e.min)) : null,
        max: e.max ? (e.type === 'date' ? e.max : Number(e.max)) : null,
        step: e.step || 'any',
        nodes,
        container
      };
    });
  }

  function descriptors() {
    return fields().map(({
      nodes,
      container,
      ...f
    }) => f);
  }

  function emptyKeys() {
    return fields().filter(f => f.type === 'boolean' ? !f.nodes[0].checked && !f.nodes[0].dataset.pupAnswered : ['choice', 'multichoice'].includes(f.type) && f.nodes[0].tagName !== 'SELECT' ? !f.nodes.some(n => n.checked) : f.nodes[0].value === '').map(f => f.key);
  }

  function fill(items) {
    for (const a of items || []) {
      if (!emptyKeys().includes(a.key)) continue;
      const f = fields().find(f => f.key === a.key);
      if (!f) continue;
      for (const e of f.nodes) {
        if (f.type === 'boolean') {
          e.checked = a.value === true || ['true', '1'].includes(String(a.value));
          e.dataset.pupAnswered = 'true';
        } else if (e.type === 'radio' || e.type === 'checkbox') {
          e.checked = Array.isArray(a.value) ? a.value.map(String).includes(e.value) : e.value === String(a.value);
        } else if (e.tagName === 'SELECT' && e.multiple) {
          for (const o of e.options) o.selected = Array.isArray(a.value) && a.value.map(String).includes(o.value);
        } else e.value = String(a.value);
        e.dispatchEvent(new Event('input', {
          bubbles: true
        }));
        e.dispatchEvent(new Event('change', {
          bubbles: true
        }));
      }
    }
  }
  const skip = text => /不知道|跳过|不清楚|停止|\b(skip|don.t know|stop)\b/i.test(text);
  async function answer(key, j) {
    let source = '';
    for (let round = 0; round <= policy.clarify_rounds && emptyKeys().includes(key); round++) {
      const text = await listen(j);
      if (skip(text)) return;
      source += '\n' + text;
      state('analyzing');
      const result = await api('answer', {
        keys: [key],
        round,
        fields: descriptors(),
        text: source
      }, j);
      fill(result.answers);
      if (!emptyKeys().includes(key) || result.skip) {
        hide();
        return;
      }
      if (round < policy.clarify_rounds) {
        const question = result.question || t('请补充具体答案，也可以说跳过。', 'Please give a more specific answer, or say skip.');
        show(question);
        await speak(question, j);
      }
    }
    hide();
  }

  function readingUnits() {
    const workspace = document.querySelector('.workspace');
    if (!workspace) return [];
    const questions = fields(),
      groups = new Map(),
      walker = document.createTreeWalker(workspace, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      const parent = node.parentElement;
      let closed=parent.closest('details:not([open])');let concealed=false;
      while(closed){if(!closed.querySelector(':scope > summary')?.contains(parent)){concealed=true;break;}closed=closed.parentElement?.closest('details:not([open])');}
      if(concealed)continue;
      if (!node.textContent.trim() || parent.closest('script,style,svg,input,select,textarea,option,[hidden],dialog:not([open]),.actions')) continue;
      if (!parent.getClientRects().length || getComputedStyle(parent).visibility === 'hidden') continue;
      const question = questions.find(f => f.container.contains(node));
      const legend = question?.container.querySelector('legend');
      const option = !!(legend && !legend.contains(node));
      const block = question ? (option ? (parent.closest('label') || parent) : legend || question.container) : (parent.closest('[data-reading-block],.risk-result,a,button,summary,p,li,td,th,h1,h2,h3,h4,legend,label,dt,dd,div,article,section') || parent);
      if (!groups.has(block)) groups.set(block, {
        block,
        key: question?.key,
        questionPart: question ? (option ? 'option' : 'stem') : null,
        chars: []
      });
      const g = groups.get(block);
      for (let i = 0; i < node.length; i++) {
        const range = document.createRange();
        range.setStart(node, i);
        range.setEnd(node, i + 1);
        const rect = range.getBoundingClientRect();
        if (rect.height && rect.width) {
          if (i === 0 && g.chars.length) g.chars.push({
            range,
            char: ' ',
            y: rect.top
          });
          g.chars.push({
            range,
            char: node.textContent[i],
            y: rect.top
          });
        }
      }
    }
    const units = [];
    for (const g of groups.values()) {
      let line = null;
      for (const c of g.chars) {
        if (!line || Math.abs(c.y - line.y) > 3 || line.text.length >= 150) {
          line = {
            block: g.block,
            key: g.key,
            questionPart: g.questionPart,
            text: '',
            chars: [],
            y: c.y
          };
          units.push(line);
        }
        line.text += c.char;
        line.chars.push(c.range);
      }
      if (line && g.key && g.questionPart === 'stem') line.lastStemLine = true;
    }
    return units.filter(u => u.text.trim());
  }
  async function follow(target, j, point) {
    hide();
    const units = readingUnits();
    let index = -1;
    if (point) index = units.findIndex(u => u.chars.some(c => {
      const r = c.getBoundingClientRect();
      return point.y >= r.top - 2 && point.y <= r.bottom + 2 && point.x >= r.left - 2 && point.x <= r.right + 2;
    }));
    if (index < 0) {
      const semantic = target.closest('a,button,label,legend,h1,h2,h3,h4');
      if (semantic) index = units.findIndex(u => u.block === semantic);
    }
    if (index < 0) {
      const field = fields().find(f => f.nodes.includes(target));
      if (field) index = units.findIndex(u => u.key === field.key && u.questionPart === 'stem');
    }
    if (index < 0) return;
    // A drop anywhere in a semantic text block starts at that block, not a sibling card.
    const block = units[index].block;
    while (index > 0 && units[index - 1].block === block) index--;
    const plan = [];
    for (let i = index; i < units.length; i++) {
      const u = units[i];
      plan.push(u);
      // After a question stem, its options are skipped whether answered, prefilled or skipped.
      // Starting on options instead reads them but never invokes ASR for that prior question.
      if (u.lastStemLine)
        while (units[i + 1]?.key === u.key && units[i + 1].questionPart === 'option') i++;
    }
    let previous = null;
    for (let i = 0; i < plan.length; i++) {
      const unit = plan[i];
      check(j);
      const closed=unit.block.closest('details:not([open])');
      if(closed&&!closed.querySelector(':scope > summary')?.contains(unit.block))continue;
      prepare(unit, j);
      if (plan[i + 1]) prepare(plan[i + 1], j);
      if (plan[i + 2]) prepare(plan[i + 2], j);
      unit.block.scrollIntoView({
        block: 'nearest'
      });
      const workspace = document.querySelector('.workspace');
      let r = unit.chars[0].getBoundingClientRect();
      const clip = workspace.getBoundingClientRect();
      if (r.top < clip.top + 12 || r.bottom > Math.min(clip.bottom, innerHeight) - 175) {
        workspace.scrollTop += r.top - clip.top - 24;
        r = unit.chars[0].getBoundingClientRect();
      }
      await travel(r.left, r.bottom + 4, previous === unit.block ? 'walking' : 'running', j);
      await play(unit, j, true);
      previous = unit.block;
      if (unit.key && unit.lastStemLine && policy.auto_asr && emptyKeys().includes(unit.key)) {
        await answer(unit.key, j);
        hide();
      }
    }
    await travel(innerWidth - root.offsetWidth - 24, innerHeight - root.offsetHeight - 20, 'running', j);
    root.dataset.motion = 'standing';
    savePosition();
  }
  async function fileTask(file, j) {
    let evidence = '';
    for (let round = 0; round <= policy.file_rounds; round++) {
      pendingFile = null;
      delete j.nextFile;
      root.querySelector('.pup-package text').textContent = /\.(wav|mp3|m4a|ogg|flac|webm)$/i.test(file.name) ? '♫' : /\.pdf$/i.test(file.name) ? 'PDF' : 'TXT';
      state('accepting');
      await new Promise(r => setTimeout(r, 450));
      check(j);
      state('processing');
      const result = await api('file', {
        keys: emptyKeys(),
        round,
        fields: descriptors(),
        evidence
      }, j, file);
      file = null;
      evidence = result.evidence || evidence;
      fill(result.answers);
      if (!emptyKeys().length) {
        show(t('已填写，请核对后提交。', 'Filled. Please review before submitting.'));
        return;
      }
      if (round === policy.file_rounds) {
        show(t('未提供的信息已留空。', 'Fields without information have been left blank.'));
        return;
      }
      const message = t('还有可以补充的文件吗？\n拖入一个文件，或点击“跳过”。', 'Do you have another file? \nDrop one file, or select Skip.');
      show(message, true);
      const waiting = new Promise((resolve, reject) => {
        const timeout = setTimeout(() => resolve(null), 90000);
        const abort = () => {
          clearTimeout(timeout);
          reject(new DOMException('Cancelled', 'AbortError'));
        };
        j.controller.signal.addEventListener('abort', abort, {
          once: true
        });
        pendingFile = f => {
          pendingFile = null;
          clearTimeout(timeout);
          j.controller.signal.removeEventListener('abort', abort);
          j.nextFile = f || true;
          if (f) state('accepting');
          j.stopSpeech?.();
          resolve(f);
        };
      });
      await speak(message, j);
      if (!j.nextFile) state('waiting');
      file = await waiting;
      check(j);
      if (!file) {
        hide();
        return;
      }
    }
  }

  function reject(message) {
    show(message);
    clearTimeout(rejectionTimer);
    rejectionTimer = setTimeout(() => {
      rejectionTimer = null;
      renderState(taskState);
    }, 1300);
    renderState('rejecting');
  }
  root.addEventListener('dragover', e => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
  });
  root.addEventListener('drop', e => {
    e.preventDefault();
    const files = e.dataTransfer.files;
    if (!fields().length) return reject(t('此页没有可填写问卷。', 'No editable questionnaire here.'));
    if (job?.type === 'file' && !pendingFile) return reject(t('正在处理文件，请稍后再拖入。', 'A file is being processed. Please wait.'));
    if (files.length !== 1) return reject(t('一次只能接收一个文件。', 'One file at a time.'));
    const file = files[0];
    if (file.size > policy.max_file_mb * 1024 * 1024) return reject(t(`文件不能超过${policy.max_file_mb}MB。`, `Maximum file size is ${policy.max_file_mb} MB.`));
    if (!/\.(wav|mp3|m4a|ogg|flac|webm|pdf|txt|docx)$/i.test(file.name)) return reject(t('仅接受音频、PDF、TXT、DOCX。', 'Accepts audio, PDF, TXT or DOCX.'));
    if (pendingFile) pendingFile(file);
    else run(j => fileTask(file, j), 'file');
  });
  root.querySelector('[data-pup-close]').onclick = () => cancel();
  root.querySelector('[data-pup-skip]').onclick = () => {
    const finish = pendingFile;
    finish?.(null);
    if (finish) cancel();
  };
  button.addEventListener('click', () => {
    if (suppress) {
      suppress = false;
      return;
    }
    if (job) {
      if (job.speaking || job.listening || root.dataset.motion !== 'standing') cancel();
      return;
    }
    if (panelStage) {
      hide();
      panelStage = 0;
      return;
    }
    if (['home', 'query', 'report', 'alerts', 'training', 'users', 'logs'].includes(root.dataset.page)) run(async j => {
      state('analyzing');
      const result = await api('brief', {}, j);
      show(result.text);
      panelStage = 1;
      await speak(result.text, j);
    });
    else root.dataset.idle = String((Number(root.dataset.idle) + 1) % 4);
  });
  button.addEventListener('pointerdown', e => {
    if (e.button !== 0) return;
    const r = root.getBoundingClientRect();
    drag = {
      x: e.clientX,
      y: e.clientY,
      dx: e.clientX - r.left,
      dy: e.clientY - r.top,
      moved: false
    };
    button.setPointerCapture(e.pointerId);
  });
  button.addEventListener('pointermove', e => {
    if (!drag) return;
    if (Math.hypot(e.clientX - drag.x, e.clientY - drag.y) > 7) {
      if (!drag.moved) cancel();
      drag.moved = true;
      move(e.clientX - drag.dx, e.clientY - drag.dy);
      root.dataset.motion = 'walking';
    }
  });
  button.addEventListener('pointerup', e => {
    if (!drag) return;
    const moved = drag.moved;
    drag = null;
    root.dataset.motion = 'standing';
    if (!moved) return;
    suppress = true;
    savePosition();
    root.style.pointerEvents = 'none';
    const node = document.elementFromPoint(e.clientX, e.clientY);
    root.style.pointerEvents = '';
    if (node?.closest('.workspace')) run(j => follow(node, j, {
      x: e.clientX,
      y: e.clientY
    }), 'follow');
  });
  button.addEventListener('pointercancel', () => {
    drag = null;
    root.dataset.motion = 'standing';
    savePosition();
  });

  function beforePageChange(language = false) {
    savedBubbleScroll=bubble.querySelector('.pup-bubble-scroll').scrollTop;
    const p = position();
    if (language || job && ['file', 'follow'].includes(job.type) || job?.listening) cancel();
    savePosition();
    return p;
  }

  function mount(next, saved) {
    if (!next) return;
    const p = saved || position();
    for (const key of ['page', 'kind', 'subject']) root.dataset[key] = next.dataset[key];
    if (next !== root) next.replaceWith(root);
    const o = origin();
    move(o.x + p.x, o.y + p.y);
    readPolicy();
    localize();
    bubble.querySelector('.pup-bubble-scroll').scrollTop=savedBubbleScroll;
  }
  async function navigate(url, {
    historyMode = 'push',
    method = 'GET',
    body
  } = {}) {
    navController?.abort();
    const controller = new AbortController();
    navController = controller;
    const p = beforePageChange();
    try {
      const response = await fetch(url, {
        method,
        body,
        signal: controller.signal,
        headers: {
          'X-DocPup-Navigation': '1'
        }
      });
      if (!response.ok) throw Error('navigation');
      const html = new DOMParser().parseFromString(await response.text(), 'text/html');
      if (controller.signal.aborted) return;
      const next = html.getElementById('docpup');
      if (!next) {
        cancel();
        location.href = response.url;
        return;
      }
      Object.values(window.Chart?.instances || {}).forEach(c => c.destroy());
      document.title = html.title;
      document.documentElement.lang = html.documentElement.lang;
      savedBubbleScroll=bubble.querySelector('.pup-bubble-scroll').scrollTop;
      document.body.replaceWith(html.body);
      if (historyMode === 'push') history.pushState({}, '', response.url || url);
      else if (historyMode === 'replace') history.replaceState({}, '', response.url || url);
      mount(next, p);
      window.initPortal?.();
      for (const script of document.body.querySelectorAll('script[src]')) {
        if (window.portalScriptLoaded?.(script.src) || script.src.includes('/docpup.js')) continue;
        const copy = document.createElement('script');
        copy.src = script.src;
        copy.async = false;
        script.replaceWith(copy);
      }
    } catch (error) {
      if (error.name !== 'AbortError') location.href = url;
    }
  }
  document.addEventListener('click', e => {
    const a = e.target.closest('a[href]');
    if (!a || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || a.target || a.hasAttribute('download')) return;
    const url = new URL(a.href, location.href);
    if (url.origin === location.origin && url.pathname.startsWith('/health/') && !url.searchParams.has('format')) {
      e.preventDefault();
      navigate(url.href);
    }
  }, {
    signal: life.signal
  });
  document.addEventListener('submit', e => {
    if (e.target.matches('.language')) {
      if (e.submitter?.value !== document.querySelector('.language')?.dataset.language) beforePageChange(true);
      return;
    }
    const form = e.target;
    if (e.defaultPrevented || form.matches('[data-training]')) return;
    const url = new URL(form.action || location.href, location.href);
    if (url.origin !== location.origin || !url.pathname.startsWith('/health/')) return;
    const data = new FormData(form);
    if (e.submitter?.name) data.set(e.submitter.name, e.submitter.value);
    if (data.has('format')) return;
    e.preventDefault();
    if (form.method.toLowerCase() === 'get') {
      url.search = new URLSearchParams(data);
      navigate(url.href);
    } else navigate(url.href, {
      method: 'POST',
      body: data
    });
  }, {
    signal: life.signal
  });
  window.addEventListener('popstate', () => navigate(location.href, {
    historyMode: 'none'
  }), {
    signal: life.signal
  });
  document.addEventListener('change', e => {
    if (e.target.matches('input[type=checkbox]') && fields().some(f => f.nodes.includes(e.target))) e.target.dataset.pupAnswered = 'true';
  }, {
    signal: life.signal
  });
  document.addEventListener('reset', e => {
    e.target.querySelectorAll('[data-pup-answered]').forEach(n => delete n.dataset.pupAnswered);
  }, {
    signal: life.signal
  });
  window.addEventListener('pagehide', () => {
    savePosition();
    cancel();
  }, {
    signal: life.signal
  });
  window.addEventListener('resize', () => {
    const r = root.getBoundingClientRect();
    move(r.left, r.top);
  }, {
    signal: life.signal
  });

  function applyPolicy(value) {
    const old = policy;
    policy = {
      ...policy,
      ...value
    };
    if (!policy.enabled && job) cancel();
    if (job && ((!policy.auto_read && old.auto_read && job.type !== 'follow') || (!policy.auto_asr && job.listening))) cancel();
    if (!policy.enabled) {
      position();
      root.hidden = true;
    } else if (root.hidden) {
      root.hidden = false;
      const o = origin(),
        p = lastPosition;
      if (p) move(o.x + p.x, o.y + p.y);
    }
  }

  function readPolicy() {
    try {
      const value = JSON.parse(document.getElementById('docpup-policy')?.textContent || '{}');
      applyPolicy(value);
    } catch (_) {}
  }
  async function refreshPolicy() {
    try {
      const response = await fetch('/docpup/config/', {
        cache: 'no-store'
      });
      if (response.ok && !response.redirected) applyPolicy(await response.json());
    } catch (_) {}
  }
  const policyTimer = setInterval(refreshPolicy, 10000);
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) refreshPolicy();
  }, {
    signal: life.signal
  });
  window.docPup = {
    mount,
    beforePageChange,
    cancel,
    dispose() {
      cancel();
      life.abort();
      clearInterval(policyTimer);
    },
    readingUnits
  };
  try {
    const p = JSON.parse(sessionStorage.getItem('docpup-position'));
    if (p) {
      const o = origin();
      move(o.x + p.x, o.y + p.y);
    }
  } catch (_) {}
  idle();
  localize();
  readPolicy();
  new window.DocPupRig(root);
})();
