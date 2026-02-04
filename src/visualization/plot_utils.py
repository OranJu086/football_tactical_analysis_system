def draw_pass_network(pitch, ax, avg_pos, edges):
    # 画球员点
    pitch.scatter(
        avg_pos['x'],
        avg_pos['y'],
        s=avg_pos['pass_count'] * 10,
        ax=ax,
        color='red',
        zorder=3
    )

    # 球员名字
    for _, row in avg_pos.iterrows():
        ax.text(row['x'], row['y'], row['player.name'],
                ha='center', va='center', fontsize=8)

    # 画传球线
    for _, row in edges.iterrows():
        p1 = avg_pos[avg_pos['player.name'] == row['player.name']]
        p2 = avg_pos[avg_pos['player.name'] == row['pass.recipient.name']]

        if p1.empty or p2.empty:
            continue

        pitch.lines(
            p1['x'], p1['y'],
            p2['x'], p2['y'],
            lw=row['count'] / 2,
            ax=ax,
            color='blue',
            alpha=0.6,
            zorder=2
        )