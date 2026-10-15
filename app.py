import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import random
import gspread
import io
import asyncio
import base64
import edge_tts
import re
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# --- AYARLAR VE API BAĞLANTILARI ---
GOOGLE_API_KEY = st.secrets["API_KEY"]
SHEET_URL = st.secrets["SHEET_URL"]
GCP_JSON = json.loads(st.secrets["GCP_JSON"])

genai.configure(api_key=GOOGLE_API_KEY)

scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(GCP_JSON, scopes=scopes)
gc = gspread.authorize(creds)
sheet = gc.open_by_url(SHEET_URL).sheet1

st.set_page_config(page_title="MEYRA", layout="centered")

# --- YARDIMCI FONKSİYONLAR ---

def ai_cevap_al(komut, gorsel_verisi=None):
    # Google'ın o an aktif olan herhangi bir flash modelini otomatik bulur, 404 hatasını önler
    aktif_model = None
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods and 'flash' in m.name:
            aktif_model = m.name
            break
    if not aktif_model:
        aktif_model = 'gemini-1.5-flash'
        
    model = genai.GenerativeModel(aktif_model, generation_config={"temperature": 0.0})
    if gorsel_verisi:
        cevap = model.generate_content([komut, gorsel_verisi])
    else:
        cevap = model.generate_content(komut)
    return cevap.text

def veritabani_guncelle():
    tum_veriler = st.session_state.kelimeler + st.session_state.calisilmis
    if tum_veriler:
        df = pd.DataFrame(tum_veriler)
        sheet.clear()
        sheet.update([df.columns.values.tolist()] + df.values.tolist())

def kelime_zor_mu(kart):
    deger = kart.get('is_hard', False)
    if isinstance(deger, bool):
        return deger
    return str(deger).strip().lower() in ['true', '1', 't', 'y', 'yes']

def temiz_karsilastir(m1, m2):
    def temizle(metin):
        return ''.join(char for char in str(metin) if char.isalnum())
    return temizle(m1) == temizle(m2)

@st.cache_data(show_spinner=False)
def ses_olustur(metin):
    async def _amain():
        communicate = edge_tts.Communicate(metin, "ko-KR-SunHiNeural")
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        return audio_data
    return asyncio.run(_amain())

# --- UYGULAMA HAFIZASI ---
if 'veri_yuklendi' not in st.session_state:
    st.session_state.kelimeler = []
    st.session_state.calisilmis = []
    st.session_state.gecmis = []
    st.session_state.kart_arkasi = False
    st.session_state.arkayuz_modu = 'bilemedim' 
    st.session_state.gramer_feedback = None
    st.session_state.zor_pratik_modu = False
    st.session_state.secilen_gramer = ""
    st.session_state.yazma_karti = None
    st.session_state.yazma_id = random.randint(10000, 99999)
    st.session_state.gunluk_mesaj = random.choice([
        "오늘 너무 예뻐요!", "포기하지 마세요!", "오늘도 화이팅!", "한국어 천재 메이라!", "할 수 있어요!"
    ])
    
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

# --- ARAYÜZ ---
tab1, tab2, tab3, tab4 = st.tabs(["📂 1. Yükle", "🧠 2. Çalışma Modu", "⚙️ 3. Düzenle", "✍️ 4. Yazma Modu"])

