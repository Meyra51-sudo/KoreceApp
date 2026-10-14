import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import random
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# --- AYARLAR VE API BAĞLANTILARI ---
GOOGLE_API_KEY = st.secrets["API_KEY"]
SHEET_URL = st.secrets["SHEET_URL"]
GCP_JSON = json.loads(st.secrets["GCP_JSON"])

genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-3-flash-preview', generation_config={"temperature": 0.0})

# Google Sheets Bağlantısı
scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(GCP_JSON, scopes=scopes)
gc = gspread.authorize(creds)
sheet = gc.open_by_url(SHEET_URL).sheet1

st.set_page_config(page_title="MEYRA", layout="centered")

# --- VERİTABANI SENKRONİZASYON FONKSİYONU ---
def veritabani_guncelle():
    tum_veriler = st.session_state.kelimeler + st.session_state.calisilmis
    if tum_veriler:
        df = pd.DataFrame(tum_veriler)
        sheet.clear()
        sheet.update([df.columns.values.tolist()] + df.values.tolist())

# --- UYGULAMA HAFIZASI VE ANKI ALTYAPISI ---
if 'veri_yuklendi' not in st.session_state:
    st.session_state.kelimeler = []
    st.session_state.calisilmis = []
    st.session_state.gecmis = []
    st.session_state.kart_arkasi = False
    st.session_state.gramer_feedback = None
    st.session_state.zor_pratik_modu = False
    st.session_state.secilen_gramer = ""
    st.session_state.gunluk_mesaj = random.choice([
        "오늘 너무 예뻐요!", "포기하지 마세요!", "오늘도 화이팅!", "한국어 천재 메이라!", "할 수 있어요!"
    ])
    
    # Sheets'ten Veri Çekme ve Tarihe Göre Ayırma (Anki Algoritması)
    kayitlar = sheet.get_all_records()
    bugun = datetime.now().date()
    
    for satir in kayitlar:
        try:
            tekrar_tarihi = datetime.strptime(str(satir.get('next_review', bugun)), "%Y-%m-%d").date()
        except:
            tekrar_tarihi = bugun
            satir['next_review'] = str(bugun)
            
        if tekrar_tarihi <= bugun:
            st.session_state.kelimeler.append(satir)
        else:
            st.session_state.calisilmis.append(satir)
            
    random.shuffle(st.session_state.kelimeler)
    st.session_state.veri_yuklendi = True

topik_4_gramerler = ["-아/어 보이다", "-(으)ㄹ 뿐만 아니라", "-(으)ㄴ/는 데다가", "-기 마련이다", "-(으)ㄴ/는 척하다", "-(으)ㄹ 뻔하다", "-느라고"]

# --- ARAYÜZ (SEKMELER) ---
tab1, tab2, tab3 = st.tabs(["📂 1. Yükle", "🧠 2. Çalışma Modu", "⚙️ 3. Düzenle"])

