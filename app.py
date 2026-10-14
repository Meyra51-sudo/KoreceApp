import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import random

# API Ayarı
GOOGLE_API_KEY = st.secrets["API_KEY"]
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-3-flash-preview', generation_config={"temperature": 0.0})

st.set_page_config(page_title="SNU Kelime & Gramer Asistanı", layout="centered")
st.title("🇰🇷 SNU Akıllı Çalışma Asistanı")

# Uygulama Hafızası
if 'kelimeler' not in st.session_state: st.session_state.kelimeler = []
if 'calisilmis' not in st.session_state: st.session_state.calisilmis = []
if 'gecmis' not in st.session_state: st.session_state.gecmis = []
if 'kart_arkasi' not in st.session_state: st.session_state.kart_arkasi = False
if 'gramer_feedback' not in st.session_state: st.session_state.gramer_feedback = None

# Arayüzü 3 Sekmeye Böldük
tab1, tab2, tab3 = st.tabs(["📂 1. Yükle", "🧠 2. Çalışma Modu", "⚙️ 3. Listeyi Düzenle"])

with tab1:
    st.subheader("Kitap Sayfası veya Not Yükle")
    st.info("💡 Telefondan 'Browse files' butonuna tıkladığında açılan kameranı kullan.")
    
    gorsel = st.file_uploader("Fotoğraf Çek veya Yükle", type=["jpg", "jpeg", "png"])
    
    if gorsel is not None:
        if st.button("Analiz Et ve Desteye Ekle"):
            with st.spinner("Yapay zeka matbaa, el yazısı, gramer ve özel notlarını (X, altı çizili) analiz ediyor..."):
                try:
                    gorsel_verisi = [{"mime_type": "image/jpeg", "data": gorsel.getvalue()}]
                    
                    komut = """
GÖREVİN: KATI BİR VERİ ÇIKARICISI OLMAKTIR. 
Görseldeki Korece kelimeleri, el yazısı notları ve dilbilgisi (gramer) kurallarını çıkar.

KURALLAR (KULLANICI NOT ALMA STİLİ):
1. ALTI ÇİZİLİ KELİMELER: Kullanıcı unuttuğu kelimelerin altını çizer. TOPIK 1-2 seviyesi bile olsa ALTI ÇİZİLİ HER KELİMEYİ KESİNLİKLE LİSTEYE EKLE.
2. ZIT ANLAMLILAR (X İŞARETİ): Kullanıcı "가다 x 오다" gibi iki kelime arasına 'x' veya 'X' koymuşsa, bunlar zıt anlamlıdır. İkisini tek bir maddede topla. "korece" kısmına ana kelimeyi yaz, "tr" kısmına "Türkçe Anlamı (Zıt Anlamlısı: [Diğer Kelime] - [Anlamı])" şeklinde belirt.
3. GRAMER KURALLARI: Sayfa başlığında, kenarlarda veya kutu içinde verilen yeni dilbilgisi kalıplarını (örn: -아/어야 하다) çıkar ve bu maddelerin "tip" değerini "gramer" yap.
4. KELİMELER: Gramer dışındaki her şeyin "tip" değerini "kelime" yap. Altı çizililer hariç, sadece TOPIK 4+ kelimeleri al. Eşanlamlıları virgülle tek "korece" satırında birleştir.
5. Sadece JSON formatında çıktı ver:
[{"tip": "kelime veya gramer", "korece": "hedef metin", "tr": "Türkçe ve notlar", "en": "İngilizce", "ornek_ko": "Örnek cümle", "ornek_tr": "Çevirisi"}]
"""
                    cevap = model.generate_content([komut, gorsel_verisi[0]])
                    json_metni = cevap.text.strip().replace("```json", "").replace("```", "")
                    veriler = json.loads(json_metni)
                    
                    mevcut_korece = {k['korece'] for k in st.session_state.kelimeler + st.session_state.calisilmis}
                    yeni_maddeler = [k for k in veriler if k['korece'] not in mevcut_korece]
                    
                    st.session_state.kelimeler.extend(yeni_maddeler)
                    random.shuffle(st.session_state.kelimeler)
                    
                    st.success(f"{len(yeni_maddeler)} yeni madde (kelime/gramer) desteye eklendi! (Daha önce eklenmiş {len(veriler) - len(yeni_maddeler)} madde elendi).")
                    
                except Exception as e:
                    st.error(f"Hata: {e}")

