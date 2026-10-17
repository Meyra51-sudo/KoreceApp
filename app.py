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
    try:
        # Otomatik aramayı tamamen iptal ettik, DİREKT 3.8'e bağlanıyor
        model = genai.GenerativeModel('gemini-3.8-flash', generation_config={"temperature": 0.0})
        if gorsel_verisi:
            cevap = model.generate_content([komut, gorsel_verisi])
        else:
            cevap = model.generate_content(komut)
        return cevap.text
    except Exception as e:
        hata_mesaji = str(e).lower()
        if "429" in hata_mesaji or "quota" in hata_mesaji:
            raise Exception("Google API günlük ücretsiz 20 işlem limitin doldu. Lütfen yarın Kore saatiyle 16:00'dan sonra tekrar dene veya cümle pratiğini 'Geç' butonlarıyla atla.")
        elif "404" in hata_mesaji:
            raise Exception("API Key bu modele erişemiyor. Google AI Studio üzerinden 'gemini-3.8-flash' erişimini kontrol et.")
        else:
            raise Exception(f"Beklenmeyen API Hatası: {e}")

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

# --- MOTİVASYON HAVUZU ---
motivasyon_cumleleri = [
    "오늘 너무 예뻐요!", "포기하지 마세요!", "오늘도 화이팅!", "한국어 천재 메이라!", "할 수 있어요!",
    "작은 진전이 큰 결과를 만듭니다.", "매일 조금씩 발전하고 있어요.", "꿈을 향해 멈추지 말고 달려가세요.",
    "당신의 노력은 절대 배신하지 않습니다.", "오늘의 땀방울이 내일의 빛이 됩니다.", "실수는 배움의 과정일 뿐입니다.",
    "포기하고 싶을 때가 바로 성공에 가까워진 때입니다.", "천 리 길도 한 걸음부터.", "자신을 믿으세요, 메이라!",
    "오늘 최선을 다했다면 그것으로 충분합니다.", "당신은 생각보다 훨씬 더 강합니다.", "배움에는 끝이 없습니다.",
    "매일매일 성장하는 당신이 멋지다.", "어제보다 나은 오늘을 만들어봐요.", "지금 흘린 땀은 헛되지 않아요."
]

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
    st.session_state.gunluk_mesaj = random.choice(motivasyon_cumleleri)
    
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
GÖREVİN: KATI BİR VERİ ÇIKARICISI OLMAKTIR. Görseldeki kelimeleri ve gramerleri çıkar.
KURALLAR:
1. ÖZEL NOTLAR VE ALTI ÇİZİLİLER (MUTLAK KURAL): Görselde altı çizilmiş olan veya el yazısıyla/madde işaretiyle not alınmış kelimeler KESİNLİKLE (TOPIK seviyesine bakılmaksızın) eklenecektir. Bu kural diğer tüm filtrelerden üstündür.
2. ZIT / EŞ ANLAMLILAR: '=' eşanlamlı, 'x' veya '^' zıt anlamlıdır. Kök kelimenin yanına parantez içinde ekle.
3. GRAMER: Başına tire (-) koy ve "tip" değerini "gramer" yap.
4. ÇOK ANLAMLI GRAMER/KELİME: Eğer bir gramerin veya kelimenin birden fazla farklı kullanımı/anlamı verilmişse, bunları KESİNLİKLE ayrı maddeler olarak çıkar ve Korece metnin sonuna numara ekle (Örn: "-은/는 데다가 (1)").
5. GENEL KELİMELER: Altı çizili veya el yazısı not OLMAYAN genel metin kelimelerinden SADECE TOPIK 4 ve üzeri olanları al. Basit kelimeleri ele.
6. ÖRNEK CÜMLELER: Kitaptaki orijinal cümleyi al. Yoksa ünlü özneli ve sayma kelimeli cümle üret.
7. JSON formatı: [{"tip": "kelime/gramer", "korece": "metin", "tr": "Türkçe", "en": "İngilizce", "ornek_ko": "Örnek cümle", "ornek_tr": "Çeviri"}]
"""

                    json_metni = ai_cevap_al(komut, gorsel_verisi)
                    json_metni = json_metni.strip().replace("```json", "").replace("```", "")
                    veriler = json.loads(json_metni)
                    
                    # Çift kelime kontrolünü kusursuzlaştırmak için temizleme fonksiyonu (boşluk ve tireleri görmezden gelir)
                    def normalize_key(text):
                        return ''.join(c.lower() for c in text.split('=')[0].split('^')[0].split('x')[0] if c.isalnum() or c in '()123456789')
                    
                    mevcut_korece_dict = {normalize_key(k['korece']): k for k in st.session_state.kelimeler + st.session_state.calisilmis}
                    
                    yeni_maddeler = []
                    eklenen_isimler = []
                    guncellenen_isimler = []
                    bugun = str(datetime.now().date())
                    
                    for k in veriler:
                        ana_kelime_key = normalize_key(k['korece'])
                        
                        if ana_kelime_key in mevcut_korece_dict:
                            eski_kart = mevcut_korece_dict[ana_kelime_key]
                            # Güncelleme: Yeni gelenin Korecesi veya Türkçesi eskisinden uzunsa (örn: eşanlamlı eklenmişse)
                            if len(k['korece']) > len(eski_kart['korece']) or len(k['tr']) > len(eski_kart['tr']):
                                eski_kart['korece'] = k['korece']
                                eski_kart['tr'] = k['tr']
                                eski_kart['is_hard'] = False
                                eski_kart['hard_streak'] = 0
                                eski_kart['interval'] = 1 # İstatistik sıfırlandı
                                eski_kart['ease'] = 2.5
                                eski_kart['next_review'] = bugun
                                guncellenen_isimler.append(k['korece'])
                        else:
                            # Tamamen yeni kelime
                            k['is_hard'] = False 
                            k['hard_streak'] = 0
                            k['interval'] = 1 
                            k['ease'] = 2.5
                            k['next_review'] = bugun
                            yeni_maddeler.append(k)
                            mevcut_korece_dict[ana_kelime_key] = k
                            eklenen_isimler.append(k['korece'])
                    
                    if yeni_maddeler or guncellenen_isimler:
                        st.session_state.kelimeler.extend(yeni_maddeler)
                        veritabani_guncelle()
                        random.shuffle(st.session_state.kelimeler)
                        
                        mesaj = f"✅ Analiz tamamlandı! **{len(eklenen_isimler)}** yeni madde eklendi, **{len(guncellenen_isimler)}** madde güncellendi.\n\n"
                        if eklenen_isimler:
                            mesaj += f"✨ **Yeni Eklenenler:** {', '.join(eklenen_isimler)}\n"
                        if guncellenen_isimler:
                            mesaj += f"🔄 **Not Eklenerek Güncellenenler:** {', '.join(guncellenen_isimler)}"
                        st.success(mesaj)
                    else:
                        st.info("Bu sayfadaki tüm kelimeler/gramerler zaten veritabanında en güncel haliyle mevcut. Yeni bir şey eklenmedi.")
                    
                except Exception as e:
                    st.error(str(e))

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
            col_z1, col_z2 = st.columns(2)
            with col_z1:
                if st.button("Öğretmene Gönder (AI)", use_container_width=True):
                    if kullanici_cumlesi:
                        with st.spinner("Öğretmen cümleni okuyor..."):
                            try:
                                geribildirim_komutu = f"Adın AI Öğretmen. Karşındaki Meyra. Meyra '{kart['korece']}' kelimesini ve '{st.session_state.secilen_gramer}' gramerini kullanarak şu cümleyi kurdu: '{kullanici_cumlesi}'. Cümle doğru mu? Hata varsa doğrudan ona açıkla."
                                cevap_metni = ai_cevap_al(geribildirim_komutu)
                                st.session_state.gramer_feedback = cevap_metni
                            except Exception as e:
                                st.error(str(e))
            with col_z2:
                if st.button("⏭️ Cümle Kurmadan Geç", use_container_width=True):
                    kart['hard_streak'] = int(kart.get('hard_streak', 0)) + 1
                    if kart['hard_streak'] >= 3:
                        st.session_state.zor_pratik_modu = False
                        st.session_state.gramer_feedback = None
                        st.rerun()
                    else:
                        islem_karti = st.session_state.kelimeler.pop(0)
                        hedef_indeks = min(len(st.session_state.kelimeler), random.randint(3, 6))
                        st.session_state.kelimeler.insert(hedef_indeks, islem_karti)
                        st.session_state.gecmis.append({'kelime': islem_karti, 'islem': 'zor'})
                        st.session_state.zor_pratik_modu = False
                        st.session_state.gramer_feedback = None
                        st.session_state.kart_arkasi = False
                        veritabani_guncelle()
                        st.rerun()
            
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
                        hedef_indeks = min(len(st.session_state.kelimeler), random.randint(3, 6))
                        st.session_state.kelimeler.insert(hedef_indeks, islem_karti)
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
            if st.button("Cümlemi Kontrol Et (AI)", use_container_width=True):
                if kullanici_cumlesi:
                    with st.spinner("Öğretmen cümleni inceliyor..."):
                        try:
                            geribildirim_komutu = f"Adın AI Öğretmen. Karşındaki Meyra. Meyra '{kart['korece']}' gramerini kullanarak şu cümleyi kurdu: '{kullanici_cumlesi}'. Doğru mu? Hata varsa doğrudan Meyra'ya hitap ederek düzelt."
                            cevap_metni = ai_cevap_al(geribildirim_komutu)
                            st.session_state.gramer_feedback = cevap_metni
                        except Exception as e:
                            st.error(str(e))
            
            if st.session_state.gramer_feedback:
                st.success("📝 **Öğretmenin Geri Bildirimi:**")
                st.write(st.session_state.gramer_feedback)
                
            st.markdown("---")
            st.markdown("<p style='text-align: center; color: gray; font-size: 14px;'>Değerlendirme (Cümle kurmadan doğrudan geçebilirsin):</p>", unsafe_allow_html=True)
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
