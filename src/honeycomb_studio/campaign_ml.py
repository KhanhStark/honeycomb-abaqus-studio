"""Leakage-resistant surrogate selection and bounded adaptive/Pareto sampling."""
from __future__ import annotations

import warnings
from functools import lru_cache

import numpy as np
from scipy.spatial.distance import cdist
from scipy.stats import qmc

from .adapters.reentrant import network
from .campaign import BOUNDS, OWNERS, SEED, geometry_valid, record
from .models import ModelSpec, digest

TARGETS = ("SEA_core_J_kg", "max_rear_downward_mm")


def development_records(manifest):
    return [r for r in manifest["designs"] if r["role"] in ("development", "adaptive")
            and r.get("archive_verified") and r.get("quality", {}).get("passed")
            and r.get("summary", {}).get("rear_skin_deleted") is False
            and r.get("summary", {}).get("event_finished") is True]


def features(rows):
    return np.array([[r["model"][name] for name in BOUNDS] for r in rows])


def fit_surrogates(manifest):
    from sklearn.base import clone
    from sklearn.compose import TransformedTargetRegressor
    from sklearn.ensemble import ExtraTreesRegressor
    from sklearn.gaussian_process import GaussianProcessRegressor
    from sklearn.gaussian_process.kernels import ConstantKernel, Matern
    from sklearn.linear_model import Ridge
    from sklearn.metrics import r2_score
    from sklearn.model_selection import GridSearchCV, KFold, cross_val_predict
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import PolynomialFeatures, StandardScaler

    rows = development_records(manifest)
    if len(rows) < 25:
        raise ValueError("At least 25 audited intact development designs required")
    x = features(rows)
    y = np.array([[r["summary"][t] for t in TARGETS] for r in rows])
    if not np.isfinite(y).all() or not np.isfinite(x).all():
        raise ValueError("Nonfinite training values")
    outer = KFold(5, shuffle=True, random_state=SEED)
    models = {
        "ridge": (make_pipeline(StandardScaler(), Ridge()), {"ridge__alpha": [.01, 1., 100.]}),
        "quadratic": (make_pipeline(StandardScaler(), PolynomialFeatures(2, include_bias=False), Ridge()),
                      {"ridge__alpha": [.01, 1., 100.]}),
        "gaussian_process": (make_pipeline(StandardScaler(), GaussianProcessRegressor(
            kernel=ConstantKernel(1., (.01, 100.)) * Matern(np.ones(4), nu=2.5),
            alpha=1.e-6, normalize_y=False, random_state=SEED)), {}),
        "extra_trees": (ExtraTreesRegressor(n_estimators=160, random_state=SEED, n_jobs=2),
                        {"min_samples_leaf": [1, 3, 5]}),
    }
    fitted, scores = {}, {}
    scale = np.percentile(y, 95, axis=0) - np.percentile(y, 5, axis=0)
    if np.any(scale <= 1.e-10):
        raise ValueError("Response spread too small for the agreed NRMSE gate")
    for name, (estimator, grid) in models.items():
        transformed = TransformedTargetRegressor(regressor=estimator, transformer=StandardScaler())
        candidates = GridSearchCV(transformed, {"regressor__" + k: v for k, v in grid.items()},
                                  cv=3, scoring="r2", n_jobs=1)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=Warning)
            predicted = cross_val_predict(candidates, x, y, cv=outer, n_jobs=1)
            candidates.fit(x, y)
        rmse = np.sqrt(np.mean((predicted - y) ** 2, axis=0))
        r2 = r2_score(y, predicted, multioutput="raw_values")
        scores[name] = {"r2": r2.tolist(), "rmse": rmse.tolist(), "nrmse": (rmse / scale).tolist()}
        fitted[name] = clone(candidates.best_estimator_).fit(x, y)
    winner = min(scores, key=lambda name: max(scores[name]["nrmse"]))
    gate = len(rows) >= 250 and min(scores[winner]["r2"]) >= .9 and max(scores[winner]["nrmse"]) <= .1
    return fitted, {"winner": winner, "models": scores, "training_count": len(rows), "passed": gate,
                    "training_ids": [r["id"] for r in rows], "test_labels_used": False,
                    "targets": TARGETS, "seed": SEED}