with tab2:
    if len(st.session_state.gecmis) > 0:
        if st.button("↩️ Son İşlemi Geri Al (Yanlış Tıkladım)"):
            son_islem = st.session_state.gecmis.pop()
            if son_islem['islem'] == 'bildim':
                st.session_state.calisilmis.remove(son_islem['kelime'])
                st.session_state.kelimeler.insert(0, son_islem['kelime'])
            elif son_islem['islem'] == 'bilemedim':
                st.session_state.kelimeler.pop() 
                st.session_state.kelimeler.insert(0, son_islem['kelime'])
            st.session_state.kart_arkasi = False
            st.session_state.gramer_feedback = None
            st.rerun()

    st.markdown("---")

    if len(st.session_state.kelimeler) == 0:
        if len(st.session_state.calisilmis) == 0:
            st.info("Destede madde yok. Lütfen kitap yükleyin.")
        else:
            st.success(f"Tebrikler! Toplam {len(st.session_state.calisilmis)} madde öğrenildi.")
            if st.button("Öğrenilenleri Baştan Karıştır ve Tekrar Et"):
                st.session_state.kelimeler = st.session_state.calisilmis.copy()
                st.session_state.calisilmis = []
                random.shuffle(st.session_state.kelimeler)
                st.session_state.kart_arkasi = False
                st.rerun()
    else:
        toplam_madde = len(st.session_state.kelimeler) + len(st.session_state.calisilmis)
        ilerleme = len(st.session_state.calisilmis) / toplam_madde if toplam_madde > 0 else 0
        st.progress(ilerleme)
        
        kart = st.session_state.kelimeler[0]
        
        # EĞER KART BİR GRAMER KURALIYSA
        if kart.get('tip') == 'gramer':
            st.markdown(f"<h1 style='text-align: center; color: #ff4b4b; margin-top: 20px;'>{kart['korece']}</h1>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; font-weight: bold; color: gray;'>[Gramer / Dilbilgisi]</p>", unsafe_allow_html=True)
            
            st.info(f"**Anlamı:** {kart['tr']}\n\n**Örnek:** {kart['ornek_ko']} ({kart['ornek_tr']})")
            
            kullanici_cumlesi = st.text_input("Bu grameri kullanarak kendi Korece cümleni kur:")
            
            if st.button("Cümlemi Kontrol Et", use_container_width=True):
                if kullanici_cumlesi:
                    with st.spinner("Öğretmen cümleni inceliyor..."):
                        geribildirim_komutu = f"Bir öğrenci '{kart['korece']}' gramerini kullanarak şu cümleyi kurdu: '{kullanici_cumlesi}'. Bu cümle doğru mu? Gramer hatası veya doğallık sorunu varsa düzelt, nedenini kısaca ve arkadaşça bir dille Türkçe açıkla."
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
                        st.session_state.gecmis.append({'kelime': islem_karti, 'islem': 'bilemedim'})
                        st.session_state.gramer_feedback = None
                        st.rerun()
                with col2:
                    if st.button("✅ Tamamen Anladım", use_container_width=True):
                        islem_karti = st.session_state.kelimeler.pop(0)
                        st.session_state.calisilmis.append(islem_karti)
                        st.session_state.gecmis.append({'kelime': islem_karti, 'islem': 'bildim'})
                        st.session_state.gramer_feedback = None
                        st.rerun()

        # EĞER KART BİR KELİMEYSE (Standart Quizlet Mantığı)
        else:
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

# 3. Sekme: Kelime Yönetimi (Manuel Düzenleme/Silme)
with tab3:
    st.subheader("Veritabanını Düzenle")
    st.write("Aşağıdaki tablodan kelimeleri düzenleyebilir veya seçip silebilirsin (Delete/Backspace tuşu). İşin bitince kaydet butonuna basmayı unutma.")
    
    if len(st.session_state.kelimeler) == 0:
        st.info("Şu an aktif destede kelime/gramer bulunmuyor.")
    else:
        # Mevcut kelimeleri tabloya dönüştürüp düzenlenebilir hale getirme
        df = pd.DataFrame(st.session_state.kelimeler)
        duzenlenmis_df = st.data_editor(df, num_rows="dynamic", use_container_width=True, hide_index=True)
        
        if st.button("Değişiklikleri Kaydet", type="primary"):
            # Tablodaki güncel veriyi tekrar sözlük yapısına çevirip hafızaya yazma
            st.session_state.kelimeler = duzenlenmis_df.to_dict('records')
            st.success("Tüm düzenlemeler ve silme işlemleri başarıyla kaydedildi!")
