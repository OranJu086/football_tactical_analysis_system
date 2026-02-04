def extract_positions(df, team_name):
    """
    提取球队所有事件的坐标
    """
    events = df[df['team.name'] == team_name].copy()

    events['x'] = events['location'].apply(
        lambda x: x[0] if isinstance(x, list) else None
    )
    events['y'] = events['location'].apply(
        lambda x: x[1] if isinstance(x, list) else None
    )

    events = events.dropna(subset=['x', 'y'])

    return events