import streamlit as st
import google.generativeai as genai
import pandas as pd
import json

# API Ayarı
GOOGLE_API_KEY = st.secrets["API_KEY"]
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-3-flash-preview', generation_config={"temperature": 0.0})

st.set_page_config(page_title="SNU Kelime Asistanı", layout="centered")
st.title("🇰🇷 SNU Akıllı Çalışma Asistanı")

# Uygulama Hafızası (Session State)
if 'kelimeler' not in st.session_state:
    st.session_state.kelimeler = []
if 'mevcut_kart' not in st.session_state:
    st.session_state.mevcut_kart = 0
if 'kart_arkasi' not in st.session_state:
    st.session_state.kart_arkasi = False

# Arayüzü Sekmelere Bölme
tab1, tab2 = st.tabs(["📂 1. Veri Yükle", "🧠 2. Quizlet Modu"])

with tab1:
    st.subheader("Kitap Sayfası Yükle")
    yuklenen_dosya = st.file_uploader("Ders kitabı sayfasını yükle (JPG/PNG)", type=["jpg", "jpeg", "png"])
    
    if yuklenen_dosya is not None:
        if st.button("Kelimeleri Çıkar ve Desteye Ekle"):
            with st.spinner("Yapay zeka analiz ediyor..."):
                try:
                    gorsel_verisi = [{"mime_type": "image/jpeg", "data": yuklenen_dosya.getvalue()}]
                   komut = """
GÖREVİN: KATI BİR VERİ ÇIKARICISI OLMAKTIR. 
Aşağıdaki görselde YAZILI OLAN Korece kelimeleri tespit et.

KURALLAR:
1. SADECE ve SADECE görselde FİZİKSEL OLARAK BULUNAN kelimeleri çıkar. Görselde olmayan TEK BİR KELİME BİLE ekleme.
2. 가다, 보다, 친구, 먹다 gibi çok temel TOPIK 1 ve 2 seviyesi kelimelerini yoksay. Sadece orta ve ileri seviye hedefleri al.
3. Eksik kelime bırakma. Görseldeki tüm hedef kelimeleri tara.
4. Sadece JSON formatında çıktı ver, başka hiçbir metin yazma:
[{"korece": "kelime", "tr": "Türkçe", "en": "İngilizce", "ornek_ko": "Örnek Korece cümle", "ornek_tr": "Cümlenin Türkçesi"}]
"""
                    cevap = model.generate_content([komut, gorsel_verisi[0]])
                    json_metni = cevap.text.strip().replace("```json", "").replace("```", "")
                    veriler = json.loads(json_metni)
                    
                    # Çekilen kelimeleri desteye ekle
                    st.session_state.kelimeler.extend(veriler)
                    st.success(f"{len(veriler)} yeni kelime desteye eklendi! 'Quizlet Modu' sekmesine geçebilirsin.")
                except Exception as e:
                    st.error(f"Hata: {e}")

with tab2:
    if len(st.session_state.kelimeler) == 0:
        st.info("Destede kelime yok. Lütfen 1. sekmeden kitap yükleyerek kelime çıkarın.")
    else:
        toplam = len(st.session_state.kelimeler)
        index = st.session_state.mevcut_kart
        
        if index >= toplam:
            st.success("Tebrikler! Destede çalışılacak kelime kalmadı.")
            if st.button("Desteyi Sıfırla ve Baştan Başla"):
                st.session_state.mevcut_kart = 0
                st.session_state.kart_arkasi = False
                st.rerun()
        else:
            kart = st.session_state.kelimeler[index]
            
            st.progress(index / toplam)
            st.caption(f"Kalan Kelime: {toplam - index}")
            
            # Kartın Ön Yüzü
            st.markdown(f"<h1 style='text-align: center; font-size: 3em; color: #2e7bcf; margin-top: 20px;'>{kart['korece']}</h1>", unsafe_allow_html=True)
            
            # Kartın Arka Yüzü (Anlam Görülene Kadar Gizli)
            if not st.session_state.kart_arkasi:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Anlamını Gör", use_container_width=True):
                    st.session_state.kart_arkasi = True
                    st.rerun()
            else:
                st.markdown(f"<h3 style='text-align: center;'>🇹🇷 {kart['tr']}</h3>", unsafe_allow_html=True)
                st.markdown(f"<h4 style='text-align: center; color: gray;'>🇬🇧 {kart['en']}</h4>", unsafe_allow_html=True)
                st.info(f"**Örnek Cümle:** {kart['ornek_ko']}\n\n**Çeviri:** {kart['ornek_tr']}")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("❌ Bilemedim", use_container_width=True):
                        # Bilemediğin kelimeyi listenin en sonuna atar (Aralıklı Tekrar mantığı)
                        st.session_state.kelimeler.append(kart)
                        st.session_state.mevcut_kart += 1
                        st.session_state.kart_arkasi = False
                        st.rerun()
                with col2:
                    if st.button("✅ Bildim", use_container_width=True):
                        # Bildiğin kelimeyi geçer
                        st.session_state.mevcut_kart += 1
                        st.session_state.kart_arkasi = False
                        st.rerun()
