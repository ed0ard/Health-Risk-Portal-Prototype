from io import BytesIO
from base64 import b64encode
from dataclasses import dataclass
import json
from math import ceil, cos, pi, sin

from django.http import FileResponse
from reportlab.lib import colors
from reportlab.graphics import renderSVG
from reportlab.graphics.shapes import Drawing, Group, Line, Polygon, PolyLine, String, Circle
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Flowable, KeepTogether, SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from xml.sax.saxutils import escape

from .catalog import FIELDS, KINDS, LEGACY_SLEEP
from .models import Record, SiteOptions
from .learning import REQUIRED, features, predict, active_fit


FONT = "STSong-Light"
if FONT not in pdfmetrics.getRegisteredFontNames():
    pdfmetrics.registerFont(UnicodeCIDFont(FONT))

AXES = {
    "depre": [("Low mood","情绪低落"),("Loss of interest","失去兴趣"),("Low energy","精力减少"),
              ("Sleep disruption","睡眠障碍"),("Appetite","食欲变化"),("Worthlessness","无用感"),
              ("Attention","注意力差"),("Discomfort","身体不适"),("Self-harm thoughts","自伤念头")],
    "psqi": [("Night waking","夜间醒来"),("Early waking","早醒"),("Sleep aids","药物助眠"),
             ("Daytime sleepiness","白天困倦"),("Sleep dissatisfaction","睡眠不满意"),
             ("Daytime impact","日间活动"),("Mood impact","情绪影响")],
}


@dataclass
class Chart:
    title: str
    drawing: Drawing
    detail: dict

    @property
    def image(self):
        svg = renderSVG.drawToString(self.drawing).replace("STSong-Light", "Arial, Microsoft YaHei, sans-serif")
        return "data:image/svg+xml;base64," + b64encode(svg.encode()).decode()

    @property
    def tooltip(self):
        return json.dumps(self.detail, ensure_ascii=False)


def text_at(d, x, y, text, size=11, anchor="middle", color="#40454a"):
    d.add(String(x, y, str(text), fontName=FONT, fontSize=size, textAnchor=anchor, fillColor=colors.HexColor(color)))


def radar_chart(kind, row, loc, version="source"):
    labels = LEGACY_SLEEP if kind=="psqi" and version=="legacy" else AXES[kind]
    axes = [loc(*label) for label in labels]
    day, values = row[0], row[1:-1]
    d = Drawing(380, 263)
    cx, cy, radius = 190, 129, 94

    def points(scores):
        coords = []
        for i, value in enumerate(scores):
            angle = 2*pi*i/len(axes)
            coords.extend([cx-sin(angle)*radius*value/3, cy+cos(angle)*radius*value/3])
        return coords

    grid = colors.HexColor("#ced1d3")
    for level in (1,2,3):
        d.add(Polygon(points([level]*len(axes)),strokeColor=grid,fillColor=None,strokeWidth=.8))
    for i, label in enumerate(axes):
        angle = 2*pi*i/len(axes)
        dx,dy = -sin(angle),cos(angle)
        d.add(Line(cx,cy,cx+radius*dx,cy+radius*dy,strokeColor=grid,strokeWidth=.8))
        anchor = "middle" if abs(dx)<.22 else "start" if dx>0 else "end"
        text_at(d,cx+(radius+9)*dx,cy+(radius+12)*dy-3,label,10.4,anchor)
    vertices = points(values)
    ink = colors.HexColor("#515151")
    d.add(Polygon(vertices,fillColor=colors.Color(.41,.41,.41,alpha=.42),strokeColor=ink,strokeWidth=.85))
    for x,y in zip(vertices[::2],vertices[1::2]):
        d.add(Circle(x,y,2.1,fillColor=ink,strokeColor=ink))
    title = loc("Mood assessment","抑郁评估") if kind=="depre" else loc("Sleep assessment","睡眠评估")
    return Chart(f"{title} - {day}",d,{"labels":axes,"rows":[[day,*values]]})


def display(field, value, loc):
    if field.choices:
        return loc(*field.choices[int(value)])
    return f"{value:.2f}".rstrip("0").rstrip(".") if isinstance(value,float) else value


