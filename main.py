import re
import os
import random
import numpy as np
import streamlit as st
import google.generativeai as genai
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip, AudioFileClip, CompositeAudioClip
from gtts import gTTS

# --- 1. 基本設定 ---
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("APIキーがSecretsに設定されていません。")

CHOSEN_MODEL = 'models/gemini-2.0-flash'
FONT_PATH = "NotoSansJP-Bold.ttf"
BASE_VIDEO = "template.mp4"
SOUND1 = "sound1.mp3"  # お題直前の効果音 (1.5s)
SOUND2 = "sound2.mp3"  # モニター・回答誘導の効果音 (8.0s)

# レイアウト設定
st.set_page_config(page_title="大喜利アンサー", layout="centered")

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
    # 素材の物理チェック
    for f in [BASE_VIDEO, SOUND1, SOUND2]:
        if not os.path.exists(f):
            st.error(f"素材ファイルが見当たりません: {f}")
            return None
    
    try:
        # 1. 素材の読み込み（無音化）
        video = VideoFileClip(BASE_VIDEO).without_audio()
        clean_text = re.sub(r'^[0-9０-９\.\s、。・＊\*]+', '', answer).strip()
        
        # 2. テロップ画像生成（確定座標）
        i1 = create_text_image(odai, 100, "black", pos=(960, 530)) 
        i2 = create_text_image(odai, 60, "black", pos=(880, 300))
        i3 = create_text_image(clean_text, 120, "black", pos=(960, 500))
        
        # 3. 映像タイムライン設定
        c1 = ImageClip(np.array(i1)).set_start(2.0).set_end(8.0).set_duration(6.0)
        c2 = ImageClip(np.array(i2)).set_start(8.0).set_end(10.0).set_duration(2.0)
        c3 = ImageClip(np.array(i3)).set_start(10.1).set_end(16.0).set_duration(5.9)

        # 4. 音声の多重合成
        # A: ナレーション（2.5s開始、溜めの演出）
        txt = f"{odai}。、、{clean_text}" 
        tts = gTTS(txt, lang='ja')
        tts.save("tmp_voice.mp3")
        voice_audio = AudioFileClip("tmp_voice.mp3").set_start(2.5)
        
        # B: 効果音1（1.5s：お題直前の予兆）
        s1_audio = AudioFileClip(SOUND1).set_start(1.0)
        
        # C: 効果音2（8.0s：回答への視線誘導）
        s2_audio = AudioFileClip(SOUND2).set_start(8.0)
        
        # ミックス
        combined_audio = CompositeAudioClip([voice_audio, s1_audio, s2_audio])
        
        # 5. 最終合成
        video_composite = CompositeVideoClip([video, c1, c2, c3], size=(1920, 1080))
        final = video_composite.set_audio(combined_audio)
        
        # 6. 書き出し
        out = "geki.mp4"
        final.write_videofile(
            out, 
            fps=24, 
            codec="libx264", 
            audio_codec="aac",
            temp_audiofile='temp-audio.m4a',
            remove_temp=True
        )
        
        # 7. リソース解放
        video.close()
        voice_audio.close()
        s1_audio.close()
        s2_audio.close()
        final.close()
        
        return out
    except Exception as e:
        st.error(f"合成失敗: {e}")
        return None

# --- 4. UI ---
st.subheader("キーワード")
col1, col2, col3 = st.columns([5, 1.5, 1.5])
with col1:
    st.session_state.kw = st.text_input("KW", value=st.session_state.kw, label_visibility="collapsed")
with col2:
    if st.button("消去"):
        st.session_state.kw = ""; st.rerun()
with col3:
    if st.button("ランダム"):
        ws = ["AI", "孫", "無人島", "コンビニ", "サウナ", "SNS"]
        st.session_state.kw = random.choice(ws); st.rerun()

if st.button("お題生成", use_container_width=True):
    with st.spinner("閃き中..."):
        m = genai.GenerativeModel(CHOSEN_MODEL)
        prompt = f"「{st.session_state.kw}」テーマの大喜利お題（IPPON風）を3つ、改行のみ。挨拶不要。"
        r = m.generate_content(prompt)
        st.session_state.odais = [l.strip() for l in r.text.split('\n') if l.strip()][:3]
        st.session_state.selected_odai = ""
        st.session_state.ans_list = []
        st.rerun()

if st.session_state.odais:
    st.write("### お題を選択してください")
    for i, o in enumerate(st.session_state.odais):
        if st.button(o, key=f"o_btn_{i}"):
            st.session_state.selected_odai = o
            st.session_state.ans_list = []
            st.rerun()

if st.session_state.selected_odai:
    st.write("---")
    st.session_state.selected_odai = st.text_input(
        "お題確定（改行箇所にスペースを入れてください）", 
        value=st.session_state.selected_odai
    )
    
    tone = st.selectbox("ユーモアの種類", ["通常", "知的", "シュール", "ブラック"])
    
    if st.button("回答20案生成", type="primary"):
        with st.spinner("生成中..."):
            m = genai.GenerativeModel(CHOSEN_MODEL)
            p = f"お題：{st.session_state.selected_odai}\n雰囲気：{tone}\n回答20案。1.2.3.と番号を振り1行1案。挨拶不要。"
            r = m.generate_content(p)
            ls = [l.strip() for l in r.text.split('\n') if l.strip()]
            st.session_state.ans_list = [l for l in ls if not any(w in l for w in ["はい", "承知", "紹介"])][:20]
            st.rerun()

if st.session_state.ans_list:
    st.write("---")
    st.write("### 回答一覧")
    for i in range(len(st.session_state.ans_list)):
        col_t, col_g = st.columns([9, 1])
        st.session_state.ans_list[i] = col_t.text_input(
            f"A{i+1}", 
            value=st.session_state.ans_list[i], 
            label_visibility="collapsed", 
            key=f"ed_ans_{i}"
        )
        if col_g.button("生成", key=f"b_gen_{i}"):
            with st.spinner("動画生成中..."):
                path = create_geki_video(st.session_state.selected_odai, st.session_state.ans_list[i])
                if path:
                    st.video(path)
                    with open(path, "rb") as f:
                        st.download_button("保存", f, file_name=f"geki_{i}.mp4")
    
    st.write("---")
    st.caption("「私が100%制御しています」")
