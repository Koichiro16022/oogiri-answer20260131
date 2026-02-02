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

# デザイン設定
st.markdown("""
    <style>
    .main { background-color: #001220; color: #E5E5E5; }
    .stButton>button { width: 100%; border-radius: 5px; font-weight: bold; transition: 0.3s; }
    div.stButton > button:first-child { background: linear-gradient(135deg, #FFD700 0%, #E5E5E5 100%); color: #001220; }
    .stTextInput { margin-bottom: 5px; }
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
    """透過背景にテキストを描画した画像を生成"""
    img = Image.new("RGBA", (1080, 1920), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(FONT_PATH, fontsize)
    except:
        return None
    
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
    draw.text((pos[0] - tw // 2, pos[1] - th // 2), text, font=font, fill=color)
    return img

def create_geki_video(odai, answer):
    """動画合成メインプロセス"""
    if not os.path.exists(BASE_VIDEO):
        st.error(f"{BASE_VIDEO}が見つかりません。")
        return None

    try:
        video = VideoFileClip(BASE_VIDEO)
        
        # クリーニング（番号等を排除）
        clean_text = re.sub(r'^[0-9０-９\.\s、。・＊\*]+', '', answer).strip()

        # テロップ生成（1.2s:全面、7.4s:モニター、8.6s:フリップ）
        img1 = create_text_image(odai, 90, "black", pos=(540, 960))
        clip1 = ImageClip(np.array(img1)).set_start(1.2).set_end(7.4).set_duration(6.2)
        
        img2 = create_text_image(odai, 45, "black", pos=(540, 220))
        clip2 = ImageClip(np.array(img2)).set_start(7.4).set_end(8.6).set_duration(1.2)
        
        img3 = create_text_image(clean_text, 80, "black", pos=(540, 1050))
        clip3 = ImageClip(np.array(img3)).set_start(8.6).set_end(13.8).set_duration(5.2)

        # 音声生成
        full_text = f"{odai}
