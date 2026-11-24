function portalScriptLoaded(src) {
  const path = new URL(src, location.href).pathname;
  return (path.endsWith('/vendor/chart.umd.min.js') && !!window.Chart) ||
    (path.endsWith('/docpup-rig-v4.js') && !!window.DocPupRig) ||
    (path.endsWith('/docpup-audio.js') && !!window.DocPupAudio) ||
    (path.endsWith('/docpup.js') && !!window.docPup);
}
function initPortal() {
if (window.portalInitializedBody === document.body) return;
window.portalInitializedBody = document.body;
window.portalController?.abort();
window.portalController=new AbortController();
// Navigation reloads the inner workspace, whose scroll position browsers do not restore.
if (document.querySelector("[data-user-management]")) {
  const key = "health-user-list-scroll";
  const workspace = document.querySelector(".workspace");
  try {
    const saved = JSON.parse(sessionStorage.getItem(key) || "null");
    sessionStorage.removeItem(key);
    if (saved && saved.path === location.pathname && Date.now() - saved.time < 120000) {
      requestAnimationFrame(() => {
        if (workspace) workspace.scrollTop = saved.top;
        else window.scrollTo(0, saved.top);
      });
    }
  } catch (_) { /* Storage may be unavailable; ordinary navigation still works. */ }
  function rememberScroll(event) {
    if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    try {
      sessionStorage.setItem(key, JSON.stringify({
        path:location.pathname, top:workspace ? workspace.scrollTop : window.scrollY, time:Date.now()
      }));
    } catch (_) { /* Do not prevent the requested action when storage is disabled. */ }
  }
  document.querySelectorAll("form[data-preserve-scroll]").forEach(form =>
    form.addEventListener("submit", rememberScroll));
  document.querySelectorAll("a[data-preserve-scroll], [data-user-management] .pager a").forEach(link =>
    link.addEventListener("click", rememberScroll));
}
const settingsTabs = document.querySelectorAll("[data-settings-tab]");
document.querySelectorAll('[data-settings-panel="docpup"] > label.inline').forEach(label=>{
  label.addEventListener('click',event=>{if(event.target===label)event.preventDefault();});
});
function selectSettings(name) {
  settingsTabs.forEach(tab => tab.setAttribute("aria-selected", String(tab.dataset.settingsTab === name)));
  document.querySelectorAll("[data-settings-panel]").forEach(panel => panel.hidden = panel.dataset.settingsPanel !== name);
  try { sessionStorage.setItem("health-settings-tab",name); }
  catch (_) { /* Tabs still work when browser storage is unavailable. */ }
}
settingsTabs.forEach(tab => tab.addEventListener("click",()=>selectSettings(tab.dataset.settingsTab)));
if (settingsTabs.length) {
  let saved;
  try { saved = sessionStorage.getItem("health-settings-tab"); }
  catch (_) { /* Use the default tab when browser storage is unavailable. */ }
  selectSettings([...settingsTabs].some(tab => tab.dataset.settingsTab === saved)?saved:"accounts");
}
const menu = document.querySelector(".menu");
menu?.addEventListener("click", () => {
  const open = document.querySelector("#navigation").classList.toggle("open");
  menu.setAttribute("aria-expanded", String(open));
});
const language = document.querySelector(".language");
language?.addEventListener("submit", async event => {
  const choice = event.submitter;
  if (!choice || choice.value === language.dataset.language) {
    event.preventDefault();
    return;
  }
  event.preventDefault();
  if (language.dataset.busy) return;
  const pupPosition = window.docPup?.beforePageChange(true);
  language.dataset.busy = "true";
  const previous = language.dataset.language;
  language.dataset.language = choice.value;
  // Preserve editable values by form and field position, never overwrite hidden actions.
  const saved = [...document.forms].map(form => [...form.elements].map(field =>
    field.matches("input:not([type=hidden]):not([type=file]),select,textarea") && !form.matches(".language")
      ? {value:field.value, checked:field.checked} : null));
  const successOpen = !!document.querySelector("[data-success][open]");
  const workspace = document.querySelector(".workspace");
  const scroll = workspace?.scrollTop || window.scrollY;
  const anchor = workspace && [...workspace.querySelectorAll("section,h3,figure")].find(node =>
    node.getBoundingClientRect().bottom > workspace.getBoundingClientRect().top + 12);
  const anchorIndex = anchor ? [...workspace.querySelectorAll("section,h3,figure")].indexOf(anchor) : -1;
  const offset = anchor ? anchor.getBoundingClientRect().top - workspace.getBoundingClientRect().top : 0;
  const payload = new FormData(language);
  payload.set("lang", choice.value);
  try {
    const response = await fetch(language.action, {method:"POST",body:payload,credentials:"same-origin"});
    if (!response.ok) throw new Error("Language update failed");
    const translated = new DOMParser().parseFromString(await response.text(), "text/html");
    document.title = translated.title;
    document.documentElement.lang = translated.documentElement.lang;
    Object.values(window.Chart?.instances || {}).forEach(chart => chart.destroy());
    document.body.replaceWith(translated.body);
    window.docPup?.mount(document.getElementById('docpup'), pupPosition);
    if (!successOpen) document.querySelectorAll("[data-success]").forEach(dialog => dialog.remove());
    [...document.forms].forEach((form, formIndex) => {
      [...form.elements].forEach((field, fieldIndex) => {
        const state = saved[formIndex]?.[fieldIndex];
        if (!state || field.type === "hidden") return;
        if (field.type === "radio" || field.type === "checkbox") field.checked = state.checked;
        else field.value = state.value;
      });
    });
    initPortal();
    for (const script of document.body.querySelectorAll("script[src]")) {
      if (portalScriptLoaded(script.src)) continue;
      const fresh = document.createElement("script");
      fresh.async = false;
      fresh.src = script.src;
      script.replaceWith(fresh);
    }
    const current = document.querySelector(".workspace");
    if (current) {
      const target = current.querySelectorAll("section,h3,figure")[anchorIndex];
      current.scrollTop = target ? target.offsetTop-current.offsetTop-offset : scroll;
    } else window.scrollTo(0,scroll);
  } catch (error) {
    language.dataset.language = previous;
    delete language.dataset.busy;
    const selected = document.createElement("input");
    selected.type = "hidden"; selected.name = "lang"; selected.value = choice.value;
    language.append(selected);
    language.submit();
  }
});

const eye = document.querySelector("[data-eye]");
const password = document.querySelector("#login-password");
if (eye && password) {
  const showLabel = eye.getAttribute("aria-label");
  function reveal(show) {
    password.type = show ? "text" : "password";
    eye.setAttribute("aria-pressed", String(show));
    eye.setAttribute("aria-label", show ? eye.dataset.hide : showLabel);
  }
  password.addEventListener("input", () => { if (!password.value) reveal(false); });
  eye.addEventListener("click", () => reveal(password.type === "password"));
}
document.querySelectorAll("[data-dialog]").forEach(button => {
  button.addEventListener("click", () => document.getElementById(button.dataset.dialog).showModal());
});
document.querySelectorAll("[data-close]").forEach(button => {
  button.addEventListener("click", () => button.closest("dialog").close());
});
document.querySelectorAll("[data-success]").forEach(dialog => {
  dialog.addEventListener("close", () => dialog.remove(), {once:true});
  dialog.showModal();
});
document.querySelector("[data-training]")?.addEventListener("submit", async event => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector(".primary");
  if (button.disabled) return;
  const text = button.textContent;
  const payload = new FormData(form);
  button.disabled = true;
  button.textContent = button.dataset.pending;
  const meter = form.querySelector(".training-progress");
  const error = form.querySelector(".training-error");
  meter.hidden = false;
  error.hidden = true;
  const zh = document.documentElement.lang === "zh-CN";
  try {
    const response = await fetch(location.href, {method:"POST",body:payload,headers:{"X-Training-Progress":"1"}});
    if (!response.ok || !response.headers.get("Content-Type")?.includes("ndjson")) throw new Error("range");
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const {value,done} = await reader.read();
      if (done) break;
      buffer += decoder.decode(value,{stream:true});
      const lines = buffer.split("\n");
      buffer = lines.pop();
      for (const line of lines.filter(Boolean)) {
        const status = JSON.parse(line);
        if (status.error) throw new Error(status.error);
        meter.querySelector("progress").value = status.progress;
        meter.querySelector("output").value = status.progress + "%";
        if (status.url) { location.assign(status.url); return; }
      }
    }
    throw new Error("failed");
  } catch (failure) {
    const reasons = {
      versions:zh?"请选择同一睡眠问卷版本的日期范围。":"Choose a date range with one sleep questionnaire version.",
      samples:zh?"至少需要三组完整记录。":"At least three complete visits are required.",
      classes:zh?"至少需要两个类别。":"At least two classes are required.",
      folds:zh?"交叉验证要求每个类别至少有五组记录。":"Validation needs at least five visits per class.",
      range:zh?"请检查日期范围和算法选项。":"Check the date range and algorithm."
    };
    error.textContent = reasons[failure.message] || (zh?"训练未完成，请重试。":"Training did not complete. Please retry.");
    error.hidden = false;
    button.disabled = false;
    button.textContent = text;
  }
});


}
initPortal();
