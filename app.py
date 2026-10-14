import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import random

# API Ayarı
GOOGLE_API_KEY = st.secrets["API_KEY"]
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-3-flash-preview', generation_config={"temperature": 0.0})

st.set_page_config(page_title="SNU Kelime Asistanı", layout="centered")
st.title("🇰🇷 SNU Akıllı Çalışma Asistanı")

# Uygulama Hafızası (Session State)
if 'kelimeler' not in st.session_state: st.session_state.kelimeler = []
if 'calisilmis' not in st.session_state: st.session_state.calisilmis = []
if 'gecmis' not in st.session_state: st.session_state.gecmis = []
if 'kart_arkasi' not in st.session_state: st.session_state.kart_arkasi = False

tab1, tab2 = st.tabs(["📂 1. Veri Yükle", "🧠 2. Quizlet Modu"])

with tab1:
    st.subheader("Kitap Sayfası Ekle")
    # 2. Özellik: Telefondan doğrudan kamerayı açma seçeneği
    ekleme_yontemi = st.radio("Fotoğraf Ekleme Yöntemi:", ["📸 Kamerayla Çek (Telefondan)", "📂 Dosya Yükle (Galeriden)"], horizontal=True)
    
    gorsel = None
    if ekleme_yontemi == "📸 Kamerayla Çek (Telefondan)":
        gorsel = st.camera_input("Kamerayı Aç")
    else:
        gorsel = st.file_uploader("Ders kitabı sayfasını yükle (JPG/PNG)", type=["jpg", "jpeg", "png"])
    
    if gorsel is not None:
        if st.button("Kelimeleri Çıkar ve Desteye Ekle"):
            with st.spinner("Yapay zeka matbaa ve el yazısı notları analiz ediyor..."):
                try:
                    gorsel_verisi = [{"mime_type": "image/jpeg", "data": gorsel.getvalue()}]
                    
                    # El yazısı tanıma eklendi
                    komut = """
GÖREVİN: KATI BİR VERİ ÇIKARICISI OLMAKTIR. 
Aşağıdaki görselde yer alan Korece kelimeleri ve açıklamaları analiz et.

KURALLAR:
1. Sayfadaki matbaa baskısı kelimelerin yanı sıra, sayfanın kenarlarına veya kelime altlarına EL YAZISIYLA eklenmiş tüm notları, yeni kelimeleri ve açıklamaları KESİNLİKLE tespit et.
2. SADECE görselde fiziksel olarak (baskı veya el yazısı) bulunan verileri kullan.
3. 가다, 보다, 친구, 먹다 gibi çok temel TOPIK 1 ve 2 kelimelerini yoksay.
4. El yazısı notlar mevcut bir kelimenin açıklamasıysa, o kelimenin 'tr' veya 'en' alanına entegre et. Tamamen yeni bir kelimeyse bağımsız bir madde olarak listeye ekle.
5. Sadece JSON formatında çıktı ver, başka metin yazma:
[{"korece": "kelime", "tr": "Türkçe (ve el yazısı notlar)", "en": "İngilizce", "ornek_ko": "Örnek cümle", "ornek_tr": "Cümlenin çevirisi"}]
"""
                    cevap = model.generate_content([komut, gorsel_verisi[0]])
                    json_metni = cevap.text.strip().replace("```json", "").replace("```", "")
                    veriler = json.loads(json_metni)
                    
                    # 1. Özellik: Daha önce eklenmiş kelimeleri eleme (Deduplication)
                    mevcut_korece = {k['korece'] for k in st.session_state.kelimeler + st.session_state.calisilmis}
                    yeni_kelimeler = [k for k in veriler if k['korece'] not in mevcut_korece]
                    
                    st.session_state.kelimeler.extend(yeni_kelimeler)
                    
                    # 3. Özellik: Desteyi sıralı değil, rastgele karıştırarak sorma
                    random.shuffle(st.session_state.kelimeler)
                    
                    eleni_sayisi = len(veriler) - len(yeni_kelimeler)
                    mesaj = f"{len(yeni_kelimeler)} yeni kelime desteye eklendi!"
                    if eleni_sayisi > 0:
                        mesaj += f" (Zaten listede olan {eleni_sayisi} kelime elendi)."
                    st.success(mesaj)
                    
                except Exception as e:
                    st.error(f"Hata: {e}")