with tab1:
    st.markdown("<h2 style='text-align: center;'>반가워 메이라</h2>", unsafe_allow_html=True)
    st.markdown(f"<h4 style='text-align: center; color: #2e7bcf;'>{st.session_state.gunluk_mesaj}</h4>", unsafe_allow_html=True)
    st.markdown("---")
    
    gorsel = st.file_uploader("Fotoğraf Çek veya Galeriden Seç", type=["jpg", "jpeg", "png"])
    
    if gorsel is not None:
        if st.button("Analiz Et ve Desteye Ekle"):
            with st.spinner("Öğretmen sayfayı analiz ediyor..."):
                try:
                    gorsel_verisi = {"mime_type": "image/jpeg", "data": gorsel.getvalue()}
                    komut = """
GÖREVİN: KATI BİR VERİ ÇIKARICISI OLMAKTIR. Görseldeki Korece kelimeleri ve gramerleri çıkar.
KURALLAR:
1. ALTI ÇİZİLİ KELİMELER: Unutulan kelimelerdir. KESİNLİKLE EKLE.
2. ZIT ANLAMLILAR: "가다 x 오다" gibi arasına 'x' koyulmuş kelimeler zıt anlamlıdır. "tr" kısmına "Anlamı (Zıt Anlamlısı: [Diğer Kelime])" yaz.
3. GRAMER: Başına tire (-) koyarak "tip" değerini "gramer" yap.
4. KELİMELER: "tip" değerini "kelime" yap. Sadece TOPIK 4+ al.
5. ÖRNEK CÜMLELER: Kitaptaki orijinal cümleyi al. Yoksa ünlü özneli ve sayma kelimeli cümle üret.
6. JSON formatı: [{"tip": "kelime/gramer", "korece": "metin", "tr": "Türkçe", "en": "İngilizce", "ornek_ko": "Örnek cümle", "ornek_tr": "Çeviri"}]
"""
                    json_metni = ai_cevap_al(komut, gorsel_verisi)
                    json_metni = json_metni.strip().replace("```json", "").replace("```", "")
                    veriler = json.loads(json_metni)
                    
                    mevcut_korece = {k['korece'].strip() for k in st.session_state.kelimeler + st.session_state.calisilmis}
                    yeni_maddeler = []
                    bugun = str(datetime.now().date())
                    
                    for k in veriler:
                        korece_temiz = k['korece'].strip()
                        if korece_temiz not in mevcut_korece:
                            k['korece'] = korece_temiz
                            k['is_hard'] = False 
                            k['hard_streak'] = 0
                            k['interval'] = 1
                            k['ease'] = 2.5
                            k['next_review'] = bugun
                            yeni_maddeler.append(k)
                            mevcut_korece.add(korece_temiz)
                    
                    st.session_state.kelimeler.extend(yeni_maddeler)
                    veritabani_guncelle()
                    random.shuffle(st.session_state.kelimeler)
                    st.success(f"Analiz tamamlandı! Toplam {len(yeni_maddeler)} yeni madde başarıyla eklendi.")
                    
                except Exception as e:
                    st.error(f"Hata Oluştu: {e}")

