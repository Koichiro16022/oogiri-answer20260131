import streamlit as st
import google.generativeai as genai

st.title("閃 - API診断モード")

if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
    
    st.write("### 現在利用可能なモデル一覧")
    
    try:
        # 利用可能なモデルを取得
        available_models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)
                st.code(f"モデル名: {m.name}\n表示名: {m.display_name}")
        
        if not available_models:
            st.warning("利用可能な生成モデルが見つかりませんでした。")
        else:
            st.success(f"合計 {len(available_models)} 個のモデルが見つかりました。")
            
    except Exception as e:
        st.error(f"モデルリストの取得中にエラーが発生しました: {e}")
        st.info("APIキーが正しく設定されているか、またはAPIが有効化されているか確認してください。")
else:
    st.error("SecretsにGEMINI_API_KEYが設定されていません。")
