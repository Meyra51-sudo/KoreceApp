import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import random

# API Ayarı
GOOGLE_API_KEY = st.secrets["API_KEY"]
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-3-flash-preview', generation_config={"temperature": 0.0})

st.set_page_config(page_title="MEYRA", layout="centered")
st.title("🇰🇷 MEYRA")

# Motivasyon Cümleleri (Parantezsiz)
motivasyonlar = [
    "오늘 너무 예뻐요!",
    "포기하지 마세요!",
    "오늘도 화이팅!",
    "한국어 천재 메이라!",
    "할 수 있어요!"
]
if 'gunluk_mesaj' not in st.session_state:
    st.session_state.gunluk_mesaj = random.choice(motivasyonlar)

topik_4_gramerler = ["-아/어 보이다", "-(으)ㄹ 뿐만 아니라", "-(으)ㄴ/는 데다가", "-기 마련이다", "-(으)ㄴ/는 척하다", "-(으)ㄹ 뻔하다", "-느라고"]

# Uygulama Hafızası
if 'kelimeler' not in st.session_state: st.session_state.kelimeler = []
if 'calisilmis' not in st.session_state: st.session_state.calisilmis = []
if 'gecmis' not in st.session_state: st.session_state.gecmis = []
if 'kart_arkasi' not in st.session_state: st.session_state.kart_arkasi = False
if 'gramer_feedback' not in st.session_state: st.session_state.gramer_feedback = None
if 'zor_pratik_modu' not in st.session_state: st.session_state.zor_pratik_modu = False
if 'secilen_gramer' not in st.session_state: st.session_state.secilen_gramer = ""

tab1, tab2, tab3 = st.tabs(["📂 1. Yükle", "🧠 2. Çalışma Modu", "⚙️ 3. Düzenle"])

with tab1:
    st.markdown("<h2 style='text-align: center;'>Hoşgeldin 메이라</h2>", unsafe_allow_html=True)
    st.markdown(f"<h4 style='text-align: center; color: #2e7bcf;'>{st.session_state.gunluk_mesaj}</h4>", unsafe_allow_html=True)
    st.markdown("---")
    
    st.info("Kameranı açmak için 'Browse files' butonuna tıklayabilirsin.")
    gorsel = st.file_uploader("Fotoğraf Çek veya Yükle", type=["jpg", "jpeg", "png"])
    
    if gorsel is not None:
        if st.button("Analiz Et ve Desteye Ekle"):
            with st.spinner("Öğretmen Meyra için notları analiz ediyor..."):
                try:
                    gorsel_verisi = [{"mime_type": "image/jpeg", "data": gorsel.getvalue()}]
                    komut = """
GÖREVİN: KATI BİR VERİ ÇIKARICISI OLMAKTIR. 
Görseldeki Korece kelimeleri, el yazısı notları ve dilbilgisi (gramer) kurallarını çıkar.

KURALLAR (MEYRA'NIN NOT ALMA STİLİ):
1. ALTI ÇİZİLİ KELİMELER: Unutulan kelimelerdir. TOPIK 1-2 seviyesi bile olsa ALTI ÇİZİLİ HER KELİMEYİ LİSTEYE EKLE.
2. ZIT ANLAMLILAR (X İŞARETİ): "가다 x 오다" gibi arasına 'x' veya 'X' koyulmuş kelimeler zıt anlamlıdır. Tek maddede topla. "korece" kısmına ana kelimeyi, "tr" kısmına "Anlamı (Zıt Anlamlısı: [Diğer Kelime])" yaz.
3. GRAMER KURALLARI: Yeni dilbilgisi kalıplarını çıkar ve "tip" değerini "gramer" yap.
4. KELİMELER: Gramer dışındakilerin "tip" değerini "kelime" yap. Sadece TOPIK 4+ kelimeleri al. Eşanlamlıları virgülle tek satırda birleştir.
5. ÖRNEK CÜMLELER (ÇOK ÖNEMLİ): "ornek_ko" oluştururken şu İKİ KURALA KESİNLİKLE UY: 
   A) Özneler HER ZAMAN ünlü kişiler, bilim insanları veya tarihi karakterler olmalı (Örn: 아인슈타인, 마이클 잭슨, 백설공주 vb.).
   B) Cümlelerin içinde mutlaka Korece sayma kelimeleri (개, 명, 마리, 권 등) ve rakamlar bulunmalı.
6. Sadece JSON formatında çıktı ver:
[{"tip": "kelime/gramer", "korece": "hedef metin", "tr": "Türkçe", "en": "İngilizce", "ornek_ko": "Örnek cümle", "ornek_tr": "Çevirisi", "is_hard": false, "hard_streak": 0, "interval": 1, "ease": 2.5}]
"""
                    cevap = model.generate_content([komut, gorsel_verisi[0]])
                    json_metni = cevap.text.strip().replace("```json", "").replace("```", "")
                    veriler = json.loads(json_metni)
                    
                    mevcut_korece = {k['korece'] for k in st.session_state.kelimeler + st.session_state.calisilmis}
                    yeni_maddeler = [k for k in veriler if k['korece'] not in mevcut_korece]
                    
                    st.session_state.kelimeler.extend(yeni_maddeler)
                    random.shuffle(st.session_state.kelimeler)
                    st.success(f"{len(yeni_maddeler)} yeni madde desteye eklendi!")
                    
                except Exception as e:
                    st.error(f"Hata: {e}")

