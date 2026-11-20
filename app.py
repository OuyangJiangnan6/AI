"""Streamlit demo: a transparent, multi-turn shopping assistant."""
from __future__ import annotations

import streamlit as st
from engine import ShoppingTask, recommend, update_task
from llm import configured, interpret

st.set_page_config(page_title="拾光 · 购物任务助手", page_icon="🛒", layout="wide")
st.markdown("""
<style>
.stApp {background: #f7f9fc; color: #17233b;}
.block-container {max-width: 1160px; padding-top: 2.0rem;}
h1,h2,h3 {color: #17233b;}
[data-testid="stSidebar"] {background: #eaf1f7;}
[data-testid="stChatMessage"] {
    border: 1px solid #d5e3e9;
    border-radius: 16px;
    background: #ffffff !important;
    width: min(86%, 820px);
    margin: 0 auto 0.8rem 0;
    box-shadow: 0 2px 8px rgba(23, 35, 59, 0.04);
}
[data-testid="stChatMessage"]:has([aria-label="Chat message from user"]) {
    background: #e5f0ff !important;
    border-color: #bfd8fa;
    width: fit-content;
    max-width: 76%;
    margin: 0 0 0.8rem auto;
    flex-direction: row-reverse;
}
[data-testid="stChatMessage"]:has([aria-label="Chat message from user"])
    [data-testid="stChatMessageContent"] {
    overflow-wrap: anywhere;
}
@media (max-width: 640px) {
    [data-testid="stChatMessage"] {width: 100%;}
    [data-testid="stChatMessage"]:has([aria-label="Chat message from user"]) {
        max-width: 92%;
    }
}
div[data-testid="stMetric"] {background: white; border: 1px solid #e3e9f1; border-radius: 12px; padding: 12px;}
.stButton > button {border-radius: 10px; border-color: #b9d2e6;}
</style>
""", unsafe_allow_html=True)

if "task" not in st.session_state:
    st.session_state.task = ShoppingTask()
if "turns" not in st.session_state:
    st.session_state.turns = []
if "latest" not in st.session_state:
    st.session_state.latest = None
if "model_note" not in st.session_state:
    st.session_state.model_note = ""

def submit(prompt: str) -> None:
    task = update_task(st.session_state.task, prompt)
    st.session_state.model_note = ""
    if st.session_state.get("use_model", False):
        try:
            task = interpret(st.session_state.task, prompt)
            st.session_state.model_note = "本轮使用模型理解需求；商品筛选与预算约束仍由本地规划器执行。"
        except Exception:
            st.session_state.model_note = "模型暂不可用，本轮已使用本地需求解析。"
    result = recommend(task)
    st.session_state.task = task
    st.session_state.turns.append({
        "prompt": prompt,
        "result": result,
        "preferences": list(task.preferences),
        "model_note": st.session_state.model_note,
    })
    st.session_state.latest = result

def badges(values: list[str], empty: str = "暂无") -> str:
    return " · ".join(values) if values else empty

def render_answer(result: dict, preferences: list[str], model_note: str = "") -> None:
    st.write(result["message"])
    if model_note:
        st.caption(model_note)
    if result["status"] != "ok":
        return

    best = result["bundles"][0]
    st.markdown(
        f"**首选方案：¥{best['total']}**　"
        f"预算结余 ¥{best['remaining']} · "
        f"满足偏好 {len(best['matched'])}/{len(preferences)}"
    )
    for item in best["items"]:
        with st.container(border=True):
            st.markdown(f"**{item['name']} · ¥{item['price']}**")
            st.write(item["summary"])
            st.caption(f"匹配特征：{badges(item['features'])}｜取舍：{item['tradeoff']}")
    if best["missing"]:
        st.caption(f"尚未满足：{badges(best['missing'])}")

    if len(result["bundles"]) > 1:
        with st.expander("查看其他方案"):
            for index, bundle in enumerate(result["bundles"][1:], 2):
                names = " + ".join(item["name"] for item in bundle["items"])
                st.markdown(
                    f"**方案 {index}：{names} · ¥{bundle['total']}**  "
                    f"结余 ¥{bundle['remaining']}；满足：{badges(bundle['matched'])}"
                )
                for item in bundle["items"]:
                    st.caption(f"{item['name']}：{item['tradeoff']}")
                if bundle["missing"]:
                    st.caption(f"未满足：{badges(bundle['missing'])}")
    with st.expander("为什么这样推荐？"):
        st.write("先按品类、排除条件和总预算筛选，再按偏好覆盖情况排序，并参考价格。")
        st.caption(
            f"找到 {result['candidate_count']} 组预算内方案；商品与价格均为虚构演示数据。"
        )

with st.sidebar:
    if configured():
        st.checkbox("启用模型理解", value=True, key="use_model")
    else:
        st.caption("模型理解未配置；当前使用本地需求解析。")
    st.markdown("### 🛒 当前购物任务")
    task = st.session_state.task
    st.metric("总预算", f"¥{task.budget}" if task.budget is not None else "待填写")
    st.markdown(f"**品类**  {badges(task.categories)}")
    st.markdown(f"**偏好**  {badges(task.preferences)}")
    st.markdown(f"**排除**  {badges(task.exclusions)}")
    st.caption(f"已沟通 {task.turns} 轮")
    if st.button("清空任务", use_container_width=True):
        st.session_state.task = ShoppingTask()
        st.session_state.turns = []
        st.session_state.latest = None
        st.session_state.model_note = ""
        st.rerun()
    st.divider()
    st.markdown("**演示说明**")
    st.caption("商品、价格和评价均为虚构样例；模型理解需单独配置，不接入真实电商平台。")

st.title("拾光 · 购物任务助手")
st.markdown("把购买需求说出来，我会整理约束、组合商品，并说明每个选择的取舍。")
st.info("赛题 02 · 搭建你理想中的购物助手｜可复现的交互原型", icon="✨")

st.markdown("#### 快速体验")
examples = [
    "预算 1500 元，想买通勤降噪耳机",
    "预算 1200 元，买耳机和键盘，适合图书馆学习",
    "预算 600 元，想要无线办公鼠标和键盘",
]
cols = st.columns(3)
selected = None
for col, example in zip(cols, examples):
    with col:
        if st.button(example, use_container_width=True):
            selected = example

st.markdown("#### 对话")
if not st.session_state.turns:
    st.caption("试试第一轮描述需求，下一轮继续说“不要入耳式”“预算改为 900 元”或“再加一个鼠标”。")
for turn in st.session_state.turns:
    if isinstance(turn, tuple):
        prompt, response = turn
        result = None
    else:
        prompt, result = turn["prompt"], turn["result"]
    with st.chat_message("user"):
        st.write(prompt)
    with st.chat_message("assistant"):
        if result is None:
            st.write(response)
        else:
            render_answer(result, turn["preferences"], turn["model_note"])

typed = st.chat_input("例如：预算 1500 元，买通勤降噪耳机；不要入耳式")
if typed or selected:
    submit(typed or selected)
    st.rerun()