with tab2:
    zor_kelime_sayisi = sum(1 for k in (st.session_state.kelimeler + st.session_state.calisilmis) if kelime_zor_mu(k))
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
                st.session_state.calisilmis.pop() 
                st.session_state.kelimeler.insert(0, son_islem['kelime'])
            elif son_islem['islem'] in ['bilemedim', 'zor', 'gramer_tekrar']:
                st.session_state.kelimeler.pop() 
                st.session_state.kelimeler.insert(0, son_islem['kelime'])
            st.session_state.kart_arkasi = False
            veritabani_guncelle()
            st.rerun()

    if len(st.session_state.kelimeler) == 0:
        if len(st.session_state.calisilmis) == 0:
            st.info("Destede madde yok. Lütfen kitap yükleyin.")
        else:
            st.success("Harikasın 메이라! Bugünlük desteyi bitirdin.")
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
                        try:
                            geribildirim_komutu = f"Adın AI Öğretmen. Karşındaki Meyra. Meyra '{kart['korece']}' kelimesini ve '{st.session_state.secilen_gramer}' gramerini kullanarak şu cümleyi kurdu: '{kullanici_cumlesi}'. Cümle doğru mu? Hata varsa doğrudan ona açıkla."
                            cevap_metni = ai_cevap_al(geribildirim_komutu)
                            st.session_state.gramer_feedback = cevap_metni
                        except Exception as e:
                            st.error(f"Bağlantı hatası: {e}")
            
            if st.session_state.gramer_feedback:
                st.success("👩‍🏫 **Öğretmenin Geri Bildirimi:**")
                st.write(st.session_state.gramer_feedback)
                if st.button("Devam Et", use_container_width=True):
                    kart['hard_streak'] = int(kart.get('hard_streak', 0)) + 1
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
            ses_bytes = ses_olustur(kart['korece'])
            st.audio(ses_bytes, format="audio/mp3")
            st.markdown("<p style='text-align: center; font-weight: bold; color: gray;'>[Gramer / Dilbilgisi]</p>", unsafe_allow_html=True)
            st.info(f"**Anlamı:** {kart['tr']}\n\n**Örnek:** {kart['ornek_ko']} ({kart['ornek_tr']})")
            
            kullanici_cumlesi = st.text_input("Bu grameri kullanarak kendi Korece cümleni kur 메이라:")
            if st.button("Cümlemi Kontrol Et", use_container_width=True):
                if kullanici_cumlesi:
                    with st.spinner("Öğretmen cümleni inceliyor..."):
                        try:
                            geribildirim_komutu = f"Adın AI Öğretmen. Karşındaki Meyra. Meyra '{kart['korece']}' gramerini kullanarak şu cümleyi kurdu: '{kullanici_cumlesi}'. Doğru mu? Hata varsa doğrudan Meyra'ya hitap ederek düzelt."
                            cevap_metni = ai_cevap_al(geribildirim_komutu)
                            st.session_state.gramer_feedback = cevap_metni
                        except Exception as e:
                            st.error(f"Bağlantı hatası: {e}")
            
            if st.session_state.gramer_feedback:
                st.success("📝 **Öğretmenin Geri Bildirimi:**")
                st.write(st.session_state.gramer_feedback)
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("❌ Tekrar Çalışmalıyım", use_container_width=True):
                        kart['ease'] = max(1.3, float(kart.get('ease', 2.5)) - 0.2)
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
                        kart['ease'] = float(kart.get('ease', 2.5)) + 0.1
                        kart['interval'] = max(1, int(float(kart.get('interval', 1)) * kart['ease']))
                        kart['next_review'] = str(bugun_tarihi + timedelta(days=kart['interval']))
                        islem_karti = st.session_state.kelimeler.pop(0)
                        st.session_state.calisilmis.append(islem_karti)
                        st.session_state.gecmis.append({'kelime': islem_karti, 'islem': 'bildim'})
                        st.session_state.gramer_feedback = None
                        veritabani_guncelle()
                        st.rerun()

        else:
            if kelime_zor_mu(kart) and int(kart.get('hard_streak', 0)) >= 3:
                st.warning(f"🎉 메이라, **{kart['korece']}** kelimesinde 3 pratik görevini başarıyla tamamladın! Bu kelimeyi 'Zor' etiketinden çıkaralım mı?")
                colX, colY = st.columns(2)
                with colX:
                    if st.button("Evet, Öğrendim"):
                        kart['is_hard'] = False
                        kart['hard_streak'] = 0
                        kart['next_review'] = str(bugun_tarihi + timedelta(days=3))
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
                if kelime_zor_mu(kart):
                    st.markdown("<p style='text-align: center; color: #ff8c00; font-weight: bold;'>🔥 Zor Kelime</p>", unsafe_allow_html=True)
                
                st.markdown(f"<h1 style='text-align: center; font-size: 3em; color: #2e7bcf; margin-top: 10px;'>{kart['korece']}</h1>", unsafe_allow_html=True)
                ses_bytes = ses_olustur(kart['korece'])
                st.audio(ses_bytes, format="audio/mp3")
                
                if not st.session_state.kart_arkasi:
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        if st.button("❌ Bilemedim"):
                            kart['ease'] = max(1.3, float(kart.get('ease', 2.5)) - 0.2)
                            kart['interval'] = 1
                            kart['next_review'] = str(bugun_tarihi)
                            st.session_state.kart_arkasi = True
                            st.session_state.arkayuz_modu = 'bilemedim'
                            st.rerun()
                    with col2:
                        if st.button("👀 Anlamı Gör"):
                            st.session_state.kart_arkasi = True
                            st.session_state.arkayuz_modu = 'emin_degilim'
                            st.rerun()
                    with col3:
                        if st.button("⚠️ Zor"):
                            kart['is_hard'] = True
                            st.session_state.secilen_gramer = random.choice(topik_4_gramerler)
                            st.session_state.zor_pratik_modu = True
                            st.rerun()
                    with col4:
                        if st.button("✅ Bildim"):
                            kart['ease'] = float(kart.get('ease', 2.5)) + 0.1
                            kart['interval'] = max(1, int(float(kart.get('interval', 1)) * kart['ease']))
                            kart['next_review'] = str(bugun_tarihi + timedelta(days=kart['interval']))
                            islem_karti = st.session_state.kelimeler.pop(0)
                            st.session_state.calisilmis.append(islem_karti)
                            st.session_state.gecmis.append({'kelime': islem_karti, 'islem': 'bildim'})
                            st.session_state.kart_arkasi = False
                            st.session_state.yazma_id = random.randint(10000, 99999)
                            veritabani_guncelle()
                            st.rerun()
                else:
                    st.markdown(f"<h3 style='text-align: center;'>🇹🇷 {kart['tr']}</h3>", unsafe_allow_html=True)
                    st.markdown(f"<h4 style='text-align: center; color: gray;'>🇬🇧 {kart['en']}</h4>", unsafe_allow_html=True)
                    st.info(f"**Örnek Cümle:** {kart['ornek_ko']} ({kart['ornek_tr']})")
                    ses_bytes_ornek = ses_olustur(kart['ornek_ko'])
                    st.audio(ses_bytes_ornek, format="audio/mp3")
                    
                    if st.session_state.arkayuz_modu == 'emin_degilim':
                        st.markdown("<p style='text-align: center; color: gray;'>Şimdi karar ver: Anlamını doğru tahmin etmiş miydin?</p>", unsafe_allow_html=True)
                        colA, colB = st.columns(2)
                        with colA:
                            if st.button("❌ Hayır, Bilmiyormuşum", use_container_width=True):
                                kart['ease'] = max(1.3, float(kart.get('ease', 2.5)) - 0.2)
                                kart['interval'] = 1
                                kart['next_review'] = str(bugun_tarihi)
                                islem_karti = st.session_state.kelimeler.pop(0)
                                st.session_state.kelimeler.append(islem_karti) 
                                st.session_state.gecmis.append({'kelime': islem_karti, 'islem': 'bilemedim'})
                                st.session_state.kart_arkasi = False
                                st.session_state.yazma_id = random.randint(10000, 99999)
                                veritabani_guncelle()
                                st.rerun()
                        with colB:
                            if st.button("✅ Evet, Biliyordum", use_container_width=True):
                                kart['ease'] = float(kart.get('ease', 2.5)) + 0.1
                                kart['interval'] = max(1, int(float(kart.get('interval', 1)) * kart['ease']))
                                kart['next_review'] = str(bugun_tarihi + timedelta(days=kart['interval']))
                                islem_karti = st.session_state.kelimeler.pop(0)
                                st.session_state.calisilmis.append(islem_karti)
                                st.session_state.gecmis.append({'kelime': islem_karti, 'islem': 'bildim'})
                                st.session_state.kart_arkasi = False
                                st.session_state.yazma_id = random.randint(10000, 99999)
                                veritabani_guncelle()
                                st.rerun()
                    else:
                        if st.button("Destenin Sonuna Ekle ve Devam Et", use_container_width=True):
                            islem_karti = st.session_state.kelimeler.pop(0)
                            st.session_state.kelimeler.append(islem_karti) 
                            st.session_state.gecmis.append({'kelime': islem_karti, 'islem': 'bilemedim'})
                            st.session_state.kart_arkasi = False
                            st.session_state.yazma_id = random.randint(10000, 99999)
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
            st.success("Değişiklikler başarıyla Google Sheets'e kaydedildi!")

