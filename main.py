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

# --- 3. 音声生成用ヘルパー (MoviePy純正で沈黙を作る) ---
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

# --- 4. 動画合成ロジック ---
def create_text_image(text, fontsize, color, pos=(960, 540)):
    img = Image.new("RGBA", (1920, 1080), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(FONT_PATH, fontsize)
    except:
        return None
    clean_display = text.replace("_", "　")
    display_text = clean_display.replace("　", "\n").replace(" ", "\n")
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
    for f in [BASE_VIDEO, SOUND1, SOUND2]:
        if not os.path.exists(f):
            st.error(f"素材が見当たりません: {f}")
            return None
    try:
        video = VideoFileClip(BASE_VIDEO).without_audio()
        clean_ans = re.sub(r'^[0-9０-９\.\s、。・＊\*]+', '', answer).strip()
        i1 = create_text_image(odai, 100, "black", pos=(960, 530)) 
        i2 = create_text_image(odai, 55, "black", pos=(880, 300))
        i3 = create_text_image(clean_ans, 120, "black", pos=(960, 500))
        c1 = ImageClip(np.array(i1)).set_start(2.0).set_end(8.0).set_duration(6.0)
        c2 = ImageClip(np.array(i2)).set_start(8.0).set_end(10.0).set_duration(2.0)
        c3 = ImageClip(np.array(i3)).set_start(10.0).set_end(16.0).set_duration(6.0)
        voice_odai_clip = build_controlled_audio(odai, mode="gtts")
        voice_ans_clip = build_controlled_audio(clean_ans, mode="edge")
        audio_list = []
        if voice_odai_clip: audio_list.append(voice_odai_clip.set_start(2.5))
        if voice_ans_clip: audio_list.append(voice_ans_clip.set_start(10.5))
        s1_audio = AudioFileClip(SOUND1).set_start(0.8).volumex(0.2)
        s2_audio = AudioFileClip(SOUND2).set_start(9.0).volumex(0.3)
        audio_list.extend([s1_audio, s2_audio])
        combined_audio = CompositeAudioClip(audio_list)
        video_composite = CompositeVideoClip([video, c1, c2, c3], size=(1920, 1080))
        final = video_composite.set_audio(combined_audio)
        out = "geki.mp4"
        final.write_videofile(out, fps=24, codec="libx264", audio_codec="aac", temp_audiofile='temp-audio.m4a', remove_temp=True)
        video.close(); final.close()
        return out
    except Exception as e:
        st.error(f"合成失敗: {e}"); return None

# --- 5. 【100%制御】黄金の回答リスト（1/31当時の傑作選：感性同期の核） ---
GOLDEN_EXAMPLES = [
    {"odai": "目に入れても痛くない孫におじいちゃんがブチギレ。いったい何があった？", "ans": "おじいちゃんの入れ歯をメルカリで『ビンテージ雑貨』として出品していた"},
    {"odai": "この番組絶対ドッキリだろ！なぜ気付いた？", "ans": "通行人10人全員がよく見たらエキストラのバイト募集で見かけた顔だった"},
    {"odai": "ハゲてて良かった～なぜそう思った？", "ans": "職質のプロに『君、隠し事なさそうな頭してるね』とスルーされた"},
    {"odai": "ハゲてて良かった～なぜそう思った？", "ans": "美容師さんにお任せでと言ったら3秒で会計が終わった"},
    {"odai": "母親が私の友達に大激怒。いったい何があった？", "ans": "家族写真のお母さんの顔の部分だけに執拗に『ブサイクになるフィルター』をかけて保存した"},
    {"odai": "母親が私の友達に大激怒。いったい何があった？", "ans": "お母さんが大切にしている観葉植物を、勝手にメルカリで売れたんでと梱包し始めた"},
    {"odai": "母親が私の友達に大激怒。いったい何があった？", "ans": "おばさんその服カーテンと同じ柄ですね！と明るく指摘した"},
    {"odai": "母親が私の友達に大激怒。いったい何があった？", "ans": "お母さんの寝顔を勝手に撮影して#化け物 #拡散希望でアップしようとしていた"},
    {"odai": "とある大学のしきたりが1年生は全員激辛ラーメン一気食いだが、ある生徒だけは3年生になってもやらされていた。一体なぜ？", "ans": "あまりにも美味しそうに食べるので店側が『プロモーションビデオ』を撮り続けている"},
    {"odai": "とある大学のしきたりが1年生は全員激辛ラーメン一気食いだが、ある生徒だけは3年生になってもやらされていた。一体なぜ？", "ans": "激辛ラーメンを完食するまでが入学式というルールだがまだ一口も飲み込めていない"},
    {"odai": "とある大学のしきたりが1年生は全員激辛ラーメン一気食いだが、ある生徒だけは3年生になってもやらされていた。一体なぜ？", "ans": "『激辛ラーメン一気食い部』という世界で一番不毛な部活の部長になったから"},
    {"odai": "友達と2人で古畑任三郎を観ていて事件を解決した後、友達が必ずする行動とは？", "ans": "今回の犯行手口をChatGPTに入力し、『もっとバレにくい方法』を3案出させる"},
    {"odai": "友達と2人で古畑任三郎を観ていて事件を解決した後、友達が必ずする行動とは？", "ans": "真っ暗な部屋でおでこに人差し指を当てたままルンバの後をずっと追いかける"},
    {"odai": "友達と2人で古畑任三郎を観ていて事件を解決した後、友達が必ずする行動とは？", "ans": "警察の鑑識並みの手際で部屋に残った私の指紋をすべて拭き取り始める"}
]

# --- 6. UI ---
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
        prompt = f"「{st.session_state.kw}」をテーマに、思わず回答したくなる鋭い大喜利お題を3つ作成せよ。挨拶不要、お題のみを3行で。"
        r = m.generate_content(prompt)
        st.session_state.odais = [l.strip() for l in r.text.split('\n') if l.strip()][:3]
        st.session_state.selected_odai = ""; st.session_state.ans_list = []; st.rerun()

if st.session_state.odais:
    st.write("### お題を選択してください")
    for i, o in enumerate(st.session_state.odais):
        if st.button(o, key=f"o_btn_{i}"):
            st.session_state.selected_odai = o; st.session_state.ans_list = []; st.rerun()

if st.session_state.selected_odai:
    st.write("---")
    st.session_state.selected_odai = st.text_input("お題確定（_で0.1秒のタメ）", value=st.session_state.selected_odai)
    style_mode = st.selectbox("ユーモアの種類", ["通常", "知的", "シュール", "ブラック"])
    
    if st.button("回答20案生成", type="primary"):
        with st.spinner("魂の20案を捻り出し中..."):
            m = genai.GenerativeModel(CHOSEN_MODEL)
            examples_str = "\n".join([f"お題：{ex['odai']}\n回答：{ex['ans']}" for ex in GOLDEN_EXAMPLES])
            style_prompts = {
                "通常": "自由な発想で、最も爆笑を誘うボケを優先せよ。",
                "知的": "教養、専門用語、文学的表現などを用いたインテリなボケ。",
                "シュール": "不条理で独特な空気感を持つ、中毒性のあるボケ。",
                "ブラック": "人間の闇や社会の皮肉を突く、鋭い毒舌ボケ。"
            }
            p = f"""
            あなたは『ノブロックTV』の放送作家兼、伝説的な大喜利回答者です。
            【お題】: {st.session_state.selected_odai}
            【スタイル】: {style_prompts[style_mode]}

            【過去の最高傑作（これらを絶対的な手本にせよ）】
            {examples_str}

            【製作ルール】
            1. 1/31当時のキレを完全に取り戻せ。無難な回答はゴミ箱へ。
            2. 具体的な固有名詞（メルカリ、ルンバ、PV、ChatGPT等）や生々しい行動描写を多用せよ。
            3. 解説、挨拶、説明口調は一切禁止。
            4. 回答のみを20個、1. 2. 3. と番号を振り、1行1案で出力せよ。
            """
            r = m.generate_content(p)
            ls = [l.strip() for l in r.text.split('\n') if l.strip()]
            st.session_state.ans_list = [l for l in ls if not any(w in l for w in ["はい", "承知", "こちら", "紹介"])][:20]
            st.rerun()

if st.session_state.ans_list:
    st.write("---")
    st.write("### 回答一覧")
    for i in range(len(st.session_state.ans_list)):
        col_t, col_g = st.columns([9, 1])
        st.session_state.ans_list[i] = col_t.text_input(f"A{i+1}", value=st.session_state.ans_list[i], label_visibility="collapsed", key=f"ed_ans_{i}")
        if col_g.button("生成", key=f"b_gen_{i}"):
            with st.spinner("動画生成中..."):
                path = create_geki_video(st.session_state.selected_odai, st.session_state.ans_list[i])
                if path:
                    st.video(path); 
                    with open(path, "rb") as f: st.download_button("保存", f, file_name=f"geki_{i}.mp4", key=f"dl_{i}")

st.write("---")
st.caption("「私が100%制御しています」")
