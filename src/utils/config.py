"""全局路径配置：全部由环境变量决定，并带本地 CLI 默认值。

不设置环境变量时，行为与旧版本地 CLI 完全一致。
"""
import os

# 旧版单场数据路径（保留给 main.py 无参数时的 match_id 推断入口）
DATA_PATH = os.environ.get('FTAS_DATA_PATH', 'data/raw/statsbomb/events.json')
MATCHES_PATH = os.environ.get('FTAS_MATCHES_PATH', 'data/raw/statsbomb/matches.json')

# 输出目录
FIGURES_DIR = os.environ.get('FTAS_FIGURES_DIR', 'outputs/figures')
REPORTS_DIR = os.environ.get('FTAS_REPORTS_DIR', 'outputs/reports')

# 输出文件路径
PASS_NETWORK_PATH = os.environ.get('FTAS_PASS_NETWORK_PATH', f'{FIGURES_DIR}/pass_network.png')
SHOT_MAP_PATH = os.environ.get('FTAS_SHOT_MAP_PATH', f'{FIGURES_DIR}/shot_map.png')
HEATMAP_PATH = os.environ.get('FTAS_HEATMAP_PATH', f'{FIGURES_DIR}/heatmap.png')
REPORT_PATH = os.environ.get('FTAS_REPORT_PATH', f'{REPORTS_DIR}/match_analysis.txt')
