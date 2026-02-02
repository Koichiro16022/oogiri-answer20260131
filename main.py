import re
import os
import random
import numpy as np
import streamlit as st
import google.generativeai as genai
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip, AudioFileClip
from gtts import gTTS

# --- 1. 基本設定 ---
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("APIキーがSecretsに設定されていません。")

CHOSEN_MODEL = 'models/gemini-2.0-flash'
FONT_PATH = "NotoSansJP-Bold.ttf"
BASE_VIDEO = "template.mp4"

st.set_page_config(page_title="大喜利アンサー", layout="centered")

# デザイン設定（ボタンの右寄せと入力欄の幅を最適化）
st.markdown("""
    <style>
    .main { background-color: #001220; color: #E5E5E5; }
    .stButton>button { width: 100%; border-radius: 5px; font-weight: bold; transition: 0.3s; }
    div.stButton > button:first-child { background: linear-gradient(135deg, #FFD700 0%, #E5E5E5 100%); color: #001220; }
    /* 入力欄とボタンの間の余白を調整 */
    .stTextInput { margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

st.title("大喜利アンサー")

# --- 2. 状態管理 ---
if 'kw' not in st.session_state: st.session_state.kw = "孫"
if 'odais' not in st.session_state: st.session_state.odais = []
if 'selected_odai' not in st.session_state: st.session_state.selected_odai = ""
if 'ans_list' not in st.session_state: st.session_state.ans_list = []

# --- 3. 動画合成ロジック ---
def create_text_image(text, fontsize, color, pos=(540, 960)):
    img = Image.new("RGBA", (1080, 1920), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(FONT_PATH, fontsize)
    except:
        st.error("フォントファイルが見つかりません。")
        return None
    
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
    draw.text((pos[0] - tw // 2, pos[1] - th // 2), text, font=font, fill=color)
    return img

def create_geki_video(odai, answer):
    if not os.path.exists(BASE_VIDEO):
        st.error(f"{BASE_VIDEO}が見つかりません。")
        return None

    try:
        video = VideoFileClip(BASE_VIDEO)
        clean_text = re.sub(r'^[0-9０-９\.\s、。・＊\*]+', '', answer).strip()

        img1 = create_text_image(odai, 90, "black", pos=(540, 960))
        clip1 = ImageClip(np.array(img1)).set_start(1.2).set_end(7.4).set_duration(6.2)
        
        img2 = create_text_image(odai, 45, "black", pos=(540, 220))
        clip2 = ImageClip(np.array(img2)).set_start(7.4).set_end(8.6).set_duration(1.2)
        
        img3 = create_text_image(clean_text, 80, "black", pos=(540, 1050))
        clip3 = ImageClip(np.array(img3)).set_start(8.6).set_end(13.8).set_duration(5.2)

        full_text = f"{odai}。、、{clean_text}" 
        tts = gTTS(full_text, lang='ja')
        tts.save("temp_voice.mp3")
        audio = AudioFileClip("temp_voice.mp3").set_start(1.2)

        final = CompositeVideoClip([video, clip1, clip2, clip3])
        final = final.set_audio(audio) 

        output_fn = "geki_output.mp4"
        final.write_videofile(output_fn, fps=24, codec="libx264", audio_codec="aac")
        return output_fn
    except Exception as e:
        st.error(f"合成エラー: {e}")
        return None

# --- 4. ブラウザUI ---
st.subheader("キーワードを入力してください")
col1, col2, col3 = st.columns([5, 1.5, 1.5])
with col1:
    st.session_state.kw = st.text_input("キーワード", value=st.session_state.kw, label_visibility="collapsed")
with col2:
    if st.button("消去"):
        st.session_state.kw = ""; st.rerun()
with col3:
    if st.button("ランダム"):
        words = ["AI", "孫", "無人島", "コンビニ", "タイムマシン", "サウナ", "キャンプ", "SNS"]
        st.session_state.kw = random.choice(words); st.rerun()

if st.button("お題をAI生成", use_container_width=True):
    with st.spinner("閃き中..."):
        model = genai.GenerativeModel(CHOSEN_MODEL)
        res = model.generate_content(f"「{st.session_state.kw}」の大喜利お題3つ。改行のみ出力。")
        st.session_state.odais = [l.strip() for l in res.text.split('\n') if l.strip()][:3]
        st.rerun()

if st.session_state.odais:
    st.write("---")
    for i, odai in enumerate(st.session_state.odais):
        if st.button(odai, key=f"odai_{i}"):
            st.session_state.selected_odai = odai
            st.session_state.ans_list = []; st.rerun()

if st.session_state.selected_odai:
    st.write("---")
    st.session_state.selected_odai = st.text_input("お題を修正・確定してください", value=st.session_state.selected_odai)
    
    if st.button("回答を20案表示", type="primary"):
        with st.spinner("20案生成中..."):
            model = genai.GenerativeModel(CHOSEN_MODEL)
            prompt = f"お題：{st.session_state.selected_odai}\nに対する爆笑回答を20案。1. 2. 3. と番号を振ってください。挨拶は一切不要。"
            res = model.generate_content(prompt)
            lines = [l.strip() for l in res.text.split('\n') if l.strip()]
            valid_ans = [l for l in lines if not any(word in l for word in ["はい", "承知", "提案", "紹介"])][:20]
            st.session_state.ans_list = valid_ans
            st.rerun()

# --- 5. 結果表示 ＆ 修正 ＆ 動画生成 ---
if st.session_state.ans_list:
    st.write(f"### 回答一覧（修正して動画を生成）")
    for i in range(len(st.session_state.ans_list)):
        # カラム比率を 8:2 に変更して、ボタンを右端へ
        col_text, col_geki = st.columns([8, 2])
        st.session_state.ans_list[i] = col_text.text_input(
            f"回答 {i+1}", 
            value=st.session_state.ans_list[i], 
            label_visibility="collapsed",
            key=f"ans_edit_{i}"
        )
        if col_geki.button("動画を生成", key=f"geki_btn_{i}"):
            with st.spinner("動画を生成中..."):
                video_path = create_geki_video(st.session_state.selected_odai, st.session_state.ans_list[i])
                if video_path:
                    st.video(video_path)
                    with open(video_path, "rb") as f:
                        st.download_button("動画を保存", f, file_name=f"geki_{i}.mp4")
    
    st.write("---")
    st.caption("「私が100%制御しています」")
