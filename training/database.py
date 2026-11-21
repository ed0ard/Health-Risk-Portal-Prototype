from pathlib import Path

import pandas as pd


DATA_DIR = Path(__file__).resolve().parent.parent / 'data' / 'source'


def _load_visits(required_tables, date_range):
    """Join complete same-day visits, never different visits of one user."""
    if not required_tables:
        return None
    start, end = (pd.Timestamp(value).normalize() for value in date_range)
    if start > end:
        raise ValueError('Start date must not exceed end date')
    merged = None
    for table in required_tables:
        data = pd.read_excel(DATA_DIR / f'{table}.xlsx', dtype={'user_id': str})
        if not {'user_id', 'time'}.issubset(data.columns):
            raise ValueError(f'{table} requires user_id and time columns')
        data['time'] = pd.to_datetime(data['time']).dt.normalize()
        data = data.loc[data['time'].between(start, end)].dropna(subset=['user_id', 'time'])
        if data.empty:
            return None
        merged = data if merged is None else merged.merge(
            data, on=['user_id', 'time'], how='inner', validate='one_to_one')
    return None if merged.empty else merged


def load_model_trainer_data(required_tables, date_range):
    data = _load_visits(required_tables, date_range)
    if data is None or len(data) < 10:
        return None
    return data


def load_model_test_data(required_tables, date_range, user_id):
    data = _load_visits(required_tables, date_range)
    if data is None:
        return None
    return {'combined': data.loc[data['user_id'] == str(user_id)].copy()}
