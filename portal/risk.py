from bisect import bisect_right
from collections import Counter, defaultdict


MODEL_BP = (
    ("Low risk", "低风险", "low"), ("Moderate risk", "中风险", "medium"), ("High risk", "高风险", "high"),
)
MOOD = (
    ("Low risk", "低风险", "low"), ("Moderate risk", "中风险", "medium"), ("High risk", "高风险", "high"),
)
READING = (
    ("Normal range", "正常范围", "low"), ("High-normal range", "正常高值", "medium"),
    ("Grade 1 range", "1级血压范围", "medium"), ("Grade 2 range", "2级血压范围", "high"),
    ("Grade 3 range", "3级血压范围", "high"), ("Low reading", "读数偏低", "medium"),
    ("Unclassified reading", "未分级读数", "neutral"),
)
COLORS = {"low":"#2ecc71", "medium":"#f39c12", "high":"#e74c3c", "neutral":"#8999a6"}
BP_COLORS = ("#2ecc71","#e9bb36","#f39c12","#e74c3c","#a82435","#c18d20","#8999a6")


def reading_band(systolic, diastolic, age):
    if age is None or age < 18:
        return 6
    for band, (s, d) in enumerate(((180,110),(160,100),(140,90),(120,80))):
        if systolic >= s or diastolic >= d:
            return 4 - band
    return 5 if systolic < 90 or diastolic < 60 else 0


def latest_readings(dates, ages):
    history = defaultdict(list)
    for subject, day, values in ages:
        history[subject].append((day,values["age"]))
    results = {}
    for (subject,day),group in dates.items():
        if "hbp" not in group or (subject in results and results[subject][0] >= day):
            continue
        records = history[subject]
        index = bisect_right(records,(day,float("inf")))
        age = records[index-1][1] if index else None
        s, d = (group["hbp"][key] for key in ("systolic_bp","diastolic_bp"))
        band = reading_band(s,d,age)
        results[subject] = (day,band,f"{s:g}/{d:g} mmHg",None)
    return results


def distribution(results, bands, loc):
    counts = Counter(r[1] for r in results.values())
    rows, stops = [], []
    total, offset = len(results), 0
    for index,(en,zh,tone) in enumerate(bands):
        n = counts[index]
        pct = 100*n/total if total else 0
        color = BP_COLORS[index] if bands is READING else COLORS[tone]
        rows.append(dict(label=loc(en,zh),count=n,percent=f"{pct:.1f}%",color=color))
        if n:
            stops.append(f"{color} {offset:.5f}% {offset+pct:.5f}%")
            offset += pct
    gradient = "conic-gradient("+", ".join(stops)+")" if len(stops)>1 else next((r["color"] for r in rows if r["count"]),"#e9edf1")
    return rows,gradient