with tab2:
    # 4. Özellik: Geri Al (Undo) Tuşu
    if len(st.session_state.gecmis) > 0:
        if st.button("↩️ Son İşlemi Geri Al (Yanlış Tıkladım)"):
            son_islem = st.session_state.gecmis.pop()
            if son_islem['islem'] == 'bildim':
                st.session_state.calisilmis.remove(son_islem['kelime'])
                st.session_state.kelimeler.insert(0, son_islem['kelime'])
            elif son_islem['islem'] == 'bilemedim':
                st.session_state.kelimeler.pop() # Sona atılan kelimeyi geri al
                st.session_state.kelimeler.insert(0, son_islem['kelime'])
            st.session_state.kart_arkasi = False
            st.rerun()

    st.markdown("---")

    if len(st.session_state.kelimeler) == 0:
        if len(st.session_state.calisilmis) == 0:
            st.info("Destede kelime yok. Lütfen 1. sekmeden kitap yükleyerek kelime çıkarın.")
        else:
            st.success(f"Tebrikler! Desteyi bitirdin. Toplam {len(st.session_state.calisilmis)} kelime öğrenilenlere eklendi.")
            if st.button("Çalışılmış Kelimeleri Baştan Karıştır ve Tekrar Et"):
                st.session_state.kelimeler = st.session_state.calisilmis.copy()
                st.session_state.calisilmis = []
                random.shuffle(st.session_state.kelimeler)
                st.session_state.kart_arkasi = False
                st.rerun()
    else:
        toplam_kelime = len(st.session_state.kelimeler) + len(st.session_state.calisilmis)
        ilerleme_orani = len(st.session_state.calisilmis) / toplam_kelime if toplam_kelime > 0 else 0
        
        st.progress(ilerleme_orani)
        st.caption(f"Öğrenilen: {len(st.session_state.calisilmis)} | Kalan: {len(st.session_state.kelimeler)}")
        
        kart = st.session_state.kelimeler[0]
        
        st.markdown(f"<h1 style='text-align: center; font-size: 3em; color: #2e7bcf; margin-top: 20px;'>{kart['korece']}</h1>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        
        if not st.session_state.kart_arkasi:
            col1, col2 = st.columns(2)
            with col1:
                if st.button("❌ Bilemedim (Anlamı Göster)", use_container_width=True):
                    st.session_state.kart_arkasi = True
                    st.rerun()
            with col2:
                if st.button("✅ Bildim (Öğrenilenlere Ekle)", use_container_width=True):
                    islem_karti = st.session_state.kelimeler.pop(0)
                    st.session_state.calisilmis.append(islem_karti)
                    st.session_state.gecmis.append({'kelime': islem_karti, 'islem': 'bildim'})
                    st.session_state.kart_arkasi = False
                    st.rerun()
        else:
            st.markdown(f"<h3 style='text-align: center;'>🇹🇷 {kart['tr']}</h3>", unsafe_allow_html=True)
            st.markdown(f"<h4 style='text-align: center; color: gray;'>🇬🇧 {kart['en']}</h4>", unsafe_allow_html=True)
            st.info(f"**Örnek Cümle:** {kart['ornek_ko']}\n\n**Çeviri:** {kart['ornek_tr']}")
            
            if st.button("Destenin Sonuna Ekle ve Devam Et", use_container_width=True):
                islem_karti = st.session_state.kelimeler.pop(0)
                st.session_state.kelimeler.append(islem_karti) 
                st.session_state.gecmis.append({'kelime': islem_karti, 'islem': 'bilemedim'})
                st.session_state.kart_arkasi = False
                st.rerun()
