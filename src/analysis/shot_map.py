def extract_shots(df, team_name):
    """
    提取某球队的射门事件
    """
    shots = df[
        (df['type.name'] == 'Shot') &
        (df['team.name'] == team_name)
    ].copy()

    shots['x'] = shots['location'].apply(lambda x: x[0])
    shots['y'] = shots['location'].apply(lambda x: x[1])

    shots['is_goal'] = shots['shot.outcome.name'] == 'Goal'

    return shots