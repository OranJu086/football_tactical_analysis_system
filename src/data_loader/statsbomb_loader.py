import json
import pandas as pd


def load_events(json_path):
    """
    读取 StatsBomb 的 events.json
    返回 pandas DataFrame
    """
    with open(json_path, 'r', encoding='utf-8') as f:
        events = json.load(f)

    df = pd.json_normalize(events)
    return df
