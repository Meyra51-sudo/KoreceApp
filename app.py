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
        # Google'ın zorunlu tuttuğu tek geçerli model
        model = genai.GenerativeModel('gemini-3.8-flash', generation_config={"temperature": 0.0})
        if gorsel_verisi:
            cevap = model.generate_content([komut, gorsel_verisi])
        else:
            cevap = model.generate_content(komut)
        return cevap.text
    except Exception as e:
        hata_mesaji = str(e).lower()
        if "429" in hata_mesaji or "quota" in hata_mesaji:
            raise Exception("Google API günlük ücretsiz 20 işlem limitin doldu. Lütfen yarın tekrar dene veya Google AI Studio'dan farklı bir hesapla yeni bir API Key al.")
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

# --- GENİŞ MOTİVASYON HAVUZU ---
motivasyon_cumleleri = [
    "오늘 너무 예뻐요!", "포기하지 마세요!", "오늘도 화이팅!", "한국어 천재 메이라!", "할 수 있어요!",
    "작은 진전이 큰 결과를 만듭니다.", "매일 조금씩 발전하고 있어요.", "꿈을 향해 멈추지 말고 달려가세요.",
    "당신의 노력은 절대 배신하지 않습니다.", "오늘의 땀방울이 내일의 빛이 됩니다.", "할 수 있다고 믿는 순간 반은 성공한 것입니다.",
    "실수는 배움의 과정일 뿐입니다.", "포기하고 싶을 때가 바로 성공에 가까워진 때입니다.", "천 리 길도 한 걸음부터.",
    "오늘 최선을 다했다면 그것으로 충분합니다.", "당신은 생각보다 훨씬 더 강합니다.", "배움에는 끝이 없습니다.",
    "매일매일 성장하는 당신이 멋지다.", "어제보다 나은 오늘을 만들어봐요.", "자신을 믿으세요, 메이라!",
    "열정은 모든 것을 가능하게 합니다.", "성공은 준비된 사람에게 찾아옵니다.", "지금 흘린 땀은 헛되지 않아요.",
    "당신의 꿈을 응원합니다.", "빛나는 미래가 당신을 기다리고 있어요.", "한 걸음씩 꾸준히 나아가세요.",
    "어려움은 이겨내라고 있는 것입니다.", "오늘의 노력이 내일의 실력이 됩니다.", "포기는 가장 쉬운 선택일 뿐입니다.",
    "당신은 이미 충분히 잘하고 있어요.", "끝까지 포기하지 않는 사람이 승자입니다.", "언제나 응원하고 있을게요.",
    "배움은 언제나 보람차다.", "실패는 성공의 어머니입니다.", "마음먹은 것은 무엇이든 해낼 수 있어요.",
    "오늘 하루도 멋지게 채워봐요.", "당신의 언어 실력이 날마다 늘고 있어요.", "꾸준함은 모든 재능을 이깁니다.",
    "멋진 도전을 하고 있는 당신을 응원해요.", "스스로를 의심하지 마세요.", "모든 위대한 업적은 작은 시작에서 비롯됩니다.",
    "오늘의 배움이 내일의 무기가 됩니다.", "당신은 한국어 마스터가 될 것입니다.", "주저하지 말고 앞으로 나아가세요.",
    "꿈을 품고 노력하는 모습이 아름답습니다.", "어떤 순간에도 자신을 믿으세요.", "성공을 향한 길을 잘 걸어가고 있어요.",
    "매일의 습관이 운명을 바꿉니다.", "당신의 가능성은 무궁무진합니다.", "오늘도 기적 같은 하루를 만들어봐요.",
    "열심히 하는 당신이 참 자랑스럽습니다.", "배우는 즐거움을 잊지 마세요.", "어려운 벽은 더 높이 뛸 수 있게 해줍니다.",
    "당신의 발걸음은 늘 올바른 방향입니다.", "시작이 반이다, 오늘도 힘내자!", "작은 성취들을 모아 큰 성공을 만들어요.",
    "목표를 향해 곧게 나아가세요.", "당신의 눈부신 성장을 믿어 의심치 않습니다.", "오늘도 한 수 배우는 날입니다.",
    "포기하지 않는 한 실패란 없습니다.", "당신 안의 잠재력을 깨우세요.", "내일의 당신은 오늘보다 더 대단할 거예요.",
    "노력은 결코 사라지지 않습니다.", "당신의 열정을 응원합니다, 화이팅!", "힘든 만큼 더 크게 성장할 것입니다.",
    "오늘 세운 작은 목표를 달성해봐요.", "당신의 꿈에 날개를 달아주세요.", "언제나 밝게 빛나는 메이라!",
    "배움의 기쁨을 만끽하세요.", "한계는 스스로 정하는 것입니다.", "당신은 무엇이든 해낼 수 있는 사람입니다.",
    "오늘도 의미 있는 시간을 만들어봐요.", "꾸준히 걷다 보면 목적지에 닿아 있을 것입니다.", "당신의 노력이 결실을 맺을 거에요.",
    "자신만의 속도로 흔들리지 말고 가세요.", "오늘 하루도 눈부시게 빛나길 바랍니다.", "배우고 익히니 이 또한 기쁘지 아니한가.",
    "당신의 도전을 온 마음으로 응원해요.", "실수를 두려워하지 말고 부딪혀 보세요.", "오늘의 작은 시도가 내일의 큰 변화를 만듭니다.",
    "당신은 날마다 더 현명해지고 있어요.", "마음먹은 대로 이루어지는 하루가 되기를.", "지치지 않는 열정을 응원합니다.",
    "오늘도 새로운 것을 배우는 멋진 하루!", "당신의 성실함이 가장 큰 무기입니다.", "목표를 향한 당신의 집중력에 박수를 보냅니다.",
    "어떤 역경도 당신의 의지를 꺾을 수 없어요.", "오늘 하루도 스스로에게 떳떳한 하루로.", "당신의 내일은 오늘보다 훨씬 눈부실 것입니다.",
    "배움에 대한 열정이 참 아름답습니다.", "한 번에 하나씩, 차근차근 해내면 됩니다.", "당신은 이미 충분히 빛나는 사람이에요.",
    "오늘도 기분 좋은 일만 가득하길.", "자신감을 가지고 크게 한 걸음 내딛으세요.", "당신의 노력은 반드시 빛을 발합니다.",
    "꿈을 향한 항해를 멈추지 마세요.", "오늘 흘린 땀방울은 성장의 증거입니다.", "당신이 흘린 시간은 모두 보석이 될 거예요.",
    "언제나 응원하는 사람들이 있다는 걸 기억하세요.", "오늘도 멋진 하루를 스스로 선물해봐요.", "당신의 가능성을 믿고 직진하세요.",
    "배움은 언제나 나를 배신하지 않습니다.", "작은 성공의 경험을 소중히 여기세요.", "오늘도 한 걸음 더 앞으로 전진!",
    "당신의 미소가 주변을 환하게 밝힙니다.", "어떤 순간에도 긍정의 에너지를 잃지 마세요.", "당신은 늘 눈부시게 성장하고 있어요.",
    "오늘 하루도 감사함으로 채워보세요.", "당신의 꿈을 향한 열정을 응원합니다.", "모든 순간이 당신을 위한 배움의 무대입니다.",
    "오늘도 멋진 실력 발휘를 해봐요.", "당신은 언제나 최선을 다하고 있어요.", "스스로를 칭찬해 주는 하루를 보내세요.",
    "목표를 향해 한 치의 흔들림 없이.", "당신의 뜨거운 열정을 언제나 응원합니다.", "오늘도 내 인생 최고의 날로 만들어봐요.",
    "배우고 도전하는 당신이 진짜 주인공입니다.", "당신이 가는 길은 언제나 꽃길이 될 거예요.", "오늘도 무한한 가능성을 펼쳐보세요."
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
1. ALTI ÇİZİLİ KELİMELER: Unutulan kelimelerdir. KESİNLİKLE EKLE.
2. ZIT ANLAMLILAR: Arasında 'x' olanlar zıt anlamlıdır. "tr" kısmına "Anlamı (Zıt Anlamlısı: [Diğer Kelime])" yaz.
3. GRAMER: Başına tire (-) koy ve "tip" değerini "gramer" yap.
4. KELİMELER: "tip" değerini "kelime" yap. Sadece TOPIK 4+ al.
5. ÖRNEK CÜMLELER: Kitaptaki orijinal cümleyi al. Yoksa 유명인사 özneli ve sayma kelimeli cümle üret.
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
                    st.success(f"Analiz tamamlandı! Toplam {len(yeni_maddeler)} 새로운 단어가 추가되었습니다.")
                    
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
            if st.button("Öğretmene Gönder", use_container_width=True):
                if kullanici_cumlesi:
                    with st.spinner("Öğretmen cümleni okuyor..."):
                        try:
                            geribildirim_komutu = f"Adın AI Öğretmen. Karşındaki Meyra. Meyra '{kart['korece']}' kelimesini ve '{st.session_state.secilen_gramer}' gramerini 사용하여 다음 문장을 만들었습니다: '{kullanici_cumlesi}'. 이 문장이 맞습니까? 틀린 부분이 있다면 Meyra에게 직접 설명하고 수정해주세요."
                            cevap_metni = ai_cevap_al(geribildirim_komutu)
                            st.session_state.gramer_feedback = cevap_metni
                        except Exception as e:
                            st.error(str(e))
            
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
            if st.button("Cümlemi Kontrol Et", use_container_width=True):
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
            st.success("🎉 Harika! 모든 단어가 장기 기억에 저장되었습니다. Şu an dikte yapılacak taze kelime yok.")
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
                    st.success("정답입니다! Harikasın 메이라!")
                else:
                    st.error(f"틀렸습니다. Doğrusu: '{kart['korece']}' olmalıydı.")
        with col2:
            if st.button("Başka Kelimeye Geç", use_container_width=True):
                st.session_state.yazma_karti = random.choice(dikte_havuzu)
                st.session_state.yazma_id = random.randint(10000, 99999)
                st.rerun()