with tab4:
    st.header("✍️ Yazma Pratiği (받아쓰기)")
    tum_kelimeler = [k for k in (st.session_state.calisilmis + st.session_state.kelimeler) if k.get('tip') == 'kelime']
    
    dikte_havuzu = [k for k in tum_kelimeler if float(k.get('interval', 1)) < 21]
    
    if len(dikte_havuzu) == 0:
        if len(tum_kelimeler) > 0:
            st.success("🎉 Harika! Tüm kelimeler uzun süreli hafızana yerleşmiş durumda. Şu an dikte yapılacak taze kelime yok.")
        else:
            st.info("Pratik yapacak kelime yok.")
    else:
        if st.session_state.get('yazma_karti') is None or st.session_state.yazma_karti not in dikte_havuzu:
            st.session_state.yazma_karti = random.choice(dikte_havuzu)
            st.session_state.yazma_id = random.randint(10000, 99999)
            
        kart = st.session_state.yazma_karti
        st.info("Aşağıdaki sesi dinle ve duyduğun Korece kelimeyi yaz.")
        
        ses_bytes = ses_olustur(kart['korece'])
        st.audio(ses_bytes, format="audio/mp3", loop=True)
        
        cevap = st.text_input("Duyduğun kelimeyi yaz:", key=f"dikte_input_{st.session_state.yazma_id}")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Kontrol Et", use_container_width=True):
                if temiz_karsilastir(cevap, kart['korece']):
                    st.success("Doğru! Harikasın 메이라!")
                else:
                    st.error(f"Yanlış. Doğrusu: '{kart['korece']}' olmalıydı.")
        with col2:
            if st.button("Başka Kelimeye Geç", use_container_width=True):
                st.session_state.yazma_karti = random.choice(dikte_havuzu)
                st.session_state.yazma_id = random.randint(10000, 99999)
                st.rerun()