@lru_cache(maxsize=20000)
def core_mass(point):
    delta, foil, width, height = point
    indent = height / 2 * np.tan(np.deg2rad(delta))
    walls = network(100., 20., width, height, indent, 0., 0., .05)
    weighted_length = sum(np.hypot(b[0] - a[0], b[1] - a[1]) * (2 if double else 1)
                          for a, b, double in walls)
    return float(weighted_length * 100 * foil * 2700.e-9)


def candidate_pool(manifest, count=10000, *, exclude_known=True):
    low, high = np.array(list(BOUNDS.values())).T
    sampler = qmc.LatinHypercube(4, seed=SEED + 2)
    raw = qmc.scale(sampler.random(count * 2), low, high)
    known = {tuple(r["model"][k] for k in BOUNDS) for r in manifest["designs"]}
    return np.array([x for x in raw if (not exclude_known or tuple(x) not in known)
                     and geometry_valid(dict(zip(BOUNDS, x, strict=True)))][:count])


def new_designs(manifest, points, role):
    template = manifest["designs"][0]["model"]
    used = {r["physics_hash"] for r in manifest["designs"]}
    rows = []
    for vector in points:
        model = ModelSpec.model_validate({**template, **dict(zip(BOUNDS, map(float, vector), strict=True))})
        key = digest(model.resolved())
        if key in used:
            continue
        i = sum(r['role'] == role for r in manifest['designs']) + len(rows)
        rows.append(record(model, role, i + 1, OWNERS[i % 8], list(BOUNDS)))
        used.add(key)
    return rows


def adaptive_designs(manifest, fitted):
    from pymoo.util.nds.non_dominated_sorting import NonDominatedSorting

    previous = [r for r in manifest['designs'] if r['role'] == 'adaptive']
    if len(previous) + 20 > min(80, manifest.get('max_adaptive', 80)):
        raise ValueError("Adaptive budget exhausted")
    if any(r['status'] != 'completed' for r in previous):
        raise ValueError("Previous adaptive round is incomplete")
    pool = candidate_pool(manifest)
    predictions = np.stack([model.predict(pool) for model in fitted.values()])
    uncertainty = np.std(predictions, axis=0) / np.maximum(np.std(predictions.mean(axis=0), axis=0), 1.e-9)
    chosen = list(np.argsort(uncertainty.max(axis=1))[-10:])
    predicted = predictions.mean(axis=0)
    baseline = next(r for r in manifest['designs'] if r['role'] == 'development' and not r['varied_parameters'])
    feasible = np.array([core_mass(tuple(x)) <= baseline['summary']['core_mass_kg'] for x in pool])
    eligible = np.flatnonzero(feasible)
    front = [eligible[indices] for indices in NonDominatedSorting().do(
        np.column_stack((-predicted[eligible, 0], predicted[eligible, 1])))]
    for indices in front:
        for index in indices:
            if int(index) not in chosen:
                chosen.append(int(index))
                if len(chosen) == 16:
                    break
        if len(chosen) == 16:
            break
    if len(chosen) != 16:
        raise ValueError('Insufficient feasible candidates for the near-Pareto allocation')
    low, high = np.array(list(BOUNDS.values())).T
    normalized = (pool - low) / (high - low)
    train = (features(development_records(manifest)) - low) / (high - low)
    distance = cdist(normalized, train).min(axis=1)
    while len(chosen) < 20:
        distance[chosen] = -1
        index = int(np.argmax(distance))
        chosen.append(index)
        distance = np.minimum(distance, np.linalg.norm(normalized - normalized[index], axis=1))
    rows = new_designs(manifest, pool[chosen], "adaptive")
    for index, row in enumerate(rows):
        row['selection_reason'] = 'uncertainty' if index < 10 else 'near_pareto' if index < 16 else 'sparse_domain'
        row['adaptive_round'] = len(previous) // 20 + 1
    if len(rows) != 20:
        raise ValueError('Adaptive round did not produce twenty distinct configurations')
    return rows


