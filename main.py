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

# UIデザインのカスタマイズ
st.markdown("""
    <style>
    .main { background-color: #001220; color: #E5E5E5; }
    .stButton>button { width: 100%; border-radius: 5px; font-weight: bold; }
    div.stButton > button:first-child { background: linear-gradient(135deg, #FFD700 0%, #E5E5E5 100%); color: #001220; }
    .stVideo { max-width: 100%; margin: auto; }
    
    /* 注釈テキスト */
    .pronounce-box { 
        font-size: 0.8rem; 
        color: #FFD700 !important; 
        margin-top: -10px; 
        margin-bottom: 10px; 
        font-weight: bold;
    }
    .odai-pronounce { 
        font-size: 0.85rem; 
        color: #00FFCC !important; 
        margin-top: -15px; 
        margin-bottom: 10px; 
        font-weight: bold;
    }
    
    /* 入力欄のラベル */
    .stTextInput label, .stTextArea label {
        color: #E5E5E5 !important;
        font-size: 1rem !important;
        font-weight: 700 !important;
        margin-bottom: 5px;
    }

    /* 入力欄の背景色 */
    div[data-baseweb="input"] > div, div[data-baseweb="base-input"] > textarea {
        background-color: #E1F5FE !important;
        color: #01579B !important;
        border-radius: 4px;
        font-weight: 600;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 状態管理 ---
if 'kw' not in st.session_state: st.session_state.kw = "SNS"
if 'odais' not in st.session_state: st.session_state.odais = []
if 'selected_odai' not in st.session_state: st.session_state.selected_odai = ""
if 'selected_odai_pron' not in st.session_state: st.session_state.selected_odai_pron = ""
if 'ans_list' not in st.session_state: st.session_state.ans_list = []
if 'pronounce_list' not in st.session_state: st.session_state.pronounce_list = []

if 'golden_examples' not in st.session_state:
    st.session_state.golden_examples = [
        {"odai": "目に入れても痛くない孫におじいちゃんがブチギレ。いったい何があった？", "ans": "おじいちゃんの入れ歯をメルカリで『ビンテージ雑貨』として出品していた"},
        {"odai": "この番組絶対ドッキリだろ！なぜ気付いた？", "ans": "通行人10人全員がよく見たらエキストラのバイト募集で見かけた顔だった"},
        {"odai": "ハゲてて良かった～なぜそう思った？", "ans": "職質のプロに『君、隠し事なさそうな頭してるね』とスルーされた"},
        {"odai": "ハゲてて良かった～なぜそう思った？", "ans": "美容師さんにお任せでと言ったら3秒で会計が終わった"},
        {"odai": "母親が私の友達に大激怒。いったい何があった？", "ans": "家族写真のお母さんの顔の部分だけに執拗に『ブサイクになるフィルター』をかけて保存した"},
        {"odai": "母親が私の友達に大激怒。いったい何があった？", "ans": "おばさんその服カーテンと同じ柄ですね！と明るく指摘した"}
    ]

# --- 3. ロジック ---
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
    img = Image.new("RGBA", (1920, 1080), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    try: 
        font = ImageFont.truetype(FONT_PATH, fontsize)
    except: 
        font = ImageFont.load_default()
    
    clean_display = text.replace("_", "")
    display_text = clean_display.replace("　", "\n").replace(" ", "\n")
    lines = [l for l in display_text.split("\n") if l.strip()]
    if not lines: lines = [" "]
    
    line_spacing = 15
    line_heights = [draw.textbbox((0, 0), line, font=font)[3] - draw.textbbox((0, 0), line, font=font)[1] for line in lines]
    total_height = sum(line_heights) + (len(lines) - 1) * line_spacing
    
    current_y = pos[1] - total_height // 2
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        line_w = bbox[2] - bbox[0]
        draw.text((pos[0] - line_w // 2, current_y), line, font=font, fill=color)
        current_y += line_heights[i] + line_spacing
    
    return np.array(img)

def create_geki_video(odai_display, odai_audio, answer_display, answer_audio):
    for f in [BASE_VIDEO, SOUND1, SOUND2]:
        if not os.path.exists(f): 
            st.error(f"ファイルが見つかりません: {f}")
            return None
    try:
        video = VideoFileClip(BASE_VIDEO).without_audio()
        
        clean_ans_disp = re.sub(r'^[0-9０-９\.\s、。・＊\*]+', '', answer_display).strip()
        clean_ans_aud = re.sub(r'^[0-9０-９\.\s、。・＊\*]+', '', answer_audio).strip()
        
        i1 = create_text_image(odai_display, 100, "black", pos=(960, 530)) 
        i2 = create_text_image(odai_display, 55, "black", pos=(880, 300))
        i3 = create_text_image(clean_ans_disp, 120, "black", pos=(960, 500))
        
        c1 = ImageClip(i1).set_start(2.0).set_end(8.0)
        c2 = ImageClip(i2).set_start(8.0).set_end(10.0)
        c3 = ImageClip(i3).set_start(10.0).set_end(16.0)
        
        voice_odai_clip = build_controlled_audio(odai_audio, mode="gtts")
        voice_ans_clip = build_controlled_audio(clean_ans_aud, mode="edge")
        
        audio_list = []
        if voice_odai_clip: audio_list.append(voice_odai_clip.set_start(2.5))
        if voice_ans_clip: audio_list.append(voice_ans_clip.set_start(10.5))
        
        if os.path.exists(SOUND1):
            audio_list.append(AudioFileClip(SOUND1).set_start(0.8).volumex(0.2))
        if os.path.exists(SOUND2):
            audio_list.append(AudioFileClip(SOUND2).set_start(9.0).volumex(0.3))
        
        final = CompositeVideoClip([video, c1, c2, c3], size=(1920, 1080)).set_audio(CompositeAudioClip(audio_list))
        out = "geki.mp4"
        final.write_videofile(out, fps=24, codec="libx264", audio_codec="aac", temp_audiofile='temp-audio.m4a', remove_temp=True, logger=None)
        
        video.close()
        if voice_odai_clip: voice_odai_clip.close()
        if voice_ans_clip: voice_ans_clip.close()
        final.close()
        
        return out
    except Exception as e:
        st.error(f"合成失敗: {e}")
        import traceback
        st.error(traceback.format_exc())
        return None

# --- 4. サイドバー ---
with st.sidebar:
    st.header("🧠 感性同期・追加学習")
    with st.form("learning_form", clear_on_submit=True):
        new_odai = st.text_area("お題を追加", height=100)
        new_ans = st.text_input("回答を追加")
        if st.form_submit_button("感性を覚えさせる"):
            if new_odai and new_ans:
                is_duplicate = any(ex["odai"] == new_odai and ex["ans"] == new_ans for ex in st.session_state.golden_examples)
                if not is_duplicate:
                    st.session_state.golden_examples.append({"odai": new_odai, "ans": new_ans})
                    st.success("登録しました。")
                else:
                    st.warning("すでに登録されています。")
    
    st.write(f"### 学習済みリスト ({len(st.session_state.golden_examples)}件)")
    for i, ex in enumerate(reversed(st.session_state.golden_examples[-5:])):
        with st.expander(f"傑作 {i+1}"):
            st.write(f"**お題**: {ex['odai']}")
            st.write(f"**回答**: {ex['ans']}")

# --- 5. メインUI ---
st.title("大喜利アンサー")

kw_col, clr_col, rnd_col = st.columns([5, 1, 1])
st.session_state.kw = kw_col.text_input("キーワード入力", value=st.session_state.kw, label_visibility="collapsed")
if clr_col.button("消去"): 
    st.session_state.kw = ""
    st.rerun()
if rnd_col.button("ランダム"): 
    st.session_state.kw = random.choice(["SNS", "古畑任三郎", "母親", "サウナ", "孫", "無人島"])
    st.rerun()

if st.button("お題生成", use_container_width=True):
    with st.spinner("厳選中..."):
        m = genai.GenerativeModel(CHOSEN_MODEL)
        prompt = f"「{st.session_state.kw}」をテーマにした大喜利お題を3つ作れ。お題だけを3行で出力。"
        r = m.generate_content(prompt)
        
        # 各行から番号を削除してお題だけを抽出
        lines = r.text.split('\n')
        odais = []
        
        for line in lines:
            line = line.strip()
            
            # 空行はスキップ
            if not line:
                continue
            
            # 番号を削除（1. や 2. など）
            cleaned = re.sub(r'^[0-9０-９]+[\.．\s]+', '', line).strip()
            
            # 10文字以上の有効なお題のみ追加
            if len(cleaned) >= 10:
                odais.append(cleaned)
        
        # お題をセッションに保存
        st.session_state.odais = odais[:3]
        
        # お題が取得できなかった場合
        if not st.session_state.odais:
            st.error("お題の生成に失敗しました。もう一度試してください。")
        
        # リセット
        st.session_state.selected_odai = ""
        st.session_state.ans_list = []
        st.session_state.pronounce_list = []
        st.rerun()



if st.session_state.odais:
    st.write("### 📝 お題を選択してください")
    for i, o in enumerate(st.session_state.odais):
        if st.button(o, key=f"o_{i}"): 
            st.session_state.selected_odai = o
            st.session_state.selected_odai_pron = o
            st.session_state.ans_list = []
            st.session_state.pronounce_list = []
            st.rerun()

if st.session_state.selected_odai:
    st.write("---")
    
    # ★修正: お題入力セクションを明確に
    st.subheader("🎯 お題の設定")
    st.session_state.selected_odai = st.text_input(
        "お題確定（スペースで改行）", 
        value=st.session_state.selected_odai
    )
    st.session_state.selected_odai_pron = st.text_input(
        "お題の読み修正（_で無音のタメ）", 
        value=st.session_state.selected_odai_pron
    )
    st.markdown('<p class="odai-pronounce">💡 お題の発音修正（例: なん、いい、_でタメ）</p>', unsafe_allow_html=True)
    
    # ★修正: スタイル選択とボタンを明確に分離
    st.write("---")
    st.subheader("🎭 回答の生成")
    
    style = st.selectbox("ユーモアの種類", ["通常", "知的", "シュール", "ブラック"])
    
    # ★修正: ボタンの配置を明確に
    if st.button("🚀 回答20案生成", type="primary", use_container_width=True):
        with st.spinner("爆笑を追求中..."):
            m = genai.GenerativeModel(CHOSEN_MODEL)
            ex_str = "\n".join([f"・{e['ans']}" for e in st.session_state.golden_examples])
            
            p = f"""あなたは伝説の大喜利芸人です。

お題: {st.session_state.selected_odai}
雰囲気: {style}

参考となる傑作回答:
{ex_str}

指示:
1. 上記の手本を参考に、同じレベルの面白い回答を20個考えろ
2. 挨拶、説明、前置きは絶対に書くな
3. 番号付きリスト形式で出力しろ（1. 回答）
4. カッコ書きの説明は禁止
5. 回答だけを書け
"""
            r = m.generate_content(p)
            
            all_lines = [l.strip() for l in r.text.split('\n') if l.strip()]
            ans_raw = []
            
            for line in all_lines:
                # 番号で始まる行のみ
                if re.match(r'^[0-9０-９]+[\.．、。\s]', line):
                    # 挨拶を含む行を除外
                    if not any(word in line[:20] for word in ['はい', '承知', 'それでは', '以下', '提案']):
                        ans_raw.append(line)
            
            st.session_state.ans_list = ans_raw[:20]
            st.session_state.pronounce_list = ans_raw[:20]
            st.rerun()

if st.session_state.ans_list:
    st.write("---")
    st.write("### 📋 回答一覧")
    
    for i in range(len(st.session_state.ans_list)):
        # ★修正: columnsを使って横並びレイアウト
        col_text, col_button = st.columns([9, 1])
        
        # 左側：テキスト入力欄（字幕と読み）
        with col_text:
            st.session_state.ans_list[i] = st.text_input(
                f"字幕案 {i+1}（スペースで改行）", 
                value=st.session_state.ans_list[i], 
                key=f"disp_{i}"
            )
            st.session_state.pronounce_list[i] = st.text_input(
                f"読み案 {i+1}（_で無音のタメ）", 
                value=st.session_state.pronounce_list[i], 
                key=f"pron_{i}", 
                label_visibility="collapsed"
            )
            st.markdown('<p class="pronounce-box">💡 読み修正（例: なん、いい、_でタメ）</p>', unsafe_allow_html=True)
        
        # 右側：生成ボタン
        with col_button:
            # ★修正: ボタンの位置を調整するため空白を追加
            st.write("")  # 1行分の空白
            if st.button("生成", key=f"b_{i}"):
                with st.spinner("動画生成中..."):
                    path = create_geki_video(
                        st.session_state.selected_odai, 
                        st.session_state.selected_odai_pron, 
                        st.session_state.ans_list[i], 
                        st.session_state.pronounce_list[i]
                    )
                    if path:
                        st.video(path)
                        with open(path, "rb") as f:
                            st.download_button("💾 保存", f, file_name=f"geki_{i}.mp4", key=f"dl_{i}")

st.write("---")
st.caption("「私が100%制御しています」")
