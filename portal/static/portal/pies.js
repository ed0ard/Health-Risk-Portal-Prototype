document.querySelectorAll("[data-pie]").forEach(canvas => {
  if (Chart.getChart(canvas)) return;
  const data=JSON.parse(canvas.dataset.pie);
  new Chart(canvas,{
    type:"pie",
    data:{labels:data.labels,datasets:[{data:data.values,backgroundColor:data.colors,borderColor:"#fff",borderWidth:2}]},
    options:{
      responsive:true,maintainAspectRatio:false,
      animation:matchMedia("(prefers-reduced-motion: reduce)").matches?false:{duration:300},
      plugins:{
        legend:{position:"top",labels:{boxWidth:24,padding:14,font:{size:14}}},
        tooltip:{callbacks:{label:item=>{
          const total=data.values.reduce((a,b)=>a+b,0);
          return item.label+": "+item.raw+" ("+(total?100*item.raw/total:0).toFixed(1)+"%)";
        }}}
      }
    }
  });
});
