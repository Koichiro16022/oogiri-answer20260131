import streamlit as st
import google.generativeai as genai
import random
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip, AudioFileClip
from gtts import gTTS

# --- 1. 基本設定・API準備 ---
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("APIキーがSecretsに設定されていません。")

CHOSEN_MODEL = 'models/gemini-2.0-flash'
FONT_PATH = "NotoSansJP-Bold.ttf"
BASE_VIDEO = "template.mp4"

# デザイン設定（ブランドカラー：ネイビー & ゴールド）
st.markdown("""
    <style>
    .main { background-color: #001220; color: #E5E5E5; }
    .stButton>button { width: 100%; border-radius: 5px; font-weight: bold; transition: 0.3s; }
    .stButton>button:hover { transform: scale(1.02); opacity: 0.8; }
    div.stButton > button:first-child { background: linear-gradient(135deg, #FFD700 0%, #E5E5E5 100%); color: #001220; }
    </style>
    """, unsafe_allow_html=True)

st.title("大喜利アンサー ＆ 劇（GEKI）")

# --- 2. 状態管理 ---
if 'kw' not in st.session_state: st.session_state.kw = "孫"
if 'odais' not in st.session_state: st.session_state.odais = []
if 'selected_odai' not in st.session_state: st.session_state.selected_odai = ""
if 'ans_list' not in st.session_state: st.session_state.ans_list = []

# --- 3. 動画合成ロジック（劇） ---
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
    """template.mp4に文字と音声を合成"""
    if not os.path.exists(BASE_VIDEO):
        st.error(f"{BASE_VIDEO}が見つかりません。")
        return None

    try:
        video = VideoFileClip(BASE_VIDEO)
        
        # テロップ生成
        # ① お題（中央・大）: 1.2s - 7.4s
        img1 = create_text_image(odai, 90, "black", pos=(540, 960))
        clip1 = ImageClip(np.array(img1)).set_start(1.2).set_end(7.4).set_duration(6.2)
        
        # ② お題（モニター・小）: 7.4s - 8.6s
        img2 = create_text_image(odai, 45, "black", pos=(540, 220))
        clip2 = ImageClip(np.array(img2)).set_start(7.4).set_end(8.6).set_duration(1.2)
        
        # ③ 回答（フリップ中央・大）: 8.6s - 13.8s
        img3 = create_text_image(answer, 80, "black", pos=(540, 1050))
        clip3 = ImageClip(np.array(img3)).set_start(8.6).set_end(13.8).set_duration(5.2)

        # 音声生成
        full_text = f"{odai}。、、{answer}" # 間に読点をいれて間隔を調整
        tts = gTTS(full_text, lang='ja')
        tts.save("temp_voice.mp3")
        audio = AudioFileClip("temp_voice.mp3").set_start(1.2)

        # 合成
        final = CompositeVideoClip([video, clip1, clip2, clip3])
        # 元の動画に音がある場合はミックス、ない場合はTTSのみ
        final = final.set_audio(audio) 

        output_fn = "geki_output.mp4"
        final.write_videofile(output_fn, fps=24, codec="libx264", audio_codec="aac")
        return output_fn
    except Exception as e:
        st.error(f"合成エラー: {e}")
        return None

# --- 4. ブラウザUI（キーワード〜回答生成） ---
st.subheader("キーワードを入力してください")
col1, col2, col3 = st.columns([5, 1.5, 1.5])
with col1:
    st.session_state.kw = st.text_input("キーワード", value=st.session_state.kw, label_visibility="collapsed")
with col2:
    if st.button("消去"):
        st.session_state.kw = ""; st.rerun()
with col3:
    if st.button("ランダム"):
        words = ["AI", "孫", "無人島", "コンビニ", "サウナ", "キャンプ", "タイムマシン", "卒業式", "回転寿司", "SNS"]
        st.session_state.kw = random.choice(words); st.rerun()

if st.button("お題をAI生成", use_container_width=True):
    with st.spinner("閃き中..."):
        model = genai.GenerativeModel(CHOSEN_MODEL)
        prompt = f"「{st.session_state.kw}」テーマの大喜利お題を3つ。改行のみ出力。"
        res = model.generate_content(prompt)
        st.session_state.odais = [l.strip() for l in res.text.split('\n') if l.strip()][:3]
        st.rerun()

if st.session_state.odais:
    st.write("---")
    st.write("### お題を選択してください")
    for i, odai in enumerate(st.session_state.odais):
        if st.button(odai, key=f"odai_{i}"):
            st.session_state.selected_odai = odai
            st.session_state.ans_list = []; st.rerun()

if st.session_state.selected_odai:
    st.write("---")
    st.info(f"お題：{st.session_state.selected_odai}")
    tone = st.selectbox("ユーモアの種類", ["通常", "知的", "シュール", "ブラック", "ギャル風", "武士風"])
    
    if st.button("回答を20案表示", type="primary"):
        with st.spinner("爆速で20案生成中..."):
            model = genai.GenerativeModel(CHOSEN_MODEL, generation_config={"max_output_tokens": 2048, "temperature": 0.8})
            prompt = f"お題：{st.session_state.selected_odai}\n雰囲気：{tone}\nに対して爆笑回答を【必ず20案】、1行に1案。番号不要。"
            res = model.generate_content(prompt)
            st.session_state.ans_list = [l.strip() for l in res.text.split('\n') if l.strip()][:20]
            st.rerun()

# --- 5. 結果表示 ＆ 劇（動画生成）セクション ---
if st.session_state.ans_list:
    st.write(f"### 回答一覧（現在 {len(st.session_state.ans_list)} 案）")
    for i, ans in enumerate(st.session_state.ans_list):
        col_text, col_geki = st.columns([8, 2])
        col_text.write(ans)
        if col_geki.button("劇", key=f"geki_btn_{i}"):
            with st.spinner("劇を生成中..."):
                video_path = create_geki_video(st.session_state.selected_odai, ans)
                if video_path:
                    st.video(video_path)
                    with open(video_path, "rb") as f:
                        st.download_button("動画を保存", f, file_name=f"geki_{i}.mp4")
    
    st.write("---")
    st.caption("「私が100%制御しています」")
