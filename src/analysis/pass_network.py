import pandas as pd


def build_pass_network(passes, team_name):
    """
    构建传球网络所需的数据
    """
    team_passes = passes[passes['team.name'] == team_name]

    # 球员平均站位
    avg_pos = (
        team_passes
        .groupby('player.name')
        .agg(
            x=('x', 'mean'),
            y=('y', 'mean'),
            pass_count=('id', 'count')
        )
        .reset_index()
    )

    # 传球关系
    edges = (
        team_passes
        .groupby(['player.name', 'pass.recipient.name'])
        .size()
        .reset_index(name='count')
    )

    return avg_pos, edges