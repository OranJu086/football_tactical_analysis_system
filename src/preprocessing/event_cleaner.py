import pandas as pd


def clean_pass_events(df):
    """
    提取并清洗传球事件
    """
    passes = df[df['type.name'] == 'Pass'].copy()

    # 起点坐标
    passes['x'] = passes['location'].apply(lambda x: x[0])
    passes['y'] = passes['location'].apply(lambda x: x[1])

    # 终点坐标（判断传球是否有落点）
    passes['end_x'] = passes['pass.end_location'].apply(
        lambda x: x[0] if isinstance(x, list) else None
    )
    passes['end_y'] = passes['pass.end_location'].apply(
        lambda x: x[1] if isinstance(x, list) else None
    )

    passes = passes.dropna(subset=['end_x', 'end_y'])

    return passes