def baseline_rows(subject, record, loc):
    values = record.values
    bmi = values["weight"] / (values["height"] / 100) ** 2
    badge, tone = "", "neutral"
    if values["age"] >= 18:
        categories = [
            (18.5, "Underweight", "体重过低", "medium"),
            (24, "Normal", "正常", "low"),
            (28, "Overweight", "超重", "medium"),
            (float("inf"), "Obesity", "肥胖", "high"),
        ]
        _, en, zh, tone = next(item for item in categories if bmi < item[0])
        badge = loc(en, zh)
    else:
        badge = loc("Age-specific assessment required", "需按年龄评估")
    fields = {field.key: field for field in FIELDS["baseline"]}
    def field(key):
        return display(fields[key], values[key], loc)
    return [
        dict(label=loc("User ID", "用户ID"), value=subject),
        dict(label=loc("Sex", "性别"), value=field("gender")),
        dict(label=loc("Age", "年龄"), value=f"{values['age']} " + loc("years", "岁")),
        dict(label=loc("Height", "身高"), value=f"{field('height')} cm"),
        dict(label=loc("Weight", "体重"), value=f"{field('weight')} kg"),
        dict(label="BMI", value=f"{bmi:.1f}", badge=badge, tone=tone),
        dict(label=loc("Smoking", "吸烟情况"), value=field("smoking")),
        dict(label=loc("Alcohol use", "饮酒情况"), value=field("drinking")),
        dict(label=loc("Record date", "数据时间"), value=record.day.isoformat()),
    ]


def sections(subject, loc):
    result = []
    options, _ = SiteOptions.objects.get_or_create(pk=1)
    for kind, names in KINDS.items():
        fields = FIELDS[kind]
        questionnaire = kind in ("depre", "psqi")
        headers = [loc("Date","日期")]
        if questionnaire:
            headers += [loc("Q","题")+str(i) for i in range(1,len(fields)+1)] + [loc("Total","总分")]
        else:
            headers += [loc(f.en,f.zh) for f in fields]
        if kind == "baseline":
            headers.append("BMI")
        rows, series, baseline = [], [], []
        records = Record.objects.filter(subject=subject, kind=kind).order_by("day")
        if kind=="baseline":
            records = records.order_by("-day")[:1]
        versions = []
        for r in records:
            versions.append(r.form_version)
            v = r.values
            day = r.day.isoformat()
            if questionnaire:
                answers = [v[f.key] for f in fields]
                rows.append([day,*answers,sum(answers)])
                series.append([day,sum(answers)])
            else:
                row = [day]+[display(f,v[f.key],loc) for f in fields]
                if kind == "baseline":
                    baseline = baseline_rows(subject, r, loc)
                    row.append(round(v["weight"]/(v["height"]/100)**2,1))
                else:
                    series.append([day,v["systolic_bp"],v["diastolic_bp"]])
                rows.append(row)
        part = dict(kind=kind,title=loc(*names),headers=headers,rows=rows,series=series,baseline=baseline,
                    institution=getattr(options,"report_institution",""),footer=getattr(options,"report_footer",""))
        part["radars"] = [radar_chart(kind,row,loc,version) for row,version in zip(rows,versions)] if questionnaire and getattr(options,"report_charts",True) else []
        part["trend"] = trend_chart(kind,series,loc) if series and getattr(options,"report_charts",True) else None
        result.append(part)
    age_fit = active_fit("age")
    if age_fit:
        visits = {}
        for record in Record.objects.filter(subject=subject):
            group = visits.setdefault(record.day,{})
            group[record.kind]=record.values
            if record.kind=="psqi":
                group["_sleep_version"]=record.form_version
        complete = [(day,group) for day,group in sorted(visits.items()) if all(t in group for t in REQUIRED["age"]) and group.get("_sleep_version","legacy")==age_fit.artifact.get("form_version","legacy")]
        rows = []
        if complete:
            if age_fit.artifact.get("engine")=="source":
                from .original_models import source_predictions
                scores=source_predictions("age",age_fit,[(subject,g) for _,g in complete])
            else:
                scores=predict(age_fit.artifact,[features("age",g) for _,g in complete])
            rows=[[day.isoformat(),*[round(float(v),3) for v in row]] for (day,_),row in zip(complete,scores)]
        result.append(dict(kind="age",title=loc("Biological age model · component scores","生物年龄模型 · 主成分得分"),
                           headers=[loc("Date","日期"),"PC1","PC2","PC3"],rows=rows,axes=[],series=[]))
    return result