def pareto_diagnostics(manifest, selected_model, previous=None):
    """Development-only front agreement on a deterministic feasible candidate pool."""
    from pymoo.util.nds.non_dominated_sorting import NonDominatedSorting

    pool = candidate_pool(manifest, count=2000, exclude_known=False)
    baseline = next(r for r in manifest['designs'] if r['role'] == 'development' and not r['varied_parameters'])
    pool = np.array([x for x in pool if core_mass(tuple(x)) <= baseline['summary']['core_mass_kg']])
    rows = development_records(manifest)
    y = np.array([[r['summary'][k] for k in TARGETS] for r in rows])
    scale = np.maximum(np.percentile(y, 95, axis=0) - np.percentile(y, 5, axis=0), 1.e-9)

    def distance(a, b):
        distances = cdist(np.asarray(a) / scale, np.asarray(b) / scale)
        return float(max(distances.min(axis=0).max(), distances.min(axis=1).max()))

    mean_prediction = selected_model.predict(pool)
    indices = NonDominatedSorting().do(np.column_stack((-mean_prediction[:, 0], mean_prediction[:, 1])),
                                       only_non_dominated_front=True)
    current = mean_prediction[indices]
    drift = distance(current, previous['front']) if previous else None
    return {'front': current.tolist(), 'criterion': 'selected-model front stability across development updates',
            'previous_front_distance': drift, 'normalization': 'development P95-P5',
            'tolerance': .05, 'test_labels_used': False,
            'passed': drift is not None and drift <= .05}


def rear_failure_model(manifest):
    from sklearn.ensemble import ExtraTreesClassifier

    rows = [r for r in manifest["designs"] if r["role"] in ("development", "adaptive")
            and r.get("archive_verified") and r.get("quality", {}).get("passed")
            and isinstance(r.get("summary", {}).get("rear_skin_deleted"), bool)]
    if len(rows) < 25:
        raise ValueError("Insufficient numerically audited rear-failure labels")
    y = np.array([not r["summary"]["rear_skin_deleted"] for r in rows], dtype=int)
    model = ExtraTreesClassifier(n_estimators=200, min_samples_leaf=3, random_state=SEED, n_jobs=2)
    model.fit(features(rows), y)
    return model, {"training_ids": [r["id"] for r in rows], "test_labels_used": False,
                   "failure_count": int(np.sum(y == 0)), "intact_count": int(np.sum(y == 1)),
                   "status": "no_failure_boundary_observed" if np.all(y) else "surrogate_unverified"}


def intact_probability(classifier, x):
    if 1 not in classifier.classes_:
        return np.zeros(len(x))
    return classifier.predict_proba(x)[:, list(classifier.classes_).index(1)]


def confirmation_selection(manifest, points, objectives):
    """Two extremes, six balanced trades and twelve points covering objective gaps."""
    known = {tuple(row['model'][k] for k in BOUNDS) for row in manifest['designs']}
    unique = []
    for index, point in enumerate(points):
        key = tuple(map(float, point))
        if key not in known:
            unique.append(index)
            known.add(key)
    if len(unique) < 20:
        raise ValueError('Fewer than twenty new Pareto configurations')
    points, objectives = np.asarray(points)[unique], np.asarray(objectives)[unique]
    normalized = (objectives - objectives.min(axis=0)) / np.maximum(np.ptp(objectives, axis=0), 1.e-12)
    chosen = [int(np.argmin(objectives[:, 0])), int(np.argmin(objectives[:, 1]))]
    if chosen[0] == chosen[1]:
        raise ValueError('Pareto candidates do not contain two distinct objective extremes')
    reasons = ['pareto_extreme_sea', 'pareto_extreme_rear']
    for index in np.argsort(normalized.max(axis=1)):
        if int(index) not in chosen:
            chosen.append(int(index))
            reasons.append('pareto_balance')
            if len(chosen) == 8:
                break
    distance = cdist(normalized, normalized[chosen]).min(axis=1)
    while len(chosen) < 20:
        distance[chosen] = -1
        index = int(np.argmax(distance))
        chosen.append(index)
        reasons.append('pareto_coverage')
        distance = np.minimum(distance, np.linalg.norm(normalized - normalized[index], axis=1))
    rows = new_designs(manifest, points[chosen], 'confirmation')
    if len(rows) != 20:
        raise ValueError('Pareto candidates duplicate existing configurations')
    for row, reason in zip(rows, reasons, strict=True):
        row['selection_reason'] = reason
    return rows


