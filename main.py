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
    .stButton>button { width: 100%; border-radius: 5px; font-weight: bold; }
    div.stButton > button:first-child { background: linear-gradient(135deg, #FFD700 0%, #E5E5E5 100%); color: #001220; }
    .stVideo { max-width: 100%; margin: auto; }
    </style>
    """, unsafe_allow_html=True)

st.title("大喜利アンサー")

# --- 2. 状態管理 ---
if 'kw' not in st.session_state: st.session_state.kw = "孫"
if 'odais' not in st.session_state: st.session_state.odais = []
if 'selected_odai' not in st.session_state: st.session_state.selected_odai = ""
if 'ans_list' not in st.session_state: st.session_state.ans_list = []

# --- 3. 動画合成ロジック ---
def create_text_image(text, fontsize, color, pos=(960, 540)):
    """横長キャンバス(1920x1080)・中央揃え描画"""
    img = Image.new("RGBA", (1920, 1080), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(FONT_PATH, fontsize)
    except:
        return None
    
    display_text = text.replace("　", "\n").replace(" ", "\n")
    lines = display_text.split("\n")
    
    line_spacing = 15
    line_heights = [draw.textbbox((0, 0), line, font=font)[3] - draw.textbbox((0, 0), line, font=font)[1] for line in lines]
    total_height = sum(line_heights) + (len(lines) - 1) * line_spacing
    
    current_y = pos[1] - total_height // 2
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        line_w = bbox[2] - bbox[0]
        draw.text((pos[0] - line_w // 2, current_y), line, font=font, fill=color)
        current_y += line_heights[i] + line_spacing
    return img

def create_geki_video(odai, answer):
    if not os.path.exists(BASE_VIDEO):
        st.error("動画素材が見つかりません。")
        return None
    try:
        video = VideoFileClip(BASE_VIDEO)
        clean_text = re.sub(r'^[0-9０-９\.\s、。・＊\*]+', '', answer).strip()
        
        #
