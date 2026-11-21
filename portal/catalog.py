from dataclasses import dataclass


@dataclass(frozen=True)
class Field:
    key: str
    en: str
    zh: str
    lo: float = 0
    hi: float = 3
    step: str = "1"
    choices: tuple = ()


YES = (("No", "否"), ("Yes", "是"))
SEX = (("Female", "女"), ("Male", "男"))
MOOD_FREQ = (("Almost never (less than 1 day)", "几乎从未（1天以下）"),
             ("Occasionally (2–3 days)", "偶尔（2–3天）"),
             ("Sometimes (4–7 days)", "有时（4–7天）"),
             ("Nearly every day (10 days or more)", "几乎每天（10天及以上）"))
SLEEP_FREQ = (("Almost never (less than once a week)", "几乎从未（少于1次/周）"),
              ("Occasionally (1–2 times a week)", "偶尔（1–2次/周）"),
              ("Sometimes (3–4 times a week)", "有时（3–4次/周）"),
              ("Almost always (5–7 times a week)", "几乎总是（5–7次/周）"))
MOOD = (
    ("In the past two weeks, have you often felt down, depressed or hopeless?", "在过去的两周内，你是否经常感到情绪低落、沮丧或绝望？"),
    ("Have you lost interest or pleasure in things you used to enjoy, such as hobbies or social activities?", "你是否对以前感兴趣的事物，如爱好、社交活动等，失去了兴趣或乐趣？"),
    ("Have you noticed a clear decrease in energy during daily activities or become tired easily?", "你是否感觉自己在日常活动中的精力明显减少，容易疲劳？"),
    ("Have you had sleep difficulties, such as insomnia, waking early or sleeping too much?", "你是否有睡眠障碍，如失眠、早醒或睡眠过多的情况？"),
    ("Has your appetite changed noticeably, such as eating less or overeating?", "你的食欲是否发生了明显变化，如食欲减退或暴饮暴食？"),
    ("Have you felt disappointed in yourself or felt that you were worthless?", "你是否经常感到自己很无用、内疚或对自己的价值产生怀疑？"),
    ("Have you found it difficult to concentrate on activities such as reading or working?", "你是否觉得自己难以集中注意力，思维迟缓或变得优柔寡断？"),
    ("Have you experienced physical discomfort, such as headaches or other aches and pains?", "你是否感到身体不适，如头痛、胃痛或其他不明原因的疼痛？"),
    ("Have you had thoughts of hurting yourself or ending your life?", "你是否反复出现自杀的念头或有自残的行为？"),
)
SLEEP = (
    ("In the past month, have you often woken during the night and had difficulty falling asleep again?", "过去一个月，您是否经常在夜间醒来后难以再次入睡？"),
    ("In the past month, have you often woken earlier than intended?", "过去一个月，您是否经常比期望的时间早醒？"),
    ("In the past month, have you often needed medication to fall asleep?", "过去一个月，您是否经常需要借助药物才能入睡？"),
    ("In the past month, have you often felt sleepy during the day?", "过去一个月，您是否经常在白天感到困倦？"),
    ("In the past month, have you often felt dissatisfied with your sleep quality?", "过去一个月，您是否经常对自己的睡眠质量不满意？"),
    ("In the past month, have sleep problems often affected your daytime activities?", "过去一个月，您是否经常因为睡眠问题而影响白天的活动？"),
    ("In the past month, have sleep problems often made you feel low or irritable?", "过去一个月，您是否经常因为睡眠问题而情绪低落或易怒？"),
)
KINDS = {"baseline": ("Baseline", "基线数据"), "hbp": ("Blood Pressure", "高血压量表"),
         "depre": ("Mood Questionnaire", "抑郁量表"), "psqi": ("Sleep Questionnaire", "睡眠量表")}
FIELDS = {
    "baseline": (Field("age","Age","年龄",18,125), Field("gender","Sex","性别",0,1,choices=SEX),
                 Field("height","Height (cm)","身高 (cm)",100,270,"any"), Field("weight","Weight (kg)","体重 (kg)",20,350,"any"),
                 Field("smoking","Smoking","吸烟",0,1,choices=YES), Field("drinking","Alcohol use","饮酒",0,1,choices=YES)),
    "hbp": (Field("systolic_bp","Systolic (mmHg)","收缩压 (mmHg)",40,300,"any"),
            Field("diastolic_bp","Diastolic (mmHg)","舒张压 (mmHg)",30,200,"any"),
            Field("hbp_family","Family history of hypertension","高血压家族史",0,1,choices=YES)),
    "depre": tuple(Field(f"depre_question_{i}",en,zh,choices=MOOD_FREQ) for i,(en,zh) in enumerate(MOOD,1)),
    "psqi": tuple(Field(f"psqi_question_{i}",en,zh,choices=SLEEP_FREQ) for i,(en,zh) in enumerate(SLEEP,1)),
}
NAV = {
    "home": ("Overview", "健康概览"), "entry": ("Health Data Entry", "健康数据录入"),
    "query": ("Health Records", "健康数据查询"), "report": ("Health Report", "健康报告生成"),
    "alerts": ("Health Alerts", "健康预警"), "training": ("Model Training", "健康模型训练"),
    "users": ("User Management", "用户管理"), "settings": ("System Settings", "系统设置"),
    "logs": ("Activity Log", "系统日志"), "password": ("Change Password", "修改密码"),
}
EVENTS = {"login": ("Signed In", "登录系统"), "entry": ("Saved A Health Record", "保存健康数据"),
          "report": ("Opened A Health Report", "查看健康报告"), "password": ("Changed Password", "修改密码"),
          "training": ("Trained A Model", "训练模型"), "users": ("Updated User Account", "更新用户账户"),
          "settings": ("Updated Settings", "更新设置")}
MODEL_NAMES = {"hbp": ("Hypertension Risk", "高血压风险预测"), "depre": ("Depression Risk", "抑郁风险预测"),
               "age": ("Biological Age Assessment", "生物年龄评估")}

LEGACY_SLEEP = (
    ("Night Waking", "夜间醒来"),("Sleep onset over 30 minutes","入睡超过30分钟"),
    ("Sleep Under Six Hours", "睡眠不足六小时"),("Frequent Waking", "频繁夜间醒来"),
    ("Early Waking", "早醒"),("Sleep Medication", "使用安眠药"),("Daytime Impact", "日间影响"),
)


def record_fields(record):
    if record.kind == "psqi" and record.form_version == "legacy":
        return tuple(Field(f"psqi_question_{i}",en,zh,choices=SLEEP_FREQ)
                     for i,(en,zh) in enumerate(LEGACY_SLEEP,1))
    return FIELDS[record.kind]