with tab2:
    zor_kelime_sayisi = sum(1 for k in (st.session_state.kelimeler + st.session_state.calisilmis) if k.get('is_hard', False))
    toplam_ogrenilen = len(st.session_state.calisilmis)
    tekrar_bekleyen = len(st.session_state.kelimeler)
    
    colA, colB, colC = st.columns(3)
    colA.metric("📚 Öğrenilen", toplam_ogrenilen)
    colB.metric("⏳ Bekleyen", tekrar_bekleyen)
    colC.metric("🔥 Zor Kelimeler", zor_kelime_sayisi)
    st.markdown("---")

    if len(st.session_state.gecmis) > 0 and not st.session_state.zor_pratik_modu and not st.session_state.gramer_feedback:
        if st.button("↩️ Son İşlemi Geri Al"):
            son_islem = st.session_state.gecmis.pop()
            if son_islem['islem'] == 'bildim':
                st.session_state.calisilmis.remove(son_islem['kelime'])
                st.session_state.kelimeler.insert(0, son_islem['kelime'])
            elif son_islem['islem'] in ['bilemedim', 'zor', 'gramer_tekrar']:
                st.session_state.kelimeler.pop() 
                st.session_state.kelimeler.insert(0, son_islem['kelime'])
            st.session_state.kart_arkasi = False
            st.rerun()

    if len(st.session_state.kelimeler) == 0:
        if len(st.session_state.calisilmis) == 0:
            st.info("Destede madde yok. Lütfen kitap yükleyin.")
        else:
            st.success("Harikasın Meyra! Bugünlük desteyi bitirdin.")
            if st.button("Öğrenilenleri Baştan Karıştır"):
                st.session_state.kelimeler = st.session_state.calisilmis.copy()
                st.session_state.calisilmis = []
                random.shuffle(st.session_state.kelimeler)
                st.session_state.kart_arkasi = False
                st.rerun()
    else:
        kart = st.session_state.kelimeler[0]
        
        # --- ZOR KELİME PRATİK MODU ---
        if st.session_state.zor_pratik_modu:
            st.markdown(f"<h2 style='text-align: center; color: #ff8c00;'>🔥 Zor Kelime Pratiği</h2>", unsafe_allow_html=True)
            st.markdown(f"<h1 style='text-align: center;'>{kart['korece']}</h1>", unsafe_allow_html=True)
            st.info(f"**Meyra, bu kelimeyi kullanarak bir cümle kur.**\n\n📌 **Görev:** Cümleyi kurarken **{st.session_state.secilen_gramer}** gramer kuralını da kullanmaya çalış!")
            
            kullanici_cumlesi = st.text_input("Korece cümleni buraya yaz:")
            
            if st.button("Öğretmene Gönder", use_container_width=True):
                if kullanici_cumlesi:
                    with st.spinner("Öğretmen cümleni okuyor..."):
                        geribildirim_komutu = f"Senin adın AI Öğretmen. Karşındaki öğrencinin adı Meyra. Onunla arkadaşça, samimi ve sen diliyle konuş (Örn: 'Harikasın Meyra!'). Asla 'arkadaşın' gibi 3. şahıs kelimeler kullanma. Meyra şu kelimeyi: '{kart['korece']}' ve şu grameri: '{st.session_state.secilen_gramer}' kullanarak şu cümleyi kurdu: '{kullanici_cumlesi}'. Cümle doğru mu? Hata varsa doğrudan ona açıklayarak düzelt."
                        cevap = model.generate_content(geribildirim_komutu)
                        st.session_state.gramer_feedback = cevap.text
            
            if st.session_state.gramer_feedback:
                st.success("👩‍🏫 **Öğretmenin Geri Bildirimi:**")
                st.write(st.session_state.gramer_feedback)
                
                if st.button("Devam Et", use_container_width=True):
                    kart['hard_streak'] = kart.get('hard_streak', 0) + 1
                    if kart['hard_streak'] >= 3:
                        st.session_state.zor_pratik_modu = False
                        st.session_state.gramer_feedback = None
                        st.rerun()
                    else:
                        islem_karti = st.session_state.kelimeler.pop(0)
                        st.session_state.kelimeler.append(islem_karti)
                        st.session_state.gecmis.append({'kelime': islem_karti, 'islem': 'zor'})
                        st.session_state.zor_pratik_modu = False
                        st.session_state.gramer_feedback = None
                        st.session_state.kart_arkasi = False
                        st.rerun()

        # --- GRAMER KARTI (GERİ GELDİ!) ---
        elif kart.get('tip') == 'gramer':
            st.markdown(f"<h1 style='text-align: center; color: #ff4b4b; margin-top: 20px;'>{kart['korece']}</h1>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; font-weight: bold; color: gray;'>[Gramer / Dilbilgisi]</p>", unsafe_allow_html=True)
            st.info(f"**Anlamı:** {kart['tr']}\n\n**Örnek:** {kart['ornek_ko']} ({kart['ornek_tr']})")
            
            kullanici_cumlesi = st.text_input("Bu grameri kullanarak kendi Korece cümleni kur Meyra:")
            
            if st.button("Cümlemi Kontrol Et", use_container_width=True):
                if kullanici_cumlesi:
                    with st.spinner("Öğretmen cümleni inceliyor..."):
                        geribildirim_komutu = f"Senin adın AI Öğretmen. Öğrencinin adı Meyra. Onunla arkadaşça ve sen diliyle konuş (Örn: 'Harikasın Meyra!'). Meyra '{kart['korece']}' gramerini kullanarak şu cümleyi kurdu: '{kullanici_cumlesi}'. Cümle doğru mu? Hata varsa doğrudan Meyra'ya hitap ederek düzelt."
                        cevap = model.generate_content(geribildirim_komutu)
                        st.session_state.gramer_feedback = cevap.text
            
            if st.session_state.gramer_feedback:
                st.success("📝 **Öğretmenin Geri Bildirimi:**")
                st.write(st.session_state.gramer_feedback)
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("❌ Tekrar Çalışmalıyım", use_container_width=True):
                        islem_karti = st.session_state.kelimeler.pop(0)
                        st.session_state.kelimeler.append(islem_karti)
                        st.session_state.gecmis.append({'kelime': islem_karti, 'islem': 'gramer_tekrar'})
                        st.session_state.gramer_feedback = None
                        st.rerun()
                with col2:
                    if st.button("✅ Tamamen Anladım", use_container_width=True):
                        islem_karti = st.session_state.kelimeler.pop(0)
                        st.session_state.calisilmis.append(islem_karti)
                        st.session_state.gecmis.append({'kelime': islem_karti, 'islem': '