with tab1:
    st.markdown("<h2 style='text-align: center;'>Hoşgeldin 메이라</h2>", unsafe_allow_html=True)
    st.markdown(f"<h4 style='text-align: center; color: #2e7bcf;'>{st.session_state.gunluk_mesaj}</h4>", unsafe_allow_html=True)
    st.markdown("---")
    
    gorsel = st.file_uploader("Fotoğraf Çek veya Yükle", type=["jpg", "jpeg", "png"])
    
    if gorsel is not None:
        if st.button("Analiz Et ve Desteye Ekle"):
            with st.spinner("Öğretmen Meyra için notları analiz ediyor..."):
                try:
                    gorsel_verisi = [{"mime_type": "image/jpeg", "data": gorsel.getvalue()}]
                    komut = """
GÖREVİN: KATI BİR VERİ ÇIKARICISI OLMAKTIR. 
Görseldeki Korece kelimeleri, el yazısı notları ve dilbilgisi kurallarını çıkar.

KURALLAR (MEYRA'NIN NOT ALMA STİLİ):
1. ALTI ÇİZİLİ KELİMELER: Unutulan kelimelerdir. KESİNLİKLE LİSTEYE EKLE.
2. ZIT ANLAMLILAR (X İŞARETİ): "가다 x 오다" gibi arasına 'x' veya 'X' koyulmuş kelimeler zıt anlamlıdır. "tr" kısmına "Anlamı (Zıt Anlamlısı: [Diğer Kelime])" yaz.
3. GRAMER KURALLARI: Yeni dilbilgisi kalıplarını çıkar ve "tip" değerini "gramer" yap.
4. KELİMELER: Gramer dışındakilerin "tip" değerini "kelime" yap. Sadece TOPIK 4+ kelimeleri al. Eşanlamlıları virgülle tek satırda birleştir.
5. ÖRNEK CÜMLELER (PASİF ÖĞRENME): 
   A) Özneler HER ZAMAN ünlü kişiler veya tarihi karakterler olmalı (Örn: 아인슈타인, 마이클 잭슨).
   B) Cümlelerde Korece sayma kelimeleri (개, 명, 마리 등) ve rakamlar bulunmalı.
6. JSON formatı:
[{"tip": "kelime/gramer", "korece": "hedef metin", "tr": "Türkçe", "en": "İngilizce", "ornek_ko": "Örnek cümle", "ornek_tr": "Çevirisi", "is_hard": false, "hard_streak": 0, "interval": 1, "ease": 2.5, "next_review": ""}]
"""
                    cevap = model.generate_content([komut, gorsel_verisi[0]])
                    json_metni = cevap.text.strip().replace("```json", "").replace("```", "")
                    veriler = json.loads(json_metni)
                    
                    mevcut_korece = {k['korece'] for k in st.session_state.kelimeler + st.session_state.calisilmis}
                    yeni_maddeler = []
                    
                    bugun = str(datetime.now().date())
                    for k in veriler:
                        if k['korece'] not in mevcut_korece:
                            k['next_review'] = bugun # Yeni kelimeler hemen çalışılacak
                            yeni_maddeler.append(k)
                    
                    st.session_state.kelimeler.extend(yeni_maddeler)
                    veritabani_guncelle() # Sayfa yüklenince Sheets'e kaydet
                    
                    random.shuffle(st.session_state.kelimeler)
                    st.success(f"{len(yeni_maddeler)} yeni madde desteye eklendi ve buluta kaydedildi!")
                    
                except Exception as e:
                    st.error(f"Hata: {e}")

