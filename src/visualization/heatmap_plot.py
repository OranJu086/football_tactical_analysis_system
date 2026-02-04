def draw_heatmap(pitch, ax, events):
    pitch.kdeplot(
        events['x'],
        events['y'],
        ax=ax,
        fill=True,
        levels=100,
        cmap='Reds'
    )