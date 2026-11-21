from functools import lru_cache
from pathlib import Path
from uuid import uuid4

import joblib
import numpy as np
import pandas as pd
from django.conf import settings
from sklearn.decomposition import PCA
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_score
from xgboost import XGBClassifier

from training.trainModel import ModelTrainer
from .catalog import FIELDS
from .models import Fit


TABLES = {"hbp":("baseline","hbp"),"depre":("baseline","depre","psqi"),
          "age":("baseline","depre","psqi","hbp")}


def frame(kind, visits):
    rows = []
    for subject, group in visits:
        row = {"user_id":str(subject)}
        for table in TABLES[kind]:
            row.update(group[table])
        rows.append(row)
    return pd.DataFrame(rows)


def train_original(kind, cases, start, end, validate, progress, version):
    trainer = ModelTrainer.__new__(ModelTrainer)
    trainer.model_id = {"hbp":"1","depre":"2","age":"3"}[kind]
    trainer.data = frame(kind,cases)
    x,y = trainer._preprocess_data()
    classes = None
    if y is not None:
        classes, counts = np.unique(y, return_counts=True)
        if len(classes) < 2:
            raise ValueError("classes")
        if validate and counts.min() < 5:
            raise ValueError("folds")
        if kind == "depre":
            y = pd.Series(np.searchsorted(classes, y), index=y.index)
    progress(25)
    estimator = {"hbp":lambda:RandomForestClassifier(n_estimators=100,random_state=42),
                 "depre":lambda:XGBClassifier(random_state=42),
                 "age":lambda:PCA(n_components=3,random_state=42)}[kind]()
    estimator.fit(x,y)
    progress(50)
    scores = []
    if validate and y is not None:
        _, counts = np.unique(y,return_counts=True)
        if len(counts)<2 or counts.min()<5:
            raise ValueError("folds")
        splits = StratifiedKFold(n_splits=5,shuffle=True,random_state=42)
        for index,(training,testing) in enumerate(splits.split(x,y),1):
            from sklearn.base import clone
            fold_model = clone(estimator)
            fold_model.fit(x.iloc[training],y.iloc[training])
            scores.append(float(fold_model.score(x.iloc[testing],y.iloc[testing]))*100)
            progress(50+index*8)
    payload = {"model":estimator,"scaler":trainer.scaler,"feature_names":x.columns.tolist()}
    if classes is not None:
        payload["classes"] = classes.tolist()
    relative = Path("data/models") / (uuid4().hex+".pkl")
    path = Path(settings.BASE_DIR)/relative
    path.parent.mkdir(parents=True,exist_ok=True)
    joblib.dump(payload,path)
    metadata = {"engine":"source","path":relative.as_posix(),"feature_names":x.columns.tolist(),"form_version":version}
    if y is not None: metadata["classes"]=classes.tolist()
    else: metadata["variance"]=estimator.explained_variance_ratio_.tolist()
    try:
        fit=Fit.objects.create(kind=kind,start=start,end=end,samples=len(cases),artifact=metadata,scores=scores)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    progress(95)
    return fit


@lru_cache(maxsize=8)
def load_model(relative):
    root=Path(settings.BASE_DIR).resolve()
    path=(root/relative).resolve()
    if root not in path.parents:
        raise ValueError("Invalid model path")
    return joblib.load(path)


def source_predictions(kind,fit,visits):
    payload=load_model(fit.artifact["path"])
    data=frame(kind,visits)
    names=payload.get("feature_names")
    if names is None:
        names=list(payload["model"].feature_names_in_)
    # Legacy models require numeric IDs; newly trained models exclude IDs.
    if "user_id" in names:
        data["user_id"] = pd.to_numeric(data["user_id"], errors="coerce").fillna(0)
    scaler=payload["scaler"]
    scale_names=list(scaler.feature_names_in_)
    data[scale_names]=scaler.transform(data[scale_names])
    data=data[names]
    if kind=="age": return payload["model"].transform(data)
    return payload["model"].predict_proba(data)