def confirmation_designs(manifest, surrogate, classifier):
    from pymoo.algorithms.moo.nsga2 import NSGA2
    from pymoo.core.problem import Problem
    from pymoo.optimize import minimize

    baseline = next(r for r in manifest["designs"] if r["role"] == "development" and not r["varied_parameters"])
    mass_limit = baseline["summary"]["core_mass_kg"]
    low, high = np.array(list(BOUNDS.values())).T

    class CoreProblem(Problem):
        def __init__(self):
            super().__init__(n_var=4, n_obj=2, n_ieq_constr=3, xl=low, xu=high)

        def _evaluate(self, x, out, *args, **kwargs):
            prediction = surrogate.predict(x)
            out["F"] = np.column_stack((-prediction[:, 0], prediction[:, 1]))
            throat = x[:, 2] - x[:, 3] * np.tan(np.deg2rad(x[:, 0]))
            geometry_constraint = np.maximum(8 * x[:, 1], .5) - throat
            masses = [core_mass(tuple(v)) if g < 0 else mass_limit * 10 for v, g in zip(x, geometry_constraint, strict=True)]
            out["G"] = np.column_stack((np.array(masses) - mass_limit, geometry_constraint,
                                        .95 - intact_probability(classifier, x)))

    result = minimize(CoreProblem(), NSGA2(pop_size=160), ("n_gen", 200), seed=SEED, verbose=False)
    if result.X is None or len(result.X) < 20:
        raise ValueError("Fewer than 20 feasible surrogate Pareto candidates")
    return confirmation_selection(manifest, result.X, result.F)


def evaluate_locked_test(manifest, surrogate, report):
    """Call only after model/selection are locked; never feed this report back into fitting."""
    from sklearn.metrics import r2_score

    if manifest.get("model_locked") is not True or not report.get("passed"):
        raise ValueError("Lock a development-qualified model before opening test labels")
    rows = [r for r in manifest["designs"] if r["role"] == "test"]
    if len(rows) != 80 or any(r["status"] != "completed" or not r.get("archive_verified") for r in rows):
        raise ValueError("All 80 held-out configurations must be archived before final evaluation")
    intact = [r for r in rows if r.get("quality", {}).get("passed")
              and r["summary"].get("rear_skin_deleted") is False and r["summary"].get("event_finished")]
    if len(intact) < 2:
        raise ValueError("Too few numerically accepted intact test configurations")
    y = np.array([[r["summary"][t] for t in TARGETS] for r in intact])
    predicted = surrogate.predict(features(intact))
    scale = np.percentile(y, 95, axis=0) - np.percentile(y, 5, axis=0)
    if np.any(scale <= 1.e-10):
        raise ValueError("Test response spread too small for NRMSE")
    rmse = np.sqrt(np.mean((y - predicted) ** 2, axis=0))
    r2 = r2_score(y, predicted, multioutput="raw_values")
    return {"targets": TARGETS, "r2": r2.tolist(), "nrmse": (rmse / scale).tolist(),
            "passed": bool(min(r2) >= .9 and max(rmse / scale) <= .1), "count": len(intact),
            "excluded_ids": [r["id"] for r in rows if r not in intact],
            "selection_locked": True, "test_used_for_model_selection": False}