with tab2:
    zor_kelime_sayisi = sum(1 for k in (st.session_state.kelimeler + st.session_state.calisilmis) if k.get('is_hard', False))
    toplam_ogrenilen = len(st.session_state.calisilmis)
    tekrar_bekleyen = len(st.session_state.kelimeler)
    
    colA, colB, colC = st.columns(3)
    colA.metric("📚 Öğrenilen (Bugünlük)", toplam_ogrenilen)
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
            veritabani_guncelle() # Geri alınca da kaydet
            st.rerun()

    if len(st.session_state.kelimeler) == 0:
        if len(st.session_state.calisilmis) == 0:
            st.info("Destede madde yok. Lütfen kitap yükleyin.")
        else:
            st.success("Harikasın 메이라! Bugünlük desteyi bitirdin. Aralıklı tekrar algoritmasına göre vakti gelmeyen kelimeler seni bekletiyor.")
            if st.button("Erkenden Baştan Karıştır (Pratik)"):
                st.session_state.kelimeler = st.session_state.calisilmis.copy()
                st.session_state.calisilmis = []
                random.shuffle(st.session_state.kelimeler)
                st.session_state.kart_arkasi = False
                st.rerun()
    else:
        kart = st.session_state.kelimeler[0]
        bugun_tarihi = datetime.now().date()
        
        if st.session_state.zor_pratik_modu:
            st.markdown(f"<h2 style='text-align: center; color: #ff8c00;'>🔥 Zor Kelime Pratiği</h2>", unsafe_allow_html=True)
            st.markdown(f"<h1 style='text-align: center;'>{kart['korece']}</h1>", unsafe_allow_html=True)
            st.info(f"**메이라, bu kelimeyi kullanarak bir cümle kur.**\n\n📌 **Görev:** Cümleyi kurarken **{st.session_state.secilen_gramer}** gramer kuralını da kullanmaya çalış!")
            
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
                        veritabani_guncelle()
                        st.rerun()

        elif kart.get('tip') == 'gramer':
            st.markdown(f"<h1 style='text-align: center; color: #ff4b4b; margin-top: 20px;'>{kart['korece']}</h1>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; font-weight: bold; color: gray;'>[Gramer / Dilbilgisi]</p>", unsafe_allow_html=True)
            st.info(f"**Anlamı:** {kart['tr']}\n\n**Örnek:** {kart['ornek_ko']} ({kart['ornek_tr']})")
            
            kullanici_cumlesi = st.text_input("Bu grameri kullanarak kendi Korece cümleni kur 메이라:")
            
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
                        kart['ease'] = max(1.3, kart.get('ease', 2.5) - 0.2)
                        kart['interval'] = 1
                        kart['next_review'] = str(bugun_tarihi)
                        islem_karti = st.session_state.kelimeler.pop(0)
                        st.session_state.kelimeler.append(islem_karti)
                        st.session_state.gecmis.append({'kelime': islem_karti, 'islem': 'gramer_tekrar'})
                        st.session_state.gramer_feedback = None
                        veritabani_guncelle()
                        st.rerun()
                with col2:
                    if st.button("✅ Tamamen Anladım", use_container_width=True):
                        kart['ease'] = kart.get('ease', 2.5) + 0.1
                        kart['interval'] = max(1, int(kart.get('interval', 1) * kart['ease']))
                        kart['next_review'] = str(bugun_tarihi + timedelta(days=kart['interval']))
                        islem_karti = st.session_state.kelimeler.pop(0)
                        st.session_state.calisilmis.append(islem_karti)
                        st.session_state.gecmis.append({'kelime': islem_karti, 'islem': 'bildim'})
                        st.session_state.gramer_feedback = None
                        veritabani_guncelle()
                        st.rerun()

        else:
            if kart.get('is_hard', False) and kart.get('hard_streak', 0) >= 3:
                st.warning(f"🎉 메이라, **{kart['korece']}** kelimesinde 3 pratik görevini başarıyla tamamladın! Bu kelimeyi 'Zor' etiketinden çıkaralım mı?")
                colX, colY = st.columns(2)
                with colX:
                    if st.button("Evet, Öğrendim"):
                        kart['is_hard'] = False
                        kart['hard_streak'] = 0
                        kart['next_review'] = str(bugun_tarihi + timedelta(days=3)) # 3 gün sonraya at
                        islem_karti = st.session_state.kelimeler.pop(0)
                        st.session_state.calisilmis.append(islem_karti)
                        veritabani_guncelle()
                        st.rerun()
                with colY:
                    if st.button("Hayır, Zor Kalsın"):
                        kart['hard_streak'] = 0
                        islem_karti = st.session_state.kelimeler.pop(0)
                        st.session_state.kelimeler.append(islem_karti)
                        veritabani_guncelle()
                        st.rerun()
            else:
                if kart.get('is_hard', False):
                    st.markdown("<p style='text-align: center; color: #ff8c00; font-weight: bold;'>🔥 Zor Kelime</p>", unsafe_allow_html=True)
                
                st.markdown(f"<h1 style='text-align: center; font-size: 3em; color: #2e7bcf; margin-top: 10px;'>{kart['korece']}</h1>", unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
                
                if not st.session_state.kart_arkasi:
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button("❌ Bilemedim", use_container_width=True):
                            kart['ease'] = max(1.3, kart.get('ease', 2.5) - 0.2)
                            kart['interval'] = 1
                            kart['next_review'] = str(bugun_tarihi)
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
                            kart['interval'] = max(1, int(kart.get('interval', 1) * kart['ease']))
                            kart['next_review'] = str(bugun_tarihi + timedelta(days=kart['interval']))
                            islem_karti = st.session_state.kelimeler.pop(0)
                            st.session_state.calisilmis.append(islem_karti)
                            st.session_state.gecmis.append({'kelime': islem_karti, 'islem': 'bildim'})
                            st.session_state.kart_arkasi = False
                            veritabani_guncelle()
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
                        veritabani_guncelle()
                        st.rerun()

with tab3:
    st.subheader("Veritabanını Düzenle")
    
    tum_veriler = st.session_state.kelimeler + st.session_state.calisilmis
    if len(tum_veriler) == 0:
        st.info("Şu an veritabanında kelime yok.")
    else:
        df = pd.DataFrame(tum_veriler)
        duzenlenmis_df = st.data_editor(df, num_rows="dynamic", use_container_width=True, hide_index=True)
        if st.button("Değişiklikleri Google Sheets'e Kaydet", type="primary"):
            veriler_dict = duzenlenmis_df.to_dict('records')
            
            # Kelimeler ve çalışılmış olarak tekrar ayır
            yeni_kelimeler = []
            yeni_calisilmis = []
            bugun = datetime.now().date()
            for satir in veriler_dict:
                try:
                    rev_date = datetime.strptime(str(satir.get('next_review', bugun)), "%Y-%m-%d").date()
                except:
                    rev_date = bugun
                
                if rev_date <= bugun:
                    yeni_kelimeler.append(satir)
                else:
                    yeni_calisilmis.append(satir)
                    
            st.session_state.kelimeler = yeni_kelimeler
            st.session_state.calisilmis = yeni_calisilmis
            veritabani_guncelle()
            st.success("Tüm değişiklikler başarıyla Google Sheets'e kaydedildi!")
