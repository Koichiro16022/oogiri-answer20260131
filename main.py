import re
import os
import random
import asyncio
import numpy as np
import streamlit as st
import google.generativeai as genai
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip, AudioFileClip, CompositeAudioClip, concatenate_audioclips, AudioClip
from gtts import gTTS
import edge_tts

# --- 1. 基本設定 ---
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("APIキーがSecretsに設定されていません。")

CHOSEN_MODEL = 'models/gemini-2.0-flash'
FONT_PATH = "NotoSansJP-Bold.ttf"
BASE_VIDEO = "template.mp4"
SOUND1 = "sound1.mp3"  # お題直前 (0.8s)
SOUND2 = "sound2.mp3"  # 回答誘導 (9.0s)

st.set_page_config(page_title="大喜利アンサー", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #001220; color: #E5E5E5; }
    .stButton>button { width: 100%; border-radius: 5px; font-weight: bold; }
    div.stButton > button:first-child { background: linear-gradient(135deg, #FFD700 0%, #E5E5E5 100%); color: #001220; }
    .stVideo { max-width: 100%; margin: auto; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 状態管理（学習データ含む） ---
if 'kw' not in st.session_state: st.session_state.kw = "SNS"
if 'odais' not in st.session_state: st.session_state.odais = []
if 'selected_odai' not in st.session_state: st.session_state.selected_odai = ""
if 'ans_list' not in st.session_state: st.session_state.ans_list = []

# 初期学習データ（1/31当時の傑作選）
if 'golden_examples' not in st.session_state:
    st.session_state.golden_examples = [
        {"odai": "目に入れても痛くない孫におじいちゃんがブチギレ。いったい何があった？", "ans": "おじいちゃんの入れ歯をメルカリで『ビンテージ雑貨』として出品していた"},
        {"odai": "この番組絶対ドッキリだろ！なぜ気付いた？", "ans": "通行人10人全員がよく見たらエキストラのバイト募集で見かけた顔だった"},
        {"odai": "ハゲてて良かった～なぜそう思った？", "ans": "職質のプロに『君、隠し事なさそうな頭してるね』とスルーされた"},
        {"odai": "ハゲてて良かった～なぜそう思った？", "ans": "美容師さんにお任せでと言ったら3秒で会計が終わった"},
        {"odai": "母親が私の友達に大激怒。いったい何があった？", "ans": "家族写真のお母さんの顔の部分だけに執拗に『ブサイクになるフィルター』をかけて保存した"},
        {"odai": "母親が私の友達に大激怒。いったい何があった？", "ans": "お母さんが大切にしている観葉植物を、勝手にメルカリで売れたんでと梱包し始めた"},
        {"odai": "母親が私の友達に大激怒。いったい何があった？", "ans": "おばさんその服カーテンと同じ柄ですね！と明るく指摘した"},
        {"odai": "母親が私の友達に大激怒。いったい何があった？", "ans": "お母さんの寝顔を勝手に
