from functools import lru_cache

import numpy as np

from .catalog import FIELDS
from .models import Fit, Record


REQUIRED = {"hbp": ("baseline", "hbp"), "depre": ("baseline", "psqi", "depre"),
            "age": ("baseline", "hbp", "depre", "psqi")}


def observations(start, end):
    groups = {}
    for subject, day, kind, values, version in Record.objects.filter(day__range=(start, end)).order_by().values_list(
            "subject", "day", "kind", "values", "form_version").iterator():
        group = groups.setdefault((subject, day), {})
        group[kind] = values
        if kind == "psqi":
            group["_sleep_version"] = version
    return groups


def features(kind, group):
    tables = {"hbp": ("baseline",), "depre": ("baseline","psqi"), "age": REQUIRED["age"]}[kind]
    return [float(group[t][f.key]) for t in tables for f in FIELDS[t]]


def label(kind, group):
    if kind == "hbp":
        bp = group["hbp"]
        return int(bp["systolic_bp"] >= 140 or bp["diastolic_bp"] >= 90)
    score = sum(group["depre"].values())
    return int(score >= 5) + int(score >= 10)


def estimate(kind, x, y, method="light"):
    center, spread = x.mean(axis=0), x.std(axis=0)
    spread[spread < 1e-8] = 1
    z = (x-center)/spread
    model = {"center": center.tolist(), "spread": spread.tolist()}
    if kind == "age":
        _, singular, axes = np.linalg.svd(z, full_matrices=False)
        energy = singular ** 2
        model.update(axes=axes[:3].tolist(), variance=(energy[:3]/max(float(energy.sum()),1e-10)).tolist())
    elif method == "original" and kind == "hbp":
        from sklearn.ensemble import RandomForestClassifier
        if len(np.unique(y)) < 2:
            raise ValueError("classes")
        forest = RandomForestClassifier(n_estimators=100, max_depth=8, random_state=42).fit(z, y)
        trees = []
        for estimator in forest.estimators_:
            tree = estimator.tree_
            weights = tree.value[:,0,:]
            trees.append(dict(left=tree.children_left.tolist(),right=tree.children_right.tolist(),
                              feature=tree.feature.tolist(),threshold=tree.threshold.tolist(),
                              probs=(weights/weights.sum(axis=1,keepdims=True)).tolist()))
        model.update(trees=trees, classes=forest.classes_.tolist())
    elif method == "original":
        from xgboost import XGBClassifier
        classes, indices = np.unique(y,return_inverse=True)
        if len(classes) < 2:
            raise ValueError("classes")
        estimator = XGBClassifier(n_estimators=80,max_depth=4,random_state=42,n_jobs=2).fit(z,indices)
        encoded = estimator.get_booster().save_raw(raw_format="json").decode()
        model.update(booster=encoded,classes=classes.tolist())
    else:
        classes, counts = np.unique(y, return_counts=True)
        if len(classes) < 2:
            raise ValueError("classes")
        model.update(classes=classes.tolist(), mean=[z[y==c].mean(axis=0).tolist() for c in classes],
                     var=[np.maximum(z[y==c].var(axis=0),0.01).tolist() for c in classes],
                     prior=(counts/len(y)).tolist())
    return model


@lru_cache(maxsize=2)
def load_booster(encoded):
    from xgboost import Booster
    booster = Booster()
    booster.load_model(bytearray(encoded.encode()))
    return booster


def predict(model, x):
    z = (np.atleast_2d(x)-model["center"])/model["spread"]
    if "axes" in model:
        return z @ np.array(model["axes"]).T
    if "trees" in model:
        total = np.zeros((len(z),len(model["classes"])))
        for tree in model["trees"]:
            left,right,feature,threshold = [np.asarray(tree[k]) for k in ("left","right","feature","threshold")]
            nodes = np.zeros(len(z),dtype=int)
            while True:
                active = np.flatnonzero(left[nodes] >= 0)
                if not len(active):
                    break
                parent = nodes[active]
                nodes[active] = np.where(z[active,feature[parent]] <= threshold[parent],left[parent],right[parent])
            total += np.asarray(tree["probs"])[nodes]
        return total/len(model["trees"])
    if "booster" in model:
        p = load_booster(model["booster"]).inplace_predict(z)
        return np.column_stack((1-p,p)) if p.ndim==1 else p
    diff = z[:, None, :] - model["mean"]
    logp = np.log(model["prior"]) - .5 * (np.log(model["var"]) + diff**2/model["var"]).sum(axis=2)
    p = np.exp(logp-logp.max(axis=1,keepdims=True))
    return p/p.sum(axis=1,keepdims=True)


def train(kind, start, end, validate, method="light", progress=lambda value: None):
    progress(5)
    groups = observations(start, end)
    cases = [(subject, g) for (subject, day), g in groups.items() if all(t in g for t in REQUIRED[kind])]
    if len(cases) < 3:
        raise ValueError("samples")
    progress(20)
    versions = {g.get("_sleep_version","legacy") for _,g in cases}
    if kind != "hbp" and len(versions)>1:
        raise ValueError("versions")
    from .original_models import train_original
    return train_original(kind,cases,start,end,validate,progress,next(iter(versions)))


def assessments(kind, dates, fit):
    latest = {}
    for (subject, day), group in dates.items():
        if fit and fit.artifact.get("engine")=="source" and not all(t in group for t in REQUIRED[kind]):
            continue
        if fit and kind=="depre" and group.get("_sleep_version","legacy") != fit.artifact.get("form_version","legacy"):
            continue
        try:
            values = group if fit and fit.artifact.get("engine")=="source" else features(kind,group) if fit else group[kind]
        except KeyError:
            continue
        if subject not in latest or latest[subject][0] < day:
            latest[subject] = (day,values)
    results = {}
    if not latest:
        return results
    if fit:
        if fit.artifact.get("engine")=="source":
            from .original_models import source_predictions
            complete = {subject:item for subject,item in latest.items() if all(t in item[1] for t in REQUIRED[kind])}
            latest = complete
            if not latest: return {}
            probabilities = source_predictions(kind,fit,[(s,v) for s,(_,v) in latest.items()])
        else:
            probabilities = predict(fit.artifact,[values for _,values in latest.values()])
        classes = fit.artifact["classes"]
        for (subject,(day,_)),p in zip(latest.items(),probabilities):
            if kind == "hbp":
                risk = float(p[classes.index(1)])
                results[subject]=(day,int(risk >= .3) + int(risk > .7),f"{risk:.1%}",risk)
            else:
                results[subject]=(day,classes[int(p.argmax())],None,None)
    else:
        for subject,(day,values) in latest.items():
            band = label(kind,{kind:values})
            if kind == "hbp":
                text = f"{values['systolic_bp']:.0f}/{values['diastolic_bp']:.0f} mmHg"
                results[subject]=(day,2*band,text,None)
            else:
                results[subject]=(day,band,str(sum(values.values())),None)
    return results


def active_fit(kind):
    from .models import SiteOptions
    options, _ = SiteOptions.objects.get_or_create(pk=1)
    selected = options.selected_models.get(kind, "latest")
    if selected == "none":
        return None
    query = Fit.objects.filter(kind=kind)
    candidates = query if selected=="latest" else query.filter(pk=selected)
    return next((fit for fit in candidates if fit.available),None)
