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
import json
from datetime import datetime, timezone, timedelta

# --- 1. 基本設定 ---
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("APIキーがSecretsに設定されていません。")

CHOSEN_MODEL = 'models/gemini-2.0-flash'
FONT_PATH = "NotoSansJP-Bold.ttf"
BASE_VIDEO = "template.mp4"

# ここで定義（関数の外に書くことで、どこからでも参照可能になります）
SOUND1 = "sound1_v2.mp3"
SOUND2 = "sound2.mp3"

JST = timezone(timedelta(hours=9))  # ★日本時間用

st.set_page_config(page_title="大喜利アンサー", layout="wide")

# UIデザインのカスタマイズ
# --- 修正後：文字をすべて黒に統一、極太にして視認性を最大化 ---

st.markdown("""
    <style>
    .main { background-color: #001220; color: #E5E5E5; }
    .stButton>button { width: 100%; border-radius: 5px; font-weight: bold; }
    div.stButton > button:first-child { background: linear-gradient(135deg, #FFD700 0%, #E5E5E5 100%); color: #001220; }
    .stVideo { max-width: 100%; margin: auto; }
    
    /* 注釈テキストを黒に変更 */
    .pronounce-box, .odai-pronounce { 
        font-size: 0.85rem; 
        color: #000000 !important; 
        margin-top: -10px; 
        margin-bottom: 10px; 
        font-weight: 900;
    }
    
    /* 入力欄のラベル（説明文字）を黒に変更 */
    .stTextInput label, .stTextArea label {
        color: #000000 !important;
        font-size: 1.1rem !important;
        font-weight: 900 !important;
        margin-bottom: 5px;
    }

    /* 入力欄の中の文字色もより濃いネイビーに */
    div[data-baseweb="input"] > div, div[data-baseweb="base-input"] > textarea {
        background-color: #E1F5FE !important;
        color: #001220 !important;
        border-radius: 4px;
        font-weight: 700;
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

# ★学習データの読み込み
DATA_FILE = "learning_data.json"

def load_data():
    """起動時に学習データを読み込む"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # styleがないデータには"通常"を自動補完
                for item in data:
                    if 'style' not in item:
                        item['style'] = '通常'
                return data
        except Exception as e:
            st.error(f"データ読み込みエラー: {e}")
    
    # デフォルトデータ
    return [
        {"odai": "目に入れても痛くない孫におじいちゃんがブチギレ。いったい何があった？", "ans": "おじいちゃんの入れ歯をメルカリで『ビンテージ雑貨』として出品していた", "style": "通常"},
        {"odai": "この番組絶対ドッキリだろ！なぜ気付いた？", "ans": "通行人10人全員がよく見たらエキストラのバイト募集で見かけた顔だった", "style": "通常"},
        {"odai": "ハゲてて良かった～なぜそう思った？", "ans": "職質のプロに『君、隠し事なさそうな頭してるね』とスルーされた", "style": "通常"},
        {"odai": "ハゲてて良かった～なぜそう思った？", "ans": "美容師さんにお任せでと言ったら3秒で会計が終わった", "style": "通常"},
        {"odai": "母親が私の友達に大激怒。いったい何があった？", "ans": "家族写真のお母さんの顔の部分だけに執拗に『ブサイクになるフィルター』をかけて保存した", "style": "通常"},
        {"odai": "母親が私の友達に大激怒。いったい何があった？", "ans": "おばさんその服カーテンと同じ柄ですね！と明るく指摘した", "style": "通常"}
    ]

if 'golden_examples' not in st.session_state:
    st.session_state.golden_examples = load_data()

# --- 3. ロジック ---

def save_data():
    """学習データを自動保存"""
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(st.session_state.golden_examples, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        st.error(f"保存エラー: {e}")
        return False

async def save_edge_voice(text, filename, voice_name, rate="+20%"):
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
            # --- 修正：0.1 を 0.06 に変更 ---
            duration = len(part) * 0.06
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

# --- 修正：引数に canvas_size を追加し、サイズを可変にする ---
def create_text_image(text, fontsize, color, pos, canvas_size=(1920, 1080)):
    # 固定の (1920, 1080) ではなく、渡された canvas_size を使う
    img = Image.new("RGBA", canvas_size, (255, 255, 255, 0))
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

# --- 修正後：引数に video_mode を追加し、縦横の設定を分岐 ---

def create_geki_video(odai_display, odai_audio, answer_display, answer_audio, video_mode):
    global SOUND1, SOUND2  # これを追加！外側の変数を使うという宣言です
    import datetime
    jst = datetime.timezone(datetime.timedelta(hours=9))
    timestamp = datetime.datetime.now(jst).strftime('%Y%m%d_%H%M%S')
    out = f"{timestamp}.mp4" 

    # --- 形式に応じたレイアウト設定（100%制御） ---
    if video_mode == "縦動画 (9:16)":
        target_size = (1080, 1920)
        current_template = "template_v.mp4"
        # 縦動画用の配置（中央付近にレイアウト）
        pos_odai_main = (540, 850)   # お題（メイン）
        pos_odai_sub = (540, 500)    # お題（サブ・上部）
        pos_ans = (540, 850)        # 回答（中央やや下）
    else:
        # ★横動画の設定（今までの位置を維持）
        target_size = (1920, 1080)
        current_template = BASE_VIDEO
        pos_odai_main = (960, 530)
        pos_odai_sub = (880, 300)
        pos_ans = (960, 500)

    # チェック対象を current_template に変更
    for f in [current_template, SOUND1, SOUND2]:
        if not os.path.exists(f): 
            st.error(f"ファイルが見つかりません: {f}")
            return None
            
    try:
        # テンプレートを current_template に変更
        video = VideoFileClip(current_template).without_audio()
        
        # --- 修正後：文字数に応じた自動サイズ調整ロジック ---
        clean_ans_disp = re.sub(r'^[0-9０-９\.\s、。・＊\*]+', '', answer_display).strip()
        clean_ans_aud = re.sub(r'^[0-9０-９\.\s、。・＊\*]+', '', answer_audio).strip()

        # 文字数をカウント
        # --- 修正後：お題と回答の両方を自動サイズ調整 ---
        
        # 1. お題（メイン）のサイズ調整ロジック
        # --- 修正：お題と回答の最大サイズを 120 で統一 ---
        
        # 1. お題（メイン）のサイズ調整
        # --- 修正：すべてのテキスト（メイン・サブ・回答）を自動調整 ---
        
        # --- 決定版：すべてのテキストを自動調整（重複を排除） ---
        
        # 1. お題（メイン：i1）のサイズ調整
        odai_len = len(odai_display)
        if odai_len <= 10:
            odai_main_fontsize = 120
        elif odai_len <= 20:
            odai_main_fontsize = 100
        elif odai_len <= 30:
            odai_main_fontsize = 80
        else:
            odai_main_fontsize = 65

        # 2. お題サブ (i2: 背景パネル用) のサイズ
        # 150から、パネルにちょうど収まる「100」前後に戻します
        if odai_len <= 10:
            odai_sub_fontsize = 120   # ★ここを150から120へ
        elif odai_len <= 20:
            odai_sub_fontsize = 100    # ★ここを75から100へ
        elif odai_len <= 30:
            odai_sub_fontsize = 80    # ★ここを80へ
        else:
            odai_sub_fontsize = 80    # ★ここも80に修正した

        # 3. 回答（i3）のサイズ調整
        ans_len = len(clean_ans_disp)
        if ans_len <= 10:
            ans_fontsize = 120
        elif ans_len <= 20:
            ans_fontsize = 100
        else:
            ans_fontsize = 80

        # --- 画像生成（決定したフォントサイズを反映） ---
        i1 = create_text_image(odai_display, odai_main_fontsize, "black", pos=pos_odai_main, canvas_size=target_size) 
        i2 = create_text_image(odai_display, odai_sub_fontsize, "black", pos=pos_odai_sub, canvas_size=target_size)
        i3 = create_text_image(clean_ans_disp, ans_fontsize, "black", pos=pos_ans, canvas_size=target_size)
        
        c1 = ImageClip(i1).set_start(2.0).set_end(8.0)
        c2 = ImageClip(i2).set_start(8.0).set_end(10.0)
        c3 = ImageClip(i3).set_start(10.0).set_end(16.0)
        
        # 音声合成の処理（変更なし）
        voice_odai_clip = build_controlled_audio(odai_audio, mode="gtts")
        voice_ans_clip = build_controlled_audio(clean_ans_aud, mode="edge")
        
        audio_list = []
        if voice_odai_clip: audio_list.append(voice_odai_clip.set_start(2.5))
        if voice_ans_clip: audio_list.append(voice_ans_clip.set_start(10.5))
        
        # 呪いを解く「絶対固定」のロジック
        if os.path.exists(SOUND1):
            # normalizeは素材に依存して計算がブレるため、あえて削除。
            # 直接、数値で叩く。これが最も「計算ミス」が起きない形です。
            s1_clip = AudioFileClip(SOUND1).set_start(0.8).volumex(0.03)
            audio_list.append(s1_clip)
            
        if os.path.exists(SOUND2):
            s2_clip = AudioFileClip(SOUND2).set_start(9.0).volumex(0.2)
            audio_list.append(s2_clip)
        
        # ★size を target_size に変更
        final = CompositeVideoClip([video, c1, c2, c3], size=target_size).set_audio(CompositeAudioClip(audio_list))
        
        final.write_videofile(out, fps=24, codec="libx264", audio_codec="aac", temp_audiofile='temp-audio.m4a', remove_temp=True, logger=None)
        
        video.close()
        if voice_odai_clip: voice_odai_clip.close()
        if voice_ans_clip: voice_ans_clip.close()
        final.close()
        
        return out
        
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
    
    # 学習フォーム
    with st.form("learning_form", clear_on_submit=True):
        new_odai = st.text_area("お題を追加", height=150, placeholder="ここに新しいお題を入力してください...")
        new_ans = st.text_area("回答を追加", height=150, placeholder="ここに新しい回答を入力してください...")
        
        # ★追加：ユーモアの種類を選択できるようにする
        new_style = st.selectbox("ユーモアの種類", ["通常", "知的", "ブラック"])
        
        if st.form_submit_button("感性を覚えさせる"):
            if new_odai and new_ans:
                is_duplicate = any(
                    ex["odai"] == new_odai and ex["ans"] == new_ans 
                    for ex in st.session_state.golden_examples
                )
                if not is_duplicate:
                    # ★修正：固定の "通常" ではなく、選んだ new_style を保存する
                    st.session_state.golden_examples.append({
                        "odai": new_odai, 
                        "ans": new_ans, 
                        "style": new_style 
                    })
                    if save_data():
                        st.success("✅ 登録し、保存しました")
                        # 画面をリロードして反映
                        st.rerun() 
                    else:
                        st.error("❌ 登録しましたが保存に失敗しました")
                else:
                    st.warning("⚠️ すでに登録されています")
    
    st.write("---")
    st.subheader("💾 データ管理")

    # --- 追加：学習データ編集・削除機能 ---
    if st.session_state.golden_examples:
        with st.expander("📝 登録済みデータの編集・削除"):
            for idx, item in enumerate(st.session_state.golden_examples):
                col_e1, col_e2, col_e3 = st.columns([2, 5, 1])
                
                # ユーモア種類の変更
                new_item_style = col_e1.selectbox(
                    f"種別 {idx}", ["通常", "知的", "ブラック"], 
                    index=["通常", "知的", "ブラック"].index(item.get("style", "通常")),
                    key=f"edit_style_{idx}", label_visibility="collapsed"
                )
                
                # 回答内容の修正（text_input から text_area に変更し、高さを調整）
                new_item_ans = col_e2.text_area(
                    f"回答 {idx}", value=item["ans"], 
                    height=80,  # 約2〜3行分の高さ
                    key=f"edit_ans_{idx}", label_visibility="collapsed"
                )
                
                # 削除ボタン
                if col_e3.button("❌", key=f"del_{idx}"):
                    st.session_state.golden_examples.pop(idx)
                    save_data()
                    st.rerun()
                
                # 値が変更されたら即座に反映
                if new_item_style != item.get("style") or new_item_ans != item["ans"]:
                    st.session_state.golden_examples[idx]["style"] = new_item_style
                    st.session_state.golden_examples[idx]["ans"] = new_item_ans
                    save_data()
    # ------------------------------------
    
    # エクスポート（★日本時間に修正）
    if st.session_state.golden_examples:
        json_str = json.dumps(st.session_state.golden_examples, ensure_ascii=False, indent=2)
        timestamp = datetime.now(JST).strftime('%Y%m%d_%H%M%S')  # ★JST適用
        st.download_button(
            "📥 エクスポート",
            json_str,
            file_name=f"learning_data_{timestamp}.json",
            mime="application/json",
            use_container_width=True
        )
    
    # インポート
    uploaded_file = st.file_uploader("📁 インポート", type=['json'])
    
    if uploaded_file is not None:
        try:
            imported_data = json.load(uploaded_file)
            
            for item in imported_data:
                if 'style' not in item:
                    item['style'] = '通常'
            
            st.info(f"📊 {len(imported_data)}件のデータが見つかりました")
            st.caption("統合方法を選択してください")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("➕ 追加", use_container_width=True, help="既存データを残して追加します（重複は自動除外）"):
                    added_count = 0
                    for item in imported_data:
                        is_duplicate = any(
                            ex["odai"] == item["odai"] and ex["ans"] == item["ans"]
                            for ex in st.session_state.golden_examples
                        )
                        if not is_duplicate:
                            st.session_state.golden_examples.append(item)
                            added_count += 1
                    
                    if save_data():
                        if added_count > 0:
                            st.success(f"✅ {added_count}件を追加しました")
                        if len(imported_data) - added_count > 0:
                            st.info(f"ℹ️ 重複{len(imported_data)-added_count}件を除外しました")
                        st.rerun()
            
            with col2:
                if st.button("🔄 上書き", use_container_width=True, help="既存データを削除して置き換えます"):
                    st.session_state.golden_examples = imported_data
                    if save_data():
                        st.success(f"✅ {len(imported_data)}件で上書きしました")
                        st.rerun()
        
        except Exception as e:
            st.error(f"❌ インポートエラー: {e}")

# --- 5. メインUI ---
st.title("大喜利アンサー")

# 1. 選択肢の定義
mode_options = ["縦動画 (9:16)", "横動画 (16:9)"]

# 2. 初回起動時のみ初期値をセット
if "video_mode_selector" not in st.session_state:
    st.session_state.video_mode_selector = "縦動画 (9:16)"

# 3. 選択が変わった瞬間に実行される関数（これが確実に保持する秘訣）
def on_mode_change():
    # ラジオボタンの値を即座にセッション状態に固定する
    st.session_state.video_mode_selector = st.session_state.new_mode

# 4. ラジオボタン本体
video_mode = st.radio(
    "動画形式を選択してください", 
    mode_options,
    index=mode_options.index(st.session_state.video_mode_selector),
    key="new_mode",          # 一時的な入力キー
    on_change=on_mode_change, # 変わった瞬間に保存関数を呼ぶ
    horizontal=True
)

# 最終的にシステムが使う変数を同期
video_mode = st.session_state.video_mode_selector
st.write("---") # 区切り線

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
        
        lines = r.text.split('\n')
        odais = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            cleaned = re.sub(r'^[0-9０-９]+[\.．\s]+', '', line).strip()
            if len(cleaned) >= 10:
                odais.append(cleaned)
        
        st.session_state.odais = odais[:3]
        
        if not st.session_state.odais:
            st.error("お題の生成に失敗しました。もう一度試してください。")
        
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
    
    st.write("---")
    st.subheader("🎭 回答の生成")

    # --- 修正後：3種類に集約 ---
    style = st.selectbox("ユーモアの種類", ["通常", "知的", "ブラック"])
    
    
    if st.button("🚀 回答20案生成", type="primary", use_container_width=True):
        with st.spinner("爆笑を追求中..."):
            m = genai.GenerativeModel(CHOSEN_MODEL)
            ex_str = "\n".join([f"・{e['ans']}" for e in st.session_state.golden_examples])
            
            #p = f"""あなたは伝説の大喜利芸人です。

#お題: {st.session_state.selected_odai}
#雰囲気: {style}

#参考となる傑作回答:
#{ex_str}

#指示:
#1. 上記の手本を参考に、同じレベルの面白い回答を20個考えろ
#2. 挨拶、説明、前置きは絶対に書くな
#3. 番号付きリスト形式で出力しろ（1. 回答）
#4. カッコ書きの説明は禁止
#5. 回答だけを書け
#"""
            
# --- 修正後：YouTubeチャンネル『大喜利アンサー』専用プロンプト ---
            p = f"""あなたはYouTubeチャンネル『大喜利アンサー』を運営する伝説のクリエイター兼大喜利芸人です。
視聴者が思わず吹き出し、チャンネル登録したくなるようなキレ味鋭い回答を生成してください。

【お題】: {st.session_state.selected_odai}
【ユーモアの方向性】: {style}

【大喜利アンサー 傑作選（このトーンを再現せよ）】:
{ex_str}

【絶対ルール】:
1. 傑作選の「視点の鋭さ」「短文での爆発力」を継承し、同等以上の回答を考えろ。
2. 「ブラック」指定時は、YouTubeの規約に触れない絶妙なラインで、シュールかつ猛毒な笑いを攻めろ。
3. 挨拶・前置き・「はい、回答します」等は一切禁止。即座に回答を始めろ。
4. 番号付きリスト形式（1. 回答）で、正確に20案出力しろ。
5. 言葉を削ぎ落とし、視聴者の想像力を刺激する一撃のフレーズを重視しろ。
"""
            r = m.generate_content(p)
            
            all_lines = [l.strip() for l in r.text.split('\n') if l.strip()]
            ans_raw = []
            
            for line in all_lines:
                if re.match(r'^[0-9０-９]+[\.．、。\s]', line):
                    if not any(word in line[:20] for word in ['はい', '承知', 'それでは', '以下', '提案']):
                        # ★番号を削除してから追加
                        cleaned_line = re.sub(r'^[0-9０-９]+[\.．、。\s]+', '', line).strip()
                        ans_raw.append(cleaned_line)
                                    
            st.session_state.ans_list = ans_raw[:20]
            st.session_state.pronounce_list = ans_raw[:20]
            st.rerun()

if st.session_state.ans_list:
    st.write("---")
    st.write("### 📋 回答一覧")
    
    for i in range(len(st.session_state.ans_list)):
        col_text, col_button = st.columns([9, 1])
        
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
        
        with col_button:
            st.write("")
            st.write("")
            if st.button("生成", key=f"b_{i}"):
                with st.spinner("動画生成中..."):
                    path = create_geki_video(
                        st.session_state.selected_odai, 
                        st.session_state.selected_odai_pron, 
                        st.session_state.ans_list[i], 
                        st.session_state.pronounce_list[i],
                        video_mode  # ★ここに追加した video_mode を渡します
                    )
                    # ★変更点1：動画プレイヤーをここで出さず、パスだけを保存する
                    if path:
                        st.session_state[f"temp_video_{i}"] = path

        # ★変更点2：with col_button の外（インデントを戻した位置）で大きく表示する
        # ★修正箇所：if文の直後の行をすべて1段下げます
        # ★ここから修正（ifの前のスペースを調整して with col_button の外に出します）
        # --- 修正：動画表示と保存ボタンのブロック ---
        # --- 修正：動画表示と保存ボタンのブロック（強制サイズ固定版） ---
        # --- 修正：縦動画プレビュー時の全体幅制限 ---
        # --- 修正：動画表示と保存ボタンのブロック（縦横両方のサイズを最適化） ---
        if f"temp_video_{i}" in st.session_state:
            video_path = st.session_state[f"temp_video_{i}"]
            
            if video_mode == "縦動画 (9:16)":
                # 【縦動画】Koichiroさんの黄金設定
                st.markdown(
                    """
                    <style>
                        div[data-testid="stMainBlockContainer"] { max-width: 1000px !important; margin: auto; }
                        video { max-height: 500px; width: auto !important; margin: auto; display: block; }
                    </style>
                    """, 
                    unsafe_allow_html=True
                )
                st.video(video_path)
            else:
                # 【横動画】ここを新しく制御！
                st.markdown(
                    """
                    <style>
                        /* 横動画の時は幅を広めに戻しつつ、高さを抑える */
                        div[data-testid="stMainBlockContainer"] { max-width: 1200px !important; margin: auto; }
                        video { 
                            max-height: 450px; /* ここでお好みの高さに制限 */
                            width: auto !important; 
                            margin: auto; 
                            display: block; 
                        }
                    </style>
                    """, 
                    unsafe_allow_html=True
                )
                st.video(video_path)
            
            # 保存ボタン（共通）
            with open(video_path, "rb") as f:
                st.download_button(
                    "💾 保存", 
                    f, 
                    file_name=video_path, 
                    key=f"dl_final_perfect_{i}",
                    use_container_width=True
                )
st.write("---")
st.caption("「私が100%制御しています」")
