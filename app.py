import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import random
from datetime import datetime, timedelta

# API Ayarı
GOOGLE_API_KEY = st.secrets["API_KEY"]
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-3-flash-preview', generation_config={"temperature": 0.0})

st.set_page_config(page_title="SNU Kelime & Gramer Asistanı", layout="centered")

# Motivasyon Cümleleri (Her girişte değişir)
motivasyonlar = [
    "(오늘 너무 예뻐요!)", # Bugün çok güzelsin
    "(포기하지 마세요!)", # Pes etme
    "(오늘도 화이팅!)", # Bugün de fighting
    "(한국어 천재 메이라!)", # Korece dâhisi Meyra
    "(할 수 있어요!)" # Yapabilirsin
]
gunluk_mesaj = random.choice(motivasyonlar)

st.markdown(f"<h2 style='text-align: center;'>🇰🇷 환영합니다 Meyra! {gunluk_mesaj}</h2>", unsafe_allow_html=True)

# TOPIK 4 Gramer Listesi (Zor kelimelerle pratik için)
topik_4_gramerler = ["-아/어 보이다", "-(으)ㄹ 뿐만 아니라", "-(으)ㄴ/는 데다가", "-기 마련이다", "-(으)ㄴ/는 척하다", "-(으)ㄹ 뻔하다", "-느라고"]

# Uygulama Hafızası ve Anki Altyapısı
if 'kelimeler' not in st.session_state: st.session_state.kelimeler = []
if 'calisilmis' not in st.session_state: st.session_state.calisilmis = []
if 'gecmis' not in st.session_state: st.session_state.gecmis = []
if 'kart_arkasi' not in st.session_state: st.session_state.kart_arkasi = False
if 'gramer_feedback' not in st.session_state: st.session_state.gramer_feedback = None
if 'zor_pratik_modu' not in st.session_state: st.session_state.zor_pratik_modu = False
if 'secilen_gramer' not in st.session_state: st.session_state.secilen_gramer = ""

tab1, tab2, tab3 = st.tabs(["📂 1. Yükle", "🧠 2. Çalışma Modu", "⚙️ 3. Listeyi Düzenle"])

