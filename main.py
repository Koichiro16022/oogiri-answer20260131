import streamlit as st
import google.generativeai as genai
import random

# --- 設定・API準備 ---
# StreamlitのSecretsからAPIキーを取得
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("APIキーがSecretsに設定されていません。")

# デザイン設定（CSS）
st.markdown("""
    <style>
    .main { background-color: #001220; color: #E5E5E5; }
    .stButton>button { width: 100%; border-radius: 5px; font-weight: bold; }
    /* プライマリボタン（銀色グラデーション風） */
    div.stButton > button:first-child {
        background: linear-gradient(135deg, #E5E5E5 0%, #A0A0A0 100%);
        color: #001220;
    }
    .item-box {
        background: rgba(255,255,255,0.05);
        padding: 15px;
        margin: 8px 0;
        border-radius: 5px;
        border: 2px solid transparent;
        cursor: pointer;
    }
    .selected-red {
        border: 2px solid #FF0000 !important;
        background: rgba(255, 0, 0, 0.1) !important;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("大喜利アンサー - Prototype (閃)")

# --- 状態管理 (Session State) ---
if 'random_word' not in st.session_state:
    st.session_state.random_word = "孫"
if 'odai_list' not in st.session_state:
    st.session_state.odai_list = []
if 'selected_odai' not in st.session_state:
    st.session_state.selected_odai = ""
if 'answers' not in st.session_state:
    st.session_state.answers = []
if 'selected_answers' not in st.session_state:
    st.session_state.selected_answers = []

# --- 関数 ---
def get_random_word():
    words = ["孫", "AI", "無人島", "コンビニ", "タイムマシン", "入れ歯", "メルカリ", "宇宙飛行士", "給食", "透明人間"]
    st.session_state.random_word = random.choice(words)

# --- 1. キーワードセクション ---
st.subheader("キーワードを入力してください")
col1, col2, col3 = st.columns([6, 1, 1])
with col1:
    kw = st.text_input("キーワード", value=st.session_state.random_word, label_visibility="collapsed", key="kw_input")
with col2:
    if st.button("消去", key="clear_kw"):
        st.session_state.random_word = ""
        st.rerun()
with col3:
    if st.button("🎲", key="random_btn"):
        get_random_word()
        st.rerun()

if st.button("お題をAI生成", use_container_width=True):
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"{kw}をキーワードにして、IPPONグランプリのような大喜利のお題を3つ、改行区切りで提案してください。余計な説明は不要です。"
    response = model.generate_content(prompt)
    st.session_state.odai_list = response.text.strip().split('\n')

# --- お題選択エリア ---
if st.session_state.odai_list:
    st.write("---")
    st.write("### お題を選択してください")
    for odai in st.session_state.odai_list:
        if st.button(odai, key=f"btn_{odai}"):
            st.session_state.selected_odai = odai

# --- 2. 手動入力セクション ---
st.write("---")
st.write("または直接入力")
manual_odai = st.text_input("お題を直接入力", placeholder="例：孫におじいちゃんがブチギレ。何があった？")
if st.button("確定", key="confirm_manual"):
    if manual_odai:
        st.session_state.selected_odai = manual_odai

# --- 3. 回答設定セクション ---
if st.session_state.selected_odai:
    st.write("---")
    st.info(f"選択中のお題：{st.session_state.selected_odai}")
    
    tone = st.selectbox("ユーモアの種類", ["通常", "知的", "シュール", "ブラック"])
    
    if st.button("回答を20案表示", type="primary"):
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"お題：{st.session_state.selected_odai}\nこのお題に対して、{tone}な雰囲気の回答を常に20案出してください。番号付きリストのみで出力してください。"
        response = model.generate_content(prompt)
        st.session_state.answers = response.text.strip().split('\n')

# --- 4. 回答表示・コピーセクション ---
if st.session_state.answers:
    st.write("### 回答一覧（クリックして選択）")
    # Streamlitのmultiselect等で代用するのが一般的ですが、見た目重視でcheckboxを並べます
    new_selections = []
    for i, ans in enumerate(st.session_state.answers):
        if st.checkbox(ans, key=f"ans_{i}"):
            new_selections.append(ans)
    
    st.session_state.selected_answers = new_selections

    if st.session_state.selected_answers:
        st.write("---")
        st.write("### 選択した回答をコピー用テキスト")
        copy_text = "\n".join(st.session_state.selected_answers)
        st.text_area("以下の内容をコピーしてください", value=copy_text, height=150)
        # 将来的にここに「動画生成」ボタンを追加します
        if st.button("🎬 動画を生成する (将来機能)", disabled=True):
            pass
