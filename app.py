import streamlit as st
import google.generativeai as genai
import pandas as pd
import json

# API Ayarı
GOOGLE_API_KEY = st.secrets["API_KEY"]
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-3-flash-preview')

st.set_page_config(page_title="Korece Kelime Asistanı", layout="wide")
st.title("🇰🇷 Akıllı Korece Kelime Asistanı")

# Dil Seçeneği
dil_secimi = st.radio("Anlam Dili Seçimi:", ["TR", "EN", "TR + EN"], horizontal=True)

st.subheader("1. Kitap Sayfası Yükle (Otomatik Çıkarım)")
yuklenen_dosya = st.file_uploader("Kers kitabı sayfasının fotoğrafını yükle (JPG/PNG)", type=["jpg", "jpeg", "png"])

if yuklenen_dosya is not None:
    st.image(yuklenen_dosya, width=300, caption="Yüklenen Sayfa")
    
    if st.button("Kelimeleri Çıkar (TOPIK 4+)"):
        with st.spinner("Yapay zeka sayfayı okuyor ve temel kelimeleri eliyor..."):
            try:
                # Resmi API için hazırlama
                gorsel_verisi = [{"mime_type": "image/jpeg", "data": yuklenen_dosya.getvalue()}]
                
                # Gemini'ye verilen kesin talimat (Prompt)
                komut = """
                Bu görseldeki Korece metni incele. Sadece TOPIK 4, 5 ve 6 (Orta-İleri) seviyesi kelimeleri çıkar. 
                가다, 보다, 친구, 먹다 gibi TOPIK 1-3 seviyesindeki temel kelimeleri KESİNLİKLE yoksay.
                Çıkardığın her kelime için şu formatta geçerli bir JSON listesi döndür. Sadece JSON kodunu yaz, başına veya sonuna markdown veya açıklama ekleme:
                [
                    {"korece": "kelime", "tr": "Türkçe anlamı", "en": "İngilizce anlamı", "ornek_ko": "Görselden veya senin üreteceğin Korece örnek cümle", "ornek_tr": "Örnek cümlenin Türkçesi", "ornek_en": "Örnek cümlenin İngilizcesi"}
                ]
                """
                
                cevap = model.generate_content([komut, gorsel_verisi[0]])
                
                # Gelen metni JSON'dan Tabloya (Pandas) çevirme
                json_metni = cevap.text.strip().replace("```json", "").replace("```", "")
                veriler = json.loads(json_metni)
                df = pd.DataFrame(veriler)
                
                st.success("Kelimeler başarıyla çıkarıldı!")
                st.dataframe(df) # Tabloyu ekranda göster
                
            except Exception as e:
                st.error(f"Bir hata oluştu: {e}")