def trend_chart(kind, series, loc):
    width,height = 760,245
    left,right,bottom,top = 70,635,51,198
    d = Drawing(width,height)
    if kind == "hbp":
        title, unit = loc("Blood pressure trend","血压变化趋势"),"mmHg"
        labels = [loc("Systolic","收缩压"),loc("Diastolic","舒张压")]
        palette = ["#e64b3c","#27a562"]
        refs = [(140,"SBPmax: 140","#2ba464"),(90,"SBPmin/DBPmax: 90","#2ba464"),(60,"DBPmin: 60","#318fcb")]
        values = [v for row in series for v in row[1:]]
        low = int(min(40,10*(min(values)//10)))
        high = max(180,30*ceil(max(values)/30))
        ticks = sorted(set([low]+list(range(30*ceil(low/30),high+1,30))))
    else:
        mood = kind=="depre"
        title = loc("Mood score trend","抑郁总分变化趋势") if mood else loc("Sleep score trend","睡眠总分变化趋势")
        unit = loc("Score","总分（分）")
        labels,palette = [loc("Total score","总分")],["#3498db" if mood else "#9255a7"]
        levels = (10,20,27) if mood else (7,14,21)
        labels_ref = [loc("Score marker", "得分参考"),loc("Score marker", "得分参考"),loc("Maximum score", "量表满分")]
        refs = [(v,f"{label}: {v}",color) for v,label,color in zip(levels,labels_ref,["#d5ae19","#d27726","#d44d4b"])]
        low,high = 0,levels[-1]
        ticks = [*range(0,high,5),high]

    def x(i):
        return left+(right-left)*(i/(len(series)-1) if len(series)>1 else .5)

    def y(value):
        return bottom+(top-bottom)*(value-low)/(high-low)

    text_at(d,left-13,top+16,unit,11,"start")
    for value in ticks:
        d.add(Line(left,y(value),right,y(value),strokeColor=colors.HexColor("#dedfe2"),strokeDashArray=[2,3],strokeWidth=.5))
        text_at(d,left-7,y(value)-3,value,10,"end")
    d.add(Line(left,bottom,right,bottom,strokeColor=colors.grey,strokeWidth=.8))
    for value,label,color in refs:
        hue=colors.HexColor(color)
        yy=y(value)
        d.add(Line(left,yy,right-4,yy,strokeColor=hue,strokeDashArray=[4,3],strokeWidth=.95))
        d.add(Polygon([right,yy,right-8,yy+3,right-6,yy,right-8,yy-3],fillColor=hue,strokeColor=hue))
        d.add(Circle(left,yy,2.2,fillColor=hue,strokeColor=hue))
        text_at(d,right+6,yy-3,label,10,"start")
    for j,(label,color) in enumerate(zip(labels,palette),1):
        hue=colors.HexColor(color)
        pts = [(x(i),y(row[j])) for i,row in enumerate(series)]
        if len(pts)>1:
            d.add(PolyLine([v for point in pts for v in point],strokeColor=hue,strokeWidth=2))
        for xx,yy in pts:
            d.add(Circle(xx,yy,2.5,fillColor=hue,strokeColor=hue))
        if kind=="hbp":
            xx=width/2-85+96*(j-1)
            d.add(Line(xx,226,xx+19,226,strokeColor=hue,strokeWidth=1.6))
            d.add(Circle(xx+9,226,3,fillColor=hue,strokeColor=hue))
            text_at(d,xx+23,223,label,11,"start")
    stride = max(1,ceil(len(series)/8))
    for i in range(0,len(series),stride):
        group=Group()
        group.translate(x(i),bottom-8)
        group.rotate(30)
        text_at(group,0,0,series[i][0],10,"end")
        d.add(group)
    detail = {"labels":labels,"rows":series,"range":[left/width,right/width,1-top/height,1-bottom/height],"unit":unit if kind=="hbp" else ""}
    return Chart(title,d,detail)


def scaled_drawing(drawing, width):
    scale = min(1, width / drawing.width)
    wrapped = Drawing(drawing.width * scale, drawing.height * scale)
    group = Group(drawing)
    group.scale(scale, scale)
    wrapped.add(group)
    return wrapped


class ReportBadge(Flowable):
    def __init__(self, text, font, background):
        super().__init__()
        self.text, self.font = text, font
        self.background = colors.HexColor(background)
        self.width = pdfmetrics.stringWidth(text,font,9) + 12
        self.height = 17

    def draw(self):
        self.canv.setFillColor(self.background)
        self.canv.roundRect(0,0,self.width,self.height,3,fill=1,stroke=0)
        self.canv.setFillColor(colors.white)
        self.canv.setFont(self.font,9)
        self.canv.drawString(6,5,self.text)


def pdf_report(subject, parts, loc):
    options, _ = SiteOptions.objects.get_or_create(pk=1)
    font = "Helvetica" if loc("en","zh") == "en" else FONT
    content = BytesIO()
    pagesize = landscape(A4) if getattr(options, "report_orientation", "portrait") == "landscape" else A4
    pdf = SimpleDocTemplate(content,pagesize=pagesize,leftMargin=36,rightMargin=36,topMargin=40,bottomMargin=42)
    heading = ParagraphStyle("heading",fontName=font,fontSize=15,leading=21,textColor=colors.HexColor("#253b51"),keepWithNext=True)
    cell = ParagraphStyle("cell",fontName=font,fontSize=9,leading=13)
    white = ParagraphStyle("white",parent=cell,textColor=colors.white)
    footer_style = ParagraphStyle("footer",parent=cell,fontSize=8,leading=10,textColor=colors.HexColor("#526575"))
    institution = getattr(options, "report_institution", "")
    footer = getattr(options, "report_footer", "")
    label = loc("Health report","健康数据报告")
    story = []
    if institution:
        story.append(Paragraph(escape(institution),heading))
    story.append(Paragraph(escape(f"{subject} {label}"),heading))
    blue = colors.HexColor("#3498db")
    for number,part in enumerate(parts,1):
        story.extend([Spacer(1,14),Paragraph(escape(f"{number}. {part['title']}"),heading),Spacer(1,6)])
        if not part["rows"]:
            story.append(Paragraph(loc("No records","暂无记录"),cell))
            continue
        if part.get("baseline"):
            data = []
            badge_colors = {"low":"#229954","medium":"#bd7d0c","high":"#e74c3c","neutral":"#6f7c86"}
            for field in part["baseline"]:
                value = Paragraph(escape(str(field["value"])),cell)
                if field.get("badge"):
                    badge = ReportBadge(field["badge"],font,badge_colors[field["tone"]])
                    value = Table([[value,badge]],colWidths=[pdfmetrics.stringWidth(str(field["value"]),font,9)+10,badge.width])
                    value.setStyle(TableStyle([("LEFTPADDING",(0,0),(-1,-1),0),
                        ("RIGHTPADDING",(0,0),(-1,-1),4),("TOPPADDING",(0,0),(-1,-1),0),
                        ("BOTTOMPADDING",(0,0),(-1,-1),0),("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
                data.append([Paragraph(escape(field["label"]),white),value])
            table = Table(data,colWidths=[pdf.width*.32,pdf.width*.68])
            style = [("BACKGROUND",(0,0),(0,-1),blue)]
        else:
            data = [[Paragraph(escape(str(x)),white) for x in part["headers"]]]
            data += [[Paragraph(escape(str(x)),cell) for x in row] for row in part["rows"]]
            first = min(80,pdf.width*.2)
            widths = [first]+[(pdf.width-first)/(len(data[0])-1)]*(len(data[0])-1)
            table = Table(data,repeatRows=1,colWidths=widths)
            style = [("BACKGROUND",(0,0),(-1,0),blue)]
        table.setStyle(TableStyle(style+[
            ("GRID",(0,0),(-1,-1),.3,colors.HexColor("#dce3e8")),
            ("VALIGN",(0,0),(-1,-1),"TOP"),("TOPPADDING",(0,0),(-1,-1),6),
            ("BOTTOMPADDING",(0,0),(-1,-1),6),
        ]))
        story.append(table)
        radars = part.get("radars",[])
        for i in range(0,len(radars),2):
            width = pdf.width/2
            pair = [[Paragraph(escape(chart.title),cell),scaled_drawing(chart.drawing,width-8)] for chart in radars[i:i+2]]
            story.append(Table([pair],colWidths=[width]*len(pair),style=TableStyle([
                ("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0)])))
        if part.get("trend"):
            chart = part["trend"]
            story.append(KeepTogether([Spacer(1,12),Paragraph(escape(chart.title),heading),scaled_drawing(chart.drawing,pdf.width)]))
    def draw_footer(canvas, document):
        canvas.saveState()
        if footer:
            paragraph = Paragraph(escape(footer),footer_style)
            _,height = paragraph.wrap(document.width-35,28)
            paragraph.drawOn(canvas,document.leftMargin,max(14,32-height))
        canvas.setFont(font,8)
        canvas.drawRightString(pagesize[0]-36,18,str(document.page))
        canvas.restoreState()
    pdf.build(story,onFirstPage=draw_footer,onLaterPages=draw_footer)
    content.seek(0)
    return FileResponse(content,as_attachment=True,filename=f"health-report-{subject}.pdf")
