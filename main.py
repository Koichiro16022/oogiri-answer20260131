import streamlit as st
import google.generativeai as genai
import random
import time

# --- 設定・API準備 ---
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("APIキーがSecretsに設定されていません。")

# 有料枠（Tier 1）なので、最新鋭の 2.0 Flash を使用
CHOSEN_MODEL = 'models/gemini-2.0-flash'

# デザイン設定（閃カラー：黄色、プラチナ、シルバー）
st.markdown("""
    <style>
    .main { background-color: #001220; color: #E5E5E5; }
    .stButton>button { width: 100%; border-radius: 5px; font-weight: bold; }
    div.stButton > button:first-child {
        background: linear-gradient(135deg, #FFD700 0%, #E5E5E5 100%);
        color: #001220;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("大喜利アンサー")

# --- 状態管理 ---
if 'kw' not in st.session_state: st.session_state.kw = "孫"
if 'odais' not in st.session_state: st.session_state.odais = []
if 'selected_odai' not in st.session_state: st.session_state.selected_odai = ""
if 'ans_list' not in st.session_state: st.session_state.ans_list = []

# --- 1. キーワード入力 ---
st.subheader("キーワードを入力してください")
col1, col2, col3 = st.columns([5, 1.5, 1.5])
with col1:
    st.session_state.kw = st.text_input("キーワード", value=st.session_state.kw, label_visibility="collapsed")
with col2:
    if st.button("消去"):
        st.session_state.kw = ""
        st.rerun()
with col3:
    if st.button("ランダム"):
        st.session_state.kw = random.choice(["無人島", "タイムマシン", "入れ歯", "給食", "宇宙飛行士", "コンビニ"])
        st.rerun()

if st.button("お題をAI生成", use_container_width=True):
    with st.spinner("AIが爆速で思考中..."):
        try:
            model = genai.GenerativeModel(CHOSEN_MODEL)
            prompt = f"「{st.session_state.kw}」でIPPONグランプリ風の大喜利お題を3つ、改行区切りで出力してください。"
            res = model.generate_content(prompt)
            st.session_state.odais = [l.strip() for l in res.text.replace('*','').replace('-','').split('\n') if l.strip()]
            st.rerun()
        except Exception as e:
            st.error(f"エラー: {e}")

# --- 2. お題選択 ---
if st.session_state.odais:
    st.write("---")
    st.write("### お題を選択してください")
    for i, odai in enumerate(st.session_state.odais):
        if st.button(odai, key=f"odai_{i}"):
            st.session_state.selected_odai = odai
            st.session_state.ans_list = []
            st.rerun()

# --- 3. 回答生成 ---
if st.session_state.selected_odai:
    st.write("---")
    st.success(f"【選択中】{st.session_state.selected_odai}")
    tone = st.selectbox("ユーモアの種類", ["通常", "知的", "シュール", "ブラック"])
    
    if st.button("回答を20案表示", type="primary"):
        with st.spinner("20案を同時生成中..."):
            try:
                model = genai.GenerativeModel(CHOSEN_MODEL)
                prompt = f"お題：{st.session_state.selected_odai}\n雰囲気：{tone}\n爆笑回答を20案、番号なし改行区切りで出力。"
                res = model.generate_content(prompt)
                st.session_state.ans_list = [l.strip() for l in res.text.replace('*','').replace('-','').split('\n') if l.strip()]
                st.rerun()
            except Exception as e:
                st.error(f"回答生成エラー: {e}")

# --- 4. 結果表示 ---
if st.session_state.ans_list:
    st.write("### 回答一覧（YouTubeショート用）")
    sel = [ans for i, ans in enumerate(st.session_state.ans_list[:20]) if st.checkbox(ans, key=f"a_{i}")]
    if sel:
        st.write("---")
        st.write("### 選択した回答をコピー")
        st.text_area("コピー用", value="\n".join(sel), height=150)
        st.caption("「私が100%制御しています」")
