# --- main.py のモデル指定部分を以下に差し替え ---

# 診断結果から判明した「実在する」モデル名に修正
CHOSEN_MODEL = 'models/gemini-flash-latest' 

# もしくは、さらに新しいこれらもリストにありましたね：
# CHOSEN_MODEL = 'models/gemini-2.0-flash'
# CHOSEN_MODEL = 'models/gemini-3-flash-preview'

# --- 呼び出し部分の修正（安全策） ---
if st.button("お題をAI生成", use_container_width=True):
    with st.spinner("AIが思考中..."):
        try:
            # model_name引数を明示的に指定
            model = genai.GenerativeModel(model_name=CHOSEN_MODEL)
            prompt = f"「{st.session_state.kw}」で大喜利お題を3つ、改行区切りで出して。"
            res = call_gemini_with_retry(model, prompt)
            
            # テキスト抽出の安全性を高める
            if res and hasattr(res, 'text'):
                st.session_state.odais = [l.strip() for l in res.text.replace('*','').replace('-','').split('\n') if l.strip()]
                st.rerun()
