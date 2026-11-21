function initPortal() {
window.portalController?.abort();
window.portalController=new AbortController();
const settingsTabs = document.querySelectorAll("[data-settings-tab]");
function selectSettings(name) {
  settingsTabs.forEach(tab => tab.setAttribute("aria-selected", String(tab.dataset.settingsTab === name)));
  document.querySelectorAll("[data-settings-panel]").forEach(panel => panel.hidden = panel.dataset.settingsPanel !== name);
  sessionStorage.setItem("health-settings-tab",name);
}
settingsTabs.forEach(tab => tab.addEventListener("click",()=>selectSettings(tab.dataset.settingsTab)));
if (settingsTabs.length) {
  const saved = sessionStorage.getItem("health-settings-tab");
  selectSettings(["accounts","models","reset"].includes(saved)?saved:"accounts");
}
const search = document.querySelector(".member-search input");
if (search) {
  const names=JSON.parse(document.getElementById("member-names").textContent);
  const matches=document.getElementById("member-matches");
  function choose(name) { search.value=name; matches.hidden=true; search.setAttribute("aria-expanded","false"); search.focus(); }
  function suggest() {
    matches.replaceChildren();
    const value=search.value.trim().toLowerCase();
    if (!value) {matches.hidden=true; search.setAttribute("aria-expanded","false"); return;}
    names.filter(name=>name.toLowerCase().includes(value)).slice(0,12).forEach((name,index)=>{
      const option=document.createElement("button");
      option.type="button"; option.setAttribute("role","option"); option.textContent=name;
      option.addEventListener("click",()=>choose(name));
      option.addEventListener("keydown",event=>{
        if(event.key==="ArrowDown"){event.preventDefault();option.nextElementSibling?.focus();}
        if(event.key==="ArrowUp"){event.preventDefault();(option.previousElementSibling||search).focus();}
        if(event.key==="Escape"){matches.hidden=true;search.focus();}
      });
      matches.append(option);
    });
    matches.hidden=!matches.children.length;
    search.setAttribute("aria-expanded",String(!matches.hidden));
  }
  search.addEventListener("input",suggest);
  search.addEventListener("keydown",event=>{
    if(event.key==="ArrowDown"){event.preventDefault();matches.querySelector("button")?.focus();}
    if(event.key==="Escape"){matches.hidden=true;search.setAttribute("aria-expanded","false");}
  });
  document.addEventListener("pointerdown",event=>{
    if(!search.parentElement.contains(event.target)){matches.hidden=true;search.setAttribute("aria-expanded","false");}
  },{signal:window.portalController.signal});
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
  language.dataset.busy = "true";
  const previous = language.dataset.language;
  language.dataset.language = choice.value;
  const fields = [...document.querySelectorAll("input,select,textarea")].filter(field =>
    field.name && field.name !== "csrfmiddlewaretoken" && !field.closest(".language"));
  const saved = fields.map(field => ({
    name:field.name, type:field.type, value:field.value, checked:field.checked
  }));
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
    for (const state of saved) {
      const matches = [...document.getElementsByName(state.name)];
      for (const field of matches) {
        if (state.type === "radio" || state.type === "checkbox") {
          if (field.value === state.value) field.checked = state.checked;
        } else field.value = state.value;
      }
    }
    initPortal();
    for (const script of document.body.querySelectorAll("script[src]")) {
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
document.querySelector("[data-success]")?.showModal();
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
