def create_geki_video(odai, answer):
    # 素材チェック
    for f in [BASE_VIDEO, SOUND1, SOUND2]:
        if not os.path.exists(f):
            st.error(f"素材ファイルが見てかりません: {f}")
            return None
    
    try:
        # 1. 素材の読み込み (without_audioで元動画の音を完全シャットアウト)
        video = VideoFileClip(BASE_VIDEO).without_audio()
        clean_text = re.sub(r'^[0-9０-９\.\s、。・＊\*]+', '', answer).strip()
        
        # 2. 画像生成（お題、モニター、回答）
        i1 = create_text_image(odai, 100, "black", pos=(960, 530)) 
        i2 = create_text_image(odai, 60, "black", pos=(880, 300))
        i3 = create_text_image(clean_text, 120, "black", pos=(960, 500))
        
        # 3. 映像タイムライン設定
        c1 = ImageClip(np.array(i1)).set_start(2.0).set_end(8.0).set_duration(6.0)
        c2 = ImageClip(np.array(i2)).set_start(8.0).set_end(10.0).set_duration(2.0)
        c3 = ImageClip(np.array(i3)).set_start(10.1).set_end(16.0).set_duration(5.9)

        # 4. 音声の多重合成
        # A: ナレーション（2.5秒から「溜め」で開始）
        txt = f"{odai}。、、{clean_text}" 
        tts = gTTS(txt, lang='ja')
        tts.save("tmp_voice.mp3")
        voice_audio = AudioFileClip("tmp_voice.mp3").set_start(2.5)
        
        # B: 効果音1（1.5秒：お題直前の予兆）
        s1_audio = AudioFileClip(SOUND1).set_start(1.5)
        
        # C: 効果音2（8.0秒：回答への視線誘導）
        s2_audio = AudioFileClip(SOUND2).set_start(8.0)
        
        # すべての音声をミックス
        combined_audio = CompositeAudioClip([voice_audio, s1_audio, s2_audio])
        
        # 5. 最終合成
        video_composite = CompositeVideoClip([video, c1, c2, c3], size=(1920, 1080))
        final = video_composite.set_audio(combined_audio)
        
        # 6. 書き出し
        out = "geki.mp4"
        final.write_videofile(out, fps=24, codec="libx264", audio_codec="aac")
        
        # 7. リソース解放（これをしないと次回の生成でエラーになることがあります）
        video.close()
        voice_audio.close()
        s1_audio.close()
        s2_audio.close()
        final.close()
        
        return out
    except Exception as e:
        st.error(f"合成失敗: {e}")
        return None
