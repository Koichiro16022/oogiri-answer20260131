import streamlit as st
import google.generativeai as genai
import random

# --- 設定・API準備 ---
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("APIキーがSecretsに設定されていません。")

# デザイン設定（CSS）
st.markdown("""
    <style>
    .main { background-color: #001220; color: #E5E5E5; }
    .stButton>button { width: 100%; border-radius: 5px; font-weight: bold; }
    div.stButton > button:first-child {
        background: linear-gradient(135deg, #E5E5E5 0%, #A0A0A0 100%);
        color: #001220;
    }
    </style>
    """, unsafe_allow_html=True)

# ① タイトルを「大喜利アンサー」のみに修正
st.title("大喜利アンサー")

# --- 状態管理 ---
if 'random_word' not in st.session_state:
    st.session_state.random_word = "孫"
if 'odai_list' not in st.session_state:
    st.session_state.odai_list = []
if 'selected_odai' not in st.session_state:
    st.session_state.selected_odai = ""
if 'answers' not in st.session_state:
    st.session_state.answers = []

# --- 1. キーワードセクション ---
st.subheader("キーワードを入力してください")
col1, col2, col3 = st.columns([5, 1.5, 1.5]) # 比率を少し調整
with col1:
    kw = st.text_input("キーワード", value=st.session_state.random_word, label_visibility="collapsed")
with col2:
    if st.button("消去"):
        st.session_state.random_word = ""
        st.rerun()
with col3:
    # ② ボタンの表示を「ランダム」に修正
    if st.button("ランダム"):
        words = ["孫", "AI", "無人島", "コンビニ", "タイムマシン", "入れ歯", "メルカリ", "宇宙飛行士", "給食", "透明人間"]
        st.session_state.random_word = random.choice(words)
        st.rerun()

if st.button("お題をAI生成", use_container_width=True):
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"「{kw}」をキーワードにして、大喜利のお題を3つ、箇条書きの記号なしで、改行のみで出力してください。IPPONグランプリのようなテイストでお願いします。"
        response = model.generate_content(prompt)
        lines = response.text.replace('*', '').replace('-', '').strip().split('\n')
        st.session_state.odai_list = [l.strip() for l in lines if l.strip()]
        st.rerun()
    except Exception as e:
        st.error(f"お題生成エラー: {e}")

# --- お題選択エリア ---
if st.session_state.odai_list:
    st.write("---")
    st.write("### お題を選択してください")
    for odai in st.session_state.odai_list:
        if st.button(odai, key=f"btn_{odai}"):
            st.session_state.selected_odai = odai

# --- 2. 直接入力 ---
st.write("---")
st.write("または直接入力")
manual_odai = st.text_input("お題を直接入力", label_visibility="collapsed")
if st.button("手動入力を確定"):
    if manual_odai:
        st.session_state.selected_odai = manual_odai

# --- 3. 回答生成 ---
if st.session_state.selected_odai:
    st.write("---")
    st.info(f"お題：{st.session_state.selected_odai}")
    tone = st.selectbox("ユーモアの種類", ["通常", "知的", "シュール", "ブラック"])
    
    if st.button("回答を20案表示", type="primary"):
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = f"お題：{st.session_state.selected_odai}\n雰囲気：{tone}\nこのお題に対して、爆笑を生む回答を20案、番号や記号なしで、改行のみで出力してください。"
            response = model.generate_content(prompt)
            lines = response.text.replace('*', '').replace('-', '').strip().split('\n')
            st.session_state.answers = [l.strip() for l in lines if l.strip()]
            st.rerun()
        except Exception as e:
            st.error(f"回答生成エラー: {e}")

# --- 4. 結果表示 ---
if st.session_state.answers:
    st.write("### 回答一覧（YouTubeショート用）")
    selected = []
    # 常に20案表示するようにスライスを調整
    for i, ans in enumerate(st.session_state.answers[:20]):
        if st.checkbox(ans, key=f"ans_{i}"):
            selected.append(ans)
    
    if selected:
        st.write("---")
        st.write("### 選択した回答をコピー")
        st.text_area("コピー用", value="\n".join(selected), height=150)
