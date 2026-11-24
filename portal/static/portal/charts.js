document.querySelectorAll(".report [data-chart]").forEach(figure => {
  const chart = JSON.parse(figure.dataset.chart);
  const image = figure.querySelector("img");
  if (!chart.rows?.length || !image) return;
  const tip = document.createElement("div");
  tip.className = "chart-tip";
  tip.hidden = true;
  figure.append(tip);
  const guide = chart.range ? document.createElement("span") : null;
  if (guide) {
    guide.className = "trend-cursor";
    guide.hidden = true;
    figure.append(guide);
  }
  let selected = 0;
  let rendered = -1;
  let pendingFrame = 0;
  function hide() {
    cancelAnimationFrame(pendingFrame);
    pendingFrame = 0;
    tip.hidden = true;
    if (guide) guide.hidden = true;
  }
  function show(index, x, y) {
    selected = index;
    const row = chart.rows[index];
    if (rendered !== index) {
    rendered = index;
    const date = document.createElement("b");
    date.textContent = row[0];
    tip.replaceChildren(date);
    chart.labels.forEach((label,i) => {
      const line = document.createElement("div");
      const value = document.createElement("strong");
      value.textContent = Number(row[i+1].toFixed(2)) + (chart.unit ? " " + chart.unit : "");
      line.append(label,value);
      tip.append(line);
    });
    }
    if (guide) {
      const bounds = image.getBoundingClientRect();
      const frame = figure.getBoundingClientRect();
      const ratio = chart.rows.length === 1 ? .5 : index / (chart.rows.length - 1);
      const [left,right,top,bottom] = chart.range;
      const position = bounds.left-frame.left + (left+ratio*(right-left))*bounds.width;
      const strip = image.parentElement.getBoundingClientRect();
      guide.hidden = frame.left+position < strip.left || frame.left+position > strip.right;
      guide.style.left = position + "px";
      guide.style.top = bounds.top-frame.top+top*bounds.height + "px";
      guide.style.height = (bottom-top)*bounds.height + "px";
    }
    tip.hidden = false;
    tip.style.left = Math.max(0, Math.min(x,figure.clientWidth-tip.offsetWidth)) + "px";
    tip.style.top = Math.max(0, Math.min(y,figure.clientHeight-tip.offsetHeight)) + "px";
  }
  figure.addEventListener("pointermove", event => {
    cancelAnimationFrame(pendingFrame);
    pendingFrame = requestAnimationFrame(() => {
    pendingFrame = 0;
    if (!figure.isConnected) return;
    const bounds = image.getBoundingClientRect();
    const frame = figure.getBoundingClientRect();
    let index = 0;
    if (chart.range) {
      const [start,end] = chart.range;
      const relative = ((event.clientX-bounds.left)/bounds.width-start)/(end-start);
      index = Math.round(Math.max(0,Math.min(1,relative))*(chart.rows.length-1));
    }
    show(index, event.clientX-frame.left+12, event.clientY-frame.top+12);
    });
  });
  figure.addEventListener("pointerleave", hide);
  figure.addEventListener("focus", () => show(selected,12,32));
  figure.addEventListener("blur", hide);
  figure.addEventListener("keydown", event => {
    if (event.key === "Escape") { hide(); return; }
    const delta = {ArrowLeft:-1,ArrowRight:1}[event.key];
    if (!delta) return;
    event.preventDefault();
    show(Math.max(0,Math.min(chart.rows.length-1,selected+delta)),12,32);
  });
});
