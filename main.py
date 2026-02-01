import streamlit as st
import google.generativeai as genai
import random

# --- 設定・API準備 ---
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("APIキーがSecretsに設定されていません。")

# 有料枠を活かす最新モデル
CHOSEN_MODEL = 'models/gemini-2.0-flash'

# デザイン設定
st.markdown("""
    <style>
    .main { background-color: #001220; color: #E5E5E5; }
    .stButton>button { width: 100%; border-radius: 5px; font-weight: bold; transition: 0.3s; }
    .stButton>button:hover { transform: scale(1.02); opacity: 0.8; }
    div.stButton > button:first-child { background: linear-gradient(135deg, #FFD700 0%, #E5E5E5 100%); color: #001220; }
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
        # キーワードを大幅拡充（50種以上）
        words = [
            "孫", "AI", "無人島", "コンビニ", "タイムマシン", "入れ歯", "メルカリ", "宇宙飛行士", 
            "給食", "透明人間", "ゾンビ", "全自動", "婚活", "新幹線", "卒業式", "サウナ",
            "タピオカ", "選挙", "工事現場", "忍者", "デスゲーム", "おばあちゃん", "回転寿司",
            "スマートスピーカー", "Uber Eats", "官房長官", "マッチングアプリ", "呪いのビデオ",
            "授業参観", "宝くじ", "無重力", "確定申告", "キャンプ", "SNS", "メタバース"
        ]
        st.session_state.kw = random.choice(words)
        st.rerun()

if st.button("お題をAI生成", use_container_width=True):
    with st.spinner("閃き中..."):
        try:
            model = genai.GenerativeModel(CHOSEN_MODEL)
            prompt = f"「{st.session_state.kw}」をテーマにした、IPPONグランプリのような大喜利のお題を3つ、改行のみで出力してください。余計な説明は不要です。"
            res = model.generate_content(prompt)
            st.session_state.odais = [l.strip() for l in res.text.replace('*','').split('\n') if l.strip()][:3]
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
    st.info(f"お題：{st.session_state.selected_odai}")
    tone = st.selectbox("ユーモアの種類", ["通常", "知的", "シュール", "ブラック", "ギャル風", "武士風"])
    
    if st.button("回答を20案表示", type="primary"):
        with st.spinner("爆速で20案生成中..."):
            try:
                # 生成パラメータを調整して「長文」を許可
                model = genai.GenerativeModel(
                    CHOSEN_MODEL,
                    generation_config={"max_output_tokens": 2048, "temperature": 0.8}
                )
                prompt = f"お題：{st.session_state.selected_odai}\n雰囲気：{tone}\nに対して、爆笑を生む回答を【必ず20案】、1行に1案、番号なし・改行のみで出力してください。20個に満たないことは許されません。"
                res = model.generate_content(prompt)
                
                # 行ごとに分割して空行を除去
                raw_ans = [l.strip() for l in res.text.replace('*','').replace('・','').split('\n') if l.strip()]
                st.session_state.ans_list = raw_ans[:20] # 念のため20案でカット
                st.rerun()
            except Exception as e:
                st.error(f"回答生成エラー: {e}")

# --- 4. 結果表示 ---
if st.session_state.ans_list:
    st.write(f"### 回答一覧（現在 {len(st.session_state.ans_list)} 案）")
    sel = []
    for i, ans in enumerate(st.session_state.ans_list):
        if st.checkbox(ans, key=f"ans_check_{i}"):
            sel.append(ans)
    
    if sel:
        st.write("---")
        st.write("### 選択した回答をコピー")
        st.text_area("コピー用", value="\n".join(sel), height=150)
        st.caption("「私が100%制御しています」")
