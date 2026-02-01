import streamlit as st
import google.generativeai as genai
import random
import time

# --- 設定・API準備 ---
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("APIキーがSecretsに設定されていません。")

# 診断結果に基づいた正確なモデル名
CHOSEN_MODEL = 'models/gemini-flash-latest'

# API呼び出し関数（リトライ機能付き）
def call_gemini_with_retry(model, prompt, max_retries=3):
    for i in range(max_retries):
        try:
            return model.generate_content(prompt)
        except Exception as e:
            if "429" in str(e) and i < max_retries - 1:
                time.sleep(2 * (i + 1))
                continue
            raise e

# デザイン設定
st.markdown("""
    <style>
    .main { background-color: #001220; color: #E5E5E5; }
    .stButton>button { width: 100%; border-radius: 5px; font-weight: bold; }
    div.stButton > button:first-child { background: linear-gradient(135deg, #E5E5E5 0%, #A0A0A0 100%); color: #001220; }
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
        st.session_state.kw = random.choice(["孫", "AI", "無人島", "コンビニ", "タイムマシン", "入れ歯", "メルカリ", "給食"])
        st.rerun()

if st.button("お題をAI生成", use_container_width=True):
    with st.spinner("AIが思考中..."):
        try:
            model = genai.GenerativeModel(model_name=CHOSEN_MODEL)
            prompt = f"「{st.session_state.kw}」でIPPONグランプリ風の大喜利お題を3つ、記号なし改行区切りで出力してください。"
            res = call_gemini_with_retry(model, prompt)
            if res and hasattr(res, 'text'):
                st.session_state.odais = [l.strip() for l in res.text.replace('*','').replace('-','').split('\n') if l.strip()]
                st.rerun()
        except Exception as e:
            st.error(f"エラーが発生しました: {e}")

# --- 2. お題選択 ---
if st.session_state.odais:
    st.write("---")
    st.write("### お題を選択してください")
    for i, odai in enumerate(st.session_state.odais):
        if st.button(odai, key=f"odai_{i}"):
            st.session_state.selected_odai = odai
            st.session_state.ans_list = [] # お題変更で回答リセット
            st.rerun()

# --- 3. 回答生成 ---
if st.session_state.selected_odai:
    st.write("---")
    st.success(f"【選択中】{st.session_state.selected_odai}")
    tone = st.selectbox("ユーモアの種類", ["通常", "知的", "シュール", "ブラック"])
    
    if st.button("回答を20案表示", type="primary"):
        with st.spinner("20案を爆速生成中..."):
            try:
                model = genai.GenerativeModel(model_name=CHOSEN_MODEL)
                prompt = f"お題：{st.session_state.selected_odai}\n雰囲気：{tone}\n爆笑を生む回答を20案、番号や記号なしで改行区切りで出力してください。"
                res = call_gemini_with_retry(model, prompt)
                if res and hasattr(res, 'text'):
                    st.session_state.ans_list = [l.strip() for l in res.text.replace('*','').replace('-','').split('\n') if l.strip()]
                    st.rerun()
            except Exception as e:
                st.error(f"回答生成エラー: {e}")

# --- 4. 結果表示 ---
if st.session_state.ans_list:
    st.write("### 回答一覧（YouTubeショート用）")
    sel = []
    for i, ans in enumerate(st.session_state.ans_list[:20]):
        if st.checkbox(ans, key=f"a_{i}"):
            sel.append(ans)
    
    if sel:
        st.write("---")
        st.write("### 選択した回答をコピー")
        st.text_area("コピー用", value="\n".join(sel), height=150)
