import matplotlib
matplotlib.use('Agg')  # 无界面渲染后端，保证 headless/服务器环境也能运行

import matplotlib.pyplot as plt
import os

from src.pipeline import analyze_match
from src.utils.config import (
    DATA_PATH, MATCHES_PATH, TEAM_NAME,
    FIGURES_DIR, REPORTS_DIR,
    PASS_NETWORK_PATH, SHOT_MAP_PATH, HEATMAP_PATH, REPORT_PATH,
)


def main():
    print("加载并分析数据...")
    result = analyze_match(DATA_PATH, MATCHES_PATH, TEAM_NAME)

    os.makedirs(FIGURES_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)

    result.pass_fig.savefig(PASS_NETWORK_PATH, dpi=300)
    plt.close(result.pass_fig)
    print(f"  [ok] {PASS_NETWORK_PATH}")

    result.shot_fig.savefig(SHOT_MAP_PATH, dpi=300)
    plt.close(result.shot_fig)
    print(f"  [ok] {SHOT_MAP_PATH}")

    result.heat_fig.savefig(HEATMAP_PATH, dpi=300)
    plt.close(result.heat_fig)
    print(f"  [ok] {HEATMAP_PATH}")

    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write(result.report_text)
    print(f"[report] 已生成: {REPORT_PATH}")

    print("\n全部完成！")


if __name__ == '__main__':
    main()
