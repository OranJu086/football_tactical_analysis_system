from src.data_loader.statsbomb_loader import load_events
from src.preprocessing.event_cleaner import clean_pass_events
from src.analysis.pass_network import build_pass_network
from src.analysis.shot_map import extract_shots
from src.analysis.heatmap import extract_positions
from src.visualization.pitch import create_pitch
from src.visualization.plot_utils import draw_pass_network
from src.visualization.shot_plot import draw_shot_map
from src.visualization.heatmap_plot import draw_heatmap
from src.utils.config import DATA_PATH, TEAM_NAME

import matplotlib.pyplot as plt
import os


def main():
    df = load_events(DATA_PATH)

    os.makedirs('outputs/figures', exist_ok=True)

    # ========== 1. 传球网络 ==========
    passes = clean_pass_events(df)
    avg_pos, edges = build_pass_network(passes, TEAM_NAME)

    pitch, fig, ax = create_pitch()
    draw_pass_network(pitch, ax, avg_pos, edges)
    plt.savefig('outputs/figures/pass_network.png', dpi=300)
    plt.close()

    # ========== 2. 射门分布 ==========
    shots = extract_shots(df, TEAM_NAME)
    pitch, fig, ax = create_pitch()
    draw_shot_map(pitch, ax, shots)
    plt.savefig('outputs/figures/shot_map.png', dpi=300)
    plt.close()

    # ========== 3. 活动热力图 ==========
    events = extract_positions(df, TEAM_NAME)
    pitch, fig, ax = create_pitch()
    draw_heatmap(pitch, ax, events)
    plt.savefig('outputs/figures/heatmap.png', dpi=300)
    plt.close()


if __name__ == '__main__':
    main()
