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
SOUND1 = "sound1.mp3"
SOUND2 = "sound2.mp3"

st.set_page_config(page_title="大喜利アンサー", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #001220; color: #E5E5E5; }
    .stButton>button { width: 100%; border-radius: 5px; font-weight: bold; }
    div.stButton > button:first-child { background: linear-gradient(135deg, #FFD700 0%, #E5E5E5 100%); color: #001220; }
    .stVideo { max-width: 100%; margin: auto; }
    /* 説明文のスタイルを調整 */
    .pronounce-box { 
        font-size: 0.85rem; 
        color: #FFD700; 
        margin-top: -10px; 
        margin-bottom: 15px; 
        line-height: 1.3;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 状態管理 ---
if 'kw' not in st.session_state: st.session_state.kw = "SNS"
if 'odais' not in st.session_state: st.session_state.odais = []
if 'selected_odai' not in st.session_state: st.session_state.selected_odai = ""
if 'ans_list' not in st.session_state: st.session_state.ans_list = []
if 'pronounce_list' not in st.session_state: st.session_state.pronounce_list = []

# 初期学習データ
if 'golden_examples' not in st.session_state:
    st.session_state.golden_examples = [
        {"odai": "目に入れても痛くない孫におじいちゃんがブチギレ。いったい何があった？", "ans": "おじいちゃんの入れ歯をメルカリで『ビンテージ雑貨』として出品していた"},
        {"odai": "この番組絶対ドッキリだろ！なぜ気付いた？", "ans": "通行人10人全員がよく見たらエキストラのバイト募集で見かけた顔だった"},
        {"odai": "ハゲてて良かった～なぜそう思った？", "ans": "職質のプロに『君、隠し事なさそうな頭してるね』とスルーされた"},
        {"odai": "ハゲてて良かった～なぜそう思った？", "ans": "美容師さんにお任せでと言ったら3秒で会計が終わった"},
        {"odai": "母親が私の友達に大激怒。いったい何があった？", "ans": "家族写真のお母さんの顔の部分だけに執拗に『ブサイクになるフィルター』をかけて保存した"},
        {"odai": "母親が私の友達に大激怒。いったい何があった？", "ans": "お母さんが大切にしている観葉植物を勝手にメルカリで売れたんでと梱包し始めた"},
        {"odai": "母親が私の友達に大激怒。いったい何があった？", "ans": "おばさんその服カーテンと同じ柄ですね！と明るく指摘した"},
        {"odai": "母親が私の友達に大激怒。いったい何があった？", "ans": "お母さんの寝顔を勝手に撮影して#化け物 #拡散希望でアップしようとしていた"},
        {"odai": "とある大学のしきたりが1年生は全員激辛ラーメン一気食いだが、ある生徒だけは3年生になってもやらされていた。一体なぜ？", "ans": "あまりにも美味しそうに食べるので店側が『プロモーションビデオ』を撮り続けている"},
        {"odai": "とある大学のしきたりが1年生は全員激辛ラーメン一気食いだが、ある生徒だけは3年生になってもやらされていた。一体なぜ？", "ans": "激辛ラーメンを完食するまでが入学式というルールだがまだ一口も飲み込めていない"},
        {"odai": "とある大学のしきたりが1年生は全員激辛ラーメン一気食いだが、ある生徒だけは3年生になってもやらされていた。一体なぜ？", "ans": "『激辛ラーメン一気食い部』という世界で一番不毛な部活の部長になったから"},
        {"odai": "友達と2人で古畑任三郎を観ていて事件を解決した後、友達が必ずする行動とは？", "ans": "今回の犯行手口をChatGPTに入力し、『もっとバレにくい方法』を3案出させる"},
        {"odai": "友達と2人で古畑任三郎を観ていて事件を解決した後、友達が必ずする行動とは？", "ans": "真っ暗な部屋でおでこに人差し指を当てたままルンバの後をずっと追いかける"},
        {"odai": "友達と2人で古畑任三郎を観ていて事件を解決した後、友達が必ずする行動とは？", "ans": "警察の鑑識並みの手際で部屋に残った私の指紋をすべて拭き取り始める"}
    ]

# --- 3. 音声・動画ロジック ---
async def save_edge_voice(text, filename, voice_name, rate="+15%"):
    communicate = edge_tts.Communicate(text, voice_name, rate=rate)
    await communicate.save(filename)

def make_silence(duration):
    return AudioClip(lambda t: [0, 0], duration=duration, fps=44100)

def build_controlled_audio(full_text, mode="gtts"):
    parts = re.split(r'(_+)', full_text)
    clips = []
    for i, part in enumerate(parts):
        if not part: continue
        if '_' in part:
            duration = len(part) * 0.1
            clips.append(make_silence(duration))
        else:
            tmp_filename = f"part_{mode}_{i}.mp3"
            if mode == "gtts":
                tts = gTTS(part, lang='ja')
                tts.save(tmp_filename)
            else:
                asyncio.run(save_edge_voice(part, tmp_filename, "ja-JP-KeitaNeural", rate="+15%"))
            clips.append(AudioFileClip(tmp_filename))
    if not clips: return None
    return concatenate_audioclips(clips)

def create_text_image(text, fontsize, color, pos=(960, 540)):
    """最終統合版: numpy配列を直接返すテキスト画像生成 (デバッグ情報削除)"""
    img = Image.new("RGBA", (1920, 1080), (25
