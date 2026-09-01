"""FTAS 网页版（Streamlit）。

运行:
    cd FTAS
    .venv/bin/streamlit run web_app.py
"""
import matplotlib
matplotlib.use('Agg')  # 无界面渲染后端，必须在导入 pyplot 前设置

import matplotlib.pyplot as plt
import streamlit as st

from src.pipeline import analyze_match
from download_match import DEFAULT_TEAM, download_and_prepare
from list_matches import query_matches

st.set_page_config(page_title="FTAS 足球战术分析", layout="wide")
st.title("⚽ 足球战术分析系统")

EVENTS_PATH = "data/raw/statsbomb/events.json"
MATCHES_PATH = "data/raw/statsbomb/matches.json"

# ① 球队名称
team = st.text_input("① 球队名称", value=DEFAULT_TEAM)

# ② 赛事关键词（可选）
comp = st.text_input(
    "② 赛事关键词（可选，如 La Liga / Champions League，留空=全部）",
    value="",
)

# ③ 比赛选择
try:
    rows = query_matches(team, comp)
except (SystemExit, Exception) as e:
    st.error(f"查询比赛失败: {e}")
    st.stop()

if not rows:
    st.warning(
        f"未找到 {team} 的比赛"
        + (f"（关键词 '{comp}'）" if comp else "")
        + "，请检查球队名拼写（如 Real Madrid / Manchester United）"
    )
else:
    selected = st.selectbox(
        f"③ 选择比赛（共 {len(rows)} 场）",
        rows,
        format_func=lambda r: f"{r[0]} | {r[2]} | {r[4]}",
    )
    _, match_id, _, _, _ = selected

    if st.button("下载并分析", type="primary"):
        try:
            with st.spinner("正在下载比赛数据..."):
                download_and_prepare(int(match_id), team, update_config=False)
        except (SystemExit, Exception) as e:
            st.error(f"下载失败: {e}")
            st.stop()

        try:
            with st.spinner("正在分析..."):
                result = analyze_match(EVENTS_PATH, MATCHES_PATH, team)
        except (SystemExit, Exception) as e:
            st.error(f"分析失败: {e}")
            st.stop()

        st.subheader("传球网络")
        st.pyplot(result.pass_fig)
        plt.close(result.pass_fig)

        st.subheader("射门分布")
        st.pyplot(result.shot_fig)
        plt.close(result.shot_fig)

        st.subheader("活动热力图")
        st.pyplot(result.heat_fig)
        plt.close(result.heat_fig)

        st.subheader("文字报告")
        st.code(result.report_text, language="text")

        st.success("✅ 分析完成！")