with tab1:
    st.info("Kameranı açmak için 'Browse files' butonuna tıklayabilirsin.")
    gorsel = st.file_uploader("Fotoğraf Çek veya Yükle", type=["jpg", "jpeg", "png"])
    
    if gorsel is not None:
        if st.button("Analiz Et ve Desteye Ekle"):
            with st.spinner("Öğretmen Meyra için matbaa, el yazısı, gramer ve özel notları analiz ediyor..."):
                try:
                    gorsel_verisi = [{"mime_type": "image/jpeg", "data": gorsel.getvalue()}]
                    
                    komut = """
GÖREVİN: KATI BİR VERİ ÇIKARICISI OLMAKTIR. 
Görseldeki Korece kelimeleri, el yazısı notları ve dilbilgisi (gramer) kurallarını çıkar.

KURALLAR (MEYRA'NIN NOT ALMA STİLİ):
1. ALTI ÇİZİLİ KELİMELER: Unutulan kelimelerdir. TOPIK 1-2 seviyesi bile olsa ALTI ÇİZİLİ HER KELİMEYİ LİSTEYE EKLE.
2. ZIT ANLAMLILAR (X İŞARETİ): "가다 x 오다" gibi arasına 'x' veya 'X' koyulmuş kelimeler zıt anlamlıdır. Tek maddede topla. "korece" kısmına ana kelimeyi, "tr" kısmına "Anlamı (Zıt Anlamlısı: [Diğer Kelime])" yaz.
3. GRAMER KURALLARI: Yeni dilbilgisi kalıplarını çıkar ve "tip" değerini "gramer" yap.
4. KELİMELER: Gramer dışındakilerin "tip" değerini "kelime" yap. Sadece TOPIK 4+ kelimeleri al (altı çizililer hariç). Eşanlamlıları virgülle tek satırda birleştir.
5. ÖRNEK CÜMLELER (ÇOK ÖNEMLİ - PASİF ÖĞRENME): "ornek_ko" oluştururken şu İKİ KURALA KESİNLİKLE UY: 
   A) Özneler HER ZAMAN ünlü kişiler, bilim insanları, kurgusal veya tarihi karakterler olmalı (Örn: 아인슈타인, 마이클 잭슨, 백설공주, 도스토옙스키 vb.).
   B) Cümlelerin içinde mutlaka Korece sayma kelimeleri (개, 명, 마리, 권, 병, 잔 vb.) ve rakamlar (Sino/Native) bulunmalı.
6. Sadece JSON formatında çıktı ver:
[{"tip": "kelime/gramer", "korece": "hedef metin", "tr": "Türkçe", "en": "İngilizce", "ornek_ko": "Ünlü özneli ve sayma kelimeli örnek cümle", "ornek_tr": "Çevirisi", "is_hard": false, "hard_streak": 0, "interval": 1, "ease": 2.5}]
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
    # --- DASHBOARD (GÖSTERGE PANELİ) ---
    zor_kelime_sayisi = sum(1 for k in (st.session_state.kelimeler + st.session_state.calisilmis) if k.get('is_hard', False))
    toplam_ogrenilen = len(st.session_state.calisilmis)
    tekrar_bekleyen = len(st.session_state.kelimeler)
    
    colA, colB, colC = st.columns(3)
    colA.metric("📚 Öğrenilen/Biten", toplam_ogrenilen)
    colB.metric("⏳ Bugün Tekrar Edilecek", tekrar_bekleyen)
    colC.metric("🔥 Zor Kelimeler", zor_kelime_sayisi)
    st.markdown("---")

    # --- GERİ AL BUTONU ---
    if len(st.session_state.gecmis) > 0 and not st.session_state.zor_pratik_modu:
        if st.button("↩️ Son İşlemi Geri Al"):
            son_islem = st.session_state.gecmis.pop()
            if son_islem['islem'] == 'bildim':
                st.session_state.calisilmis.remove(son_islem['kelime'])
                st.session_state.kelimeler.insert(0, son_islem['kelime'])
            elif son_islem['islem'] in ['bilemedim', 'zor']:
                st.session_state.kelimeler.pop() 
                st.session_state.kelimeler.insert(0, son_islem['kelime'])
            st.session_state.kart_arkasi = False
            st.rerun()

    if len(st.session_state.kelimeler) == 0:
        if len(st.session_state.calisilmis) == 0:
            st.info("Destede madde yok. Lütfen kitap yükleyin.")
        else:
            st.success("Harikasın Meyra! Bugünlük desteyi bitirdin.")
            if st.button("Öğrenilenleri Baştan Karıştır ve Tekrar Et"):
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
                        geribildirim_komutu = f"""
Senin adın AI Öğretmen. Karşındaki öğrencinin adı Meyra. Onunla samimi, arkadaşça ve GÜNLÜK 'sen' diliyle konuş (Örn: 'Harikasın Meyra!', 'Şurayı biraz düzeltelim Meyra' gibi). KESİNLİKLE üçüncü şahıs (öğrenci/arkadaşın) kelimelerini kullanma. Doğrudan ona hitap et.

Meyra şu kelimeyi pratik ediyor: '{kart['korece']}'
Ekstra kullanması istenen gramer: '{st.session_state.secilen_gramer}'
Meyra'nın kurduğu cümle: '{kullanici_cumlesi}'

