def draw_shot_map(pitch, ax, shots):
    # 非进球
    pitch.scatter(
        shots[~shots['is_goal']]['x'],
        shots[~shots['is_goal']]['y'],
        ax=ax,
        s=60,
        color='blue',
        alpha=0.6,
        label='Shot'
    )

    # 进球
    pitch.scatter(
        shots[shots['is_goal']]['x'],
        shots[shots['is_goal']]['y'],
        ax=ax,
        s=100,
        color='red',
        edgecolors='black',
        label='Goal'
    )

    ax.legend()