Cümle doğru mu? İstenen kelime ve gramer kullanılmış mı? Doğallık veya gramer hatası varsa Meyra'ya doğrudan açıklayarak düzelt.
"""
                        cevap = model.generate_content(geribildirim_komutu)
                        st.session_state.gramer_feedback = cevap.text
            
            if st.session_state.gramer_feedback:
                st.success("👩‍🏫 **Öğretmenin Geri Bildirimi:**")
                st.write(st.session_state.gramer_feedback)
                
                if st.button("Devam Et", use_container_width=True):
                    # Pratik başarılı sayılırsa sayacı artır
                    kart['hard_streak'] = kart.get('hard_streak', 0) + 1
                    
                    if kart['hard_streak'] >= 3:
                        st.session_state.zor_pratik_modu = False
                        st.session_state.gramer_feedback = None
                        st.warning(f"Meyra, '{kart['korece']}' kelimesini 3 kez doğru pratik ettin! Artık 'Zor Kelimeler' listesinden çıkarılsın mı?")
                        # Geçici olarak destenin başında tutup sonraki ekranda soracağız (aşağıdaki kod bloğunda)
                        st.rerun()
                    else:
                        islem_karti = st.session_state.kelimeler.pop(0)
                        st.session_state.kelimeler.append(islem_karti)
                        st.session_state.gecmis.append({'kelime': islem_karti, 'islem': 'zor'})
                        st.session_state.zor_pratik_modu = False
                        st.session_state.gramer_feedback = None
                        st.session_state.kart_arkasi = False
                        st.rerun()

        # EĞER KART BİR GRAMER VEYA KELİMEYSE (NORMAL KART GÖRÜNÜMÜ)
        else:
            # 3 Başarılı pratik sonrası zorluktan çıkma kontrolü
            if kart.get('is_hard', False) and kart.get('hard_streak', 0) >= 3:
                st.warning(f"🎉 Meyra, **{kart['korece']}** kelimesinde 3 pratik görevini başarıyla tamamladın! Bu kelimeyi 'Zor' etiketinden çıkaralım mı?")
                colX, colY = st.columns(2)
                with colX:
                    if st.button("Evet, Öğrendim (Etiketi Kaldır)"):
                        kart['is_hard'] = False
                        kart['hard_streak'] = 0
                        islem_karti = st.session_state.kelimeler.pop(0)
                        st.session_state.calisilmis.append(islem_karti)
                        st.rerun()
                with colY:
                    if st.button("Hayır, Zor Olarak Kalsın"):
                        kart['hard_streak'] = 0 # Sayacı sıfırla
                        islem_karti = st.session_state.kelimeler.pop(0)
                        st.session_state.kelimeler.append(islem_karti)
                        st.rerun()
            else:
                if kart.get('is_hard', False):
                    st.markdown("<p style='text-align: center; color: #ff8c00; font-weight: bold;'>🔥 Zor Kelime</p>", unsafe_allow_html=True)
                
                renk = "#ff4b4b" if kart.get('tip') == 'gramer' else "#2e7bcf"
                baslik = "[Gramer / Dilbilgisi]" if kart.get('tip') == 'gramer' else ""
                
                st.markdown(f"<h1 style='text-align: center; font-size: 3em; color: {renk}; margin-top: 10px;'>{kart['korece']}</h1>", unsafe_allow_html=True)
                if baslik: st.markdown(f"<p style='text-align: center; font-weight: bold; color: gray;'>{baslik}</p>", unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
                
                if not st.session_state.kart_arkasi:
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button("❌ Bilemedim", use_container_width=True):
                            kart['ease'] = max(1.3, kart.get('ease', 2.5) - 0.2)
                            kart['interval'] = 1
                            st.session_state.kart_arkasi = True
                            st.rerun()
                    with col2:
                        if st.button("⚠️ Zor (Pratik Yap)", use_container_width=True):
                            kart['is_hard'] = True
                            st.session_state.secilen_gramer = random.choice(topik_4_gramerler)
                            st.session_state.zor_pratik_modu = True
                            st.rerun()
                    with col3:
                        if st.button("✅ Bildim", use_container_width=True):
                            kart['ease'] = kart.get('ease', 2.5) + 0.1
                            kart['interval'] = int(kart.get('interval', 1) * kart['ease'])
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

with tab3:
    st.subheader("Veritabanını Düzenle")
    st.write("Aşağıdaki tablodan kelimeleri düzenleyebilir veya silebilirsin. İşin bitince kaydet butonuna basmayı unutma.")
    
    if len(st.session_state.kelimeler) == 0:
        st.info("Şu an aktif destede kelime/gramer bulunmuyor.")
    else:
        df = pd.DataFrame(st.session_state.kelimeler)
        duzenlenmis_df = st.data_editor(df, num_rows="dynamic", use_container_width=True, hide_index=True)
        
        if st.button("Değişiklikleri Kaydet", type="primary"):
            st.session_state.kelimeler = duzenlenmis_df.to_dict('records')
            st.success("Tüm düzenlemeler başarıyla kaydedildi!")
