# 🎬 AutoDub Studio v0.0.1 Beta

**Yapay Zeka Destekli Video Dublaj Sistemi** — Yerel yapay zeka kullanarak profesyonel video dublajı için Windows 11 masaüstü uygulaması.

> Transkripsiyon → Çeviri → Seslendirme (14 dil) → MKV
> Hepsi yerel. Hepsi ücretsiz. Arayüz: EN 🇬🇧 / RU 🇷🇺 / TR 🇹🇷

<p align="center">
  <img src="gui/public/logo-icon.png" alt="AutoDub Studio" width="128"/>
</p>

---

## 🪟 Windows 11 Yerel Görünümü

- **Fluent UI v9** — Microsoft'un resmi React bileşen kütüphanesi
- **Mica efekti** — Yerel Windows 11 pencere şeffaflığı
- **3 Tema** — Açık, Koyu, Loş (Teams Koyu)
- **Win11 Ayarlar düzeni** — Kenar çubuğu navigasyonu, kart tabanlı içerik, form satırları
- **Yerel Windows uygulamalarından farksız**

---

## 🚀 Özellikler

### İşlem Akışı (Pipeline)

| Adım | Teknoloji | Durum | Açıklama |
|------|-----------|-------|----------|
| 📥 **İndirme** | yt-dlp | ✅ | YouTube / TikTok / Vimeo URL veya yerel dosya |
| 🎵 **Vokal Ayrıştırma** | Demucs (htdemucs_ft) | ✅ | 4 model birleşimi, en iyi kalite |
| 📝 **Transkripsiyon** | Faster-Whisper (large-v3) | ✅ | 99 dil, CUDA, önbelleğe alma |
| 👥 **Diarization (Konuşmacı Ayrımı)** | Pyannote 3.1 | ✅ | Temiz vokallerde konuşmacı tespiti (HF token gereklidir) |
| 🧠 **Yapay Zeka Çeviri** | DeepSeek + Google Yedekleme | ✅ | Akıllı düzeltme ve hata toleransı |
| 🎙️ **Seslendirme (TTS)** | XTTS v2 | ✅ | Ses klonlama, 10 dil, konuşmacı bazlı referans |
| 🎙️ **Seslendirme (TTS)** | F5-TTS PyTorch | ✅ | Sıfır atış klonlama (daha yavaş, daha yüksek kalite) |
| 🎙️ **Seslendirme (TTS)** | F5-TTS ONNX | ⚠️ | Sadece Türkçe, v0.0.1'de veri tipi sorunu |
| 🎙️ **Seslendirme (TTS)** | Qwen3-TTS | ⚠️ | Windows'da .venv bağımlılık çakışması |
| 🎬 **Birleştirme** | FFmpeg MKV | ✅ | 2 dublaj kanalı + orijinal + altyazılar |

### Çıktı (.mkv) İçindeki Ses Kanalları
| Kanal | İçerik |
|-------|--------|
| Orijinal Ses | Değiştirilmemiş kaynak |
| **Dublaj** | Arka plan (%100) + Orijinal ses (%25) + TTS (%100) |
| **Temiz Ses** | Arka plan (%100) + TTS (%100) — orijinal ses yok |
| Altyazılar | Orijinal + Çevrilmiş (SRT) |

### 14 Dil Desteği
🇷🇺 🇹🇷 🇬🇧 🇸🇦 🇪🇸 🇫🇷 🇩🇪 🇨🇳 🇯🇵 🇰🇷 🇮🇹 🇵🇹 🇵🇱 🇮🇳

### Kullanıcı Arayüzü
- **Fluent UI v9** — Yerel Windows 11 bileşenleri
- **3 Arayüz Dili** — EN, RU, TR (tam yerelleştirme, 300+ anahtar)
- **Komut Paleti** — Ctrl+K ile arama ve gezinme
- **Klavye kısayolları** — Sekmeler için Ctrl+1/2/3/ vb.
- **Sayfa geçişleri** — Win11 tarzı kaydırma animasyonları
- **GPU/VRAM/RAM izleme** — Durum çubuğunda gerçek zamanlı göstergeler
- **Sanal Log Görüntüleyici** — Herhangi bir log hacminde 60fps, yapışkan kaydırma
- **VRAM Temizleyici** — Yüksek GPU baskısını otomatik algılama, tek tıkla işlem sonlandırma
- **ARIA erişilebilirliği** — Ekran okuyucu desteği

### Akıllı Özellikler
- **Otomatik güncelleyici** — Arka planda ilerleme durumuyla indirme
- **Hata raporları** — GitHub Issues'a otomatik gönderme
- **Model Yöneticisi** — İlerleme durumuyla yapay zeka modellerini indirme/silme
- **Gelişmiş ayarlar** — 6 aç/kapat seçeneği (SRT dışa aktarma, geçici dosyaları tutma vb.)
- **Canlı Altyazılar** — Gerçek zamanlı çeviri arayüzü
- **Yapay Zeka Sohbet** — Markdown işleme ile Ollama üzerinden yerel LLM
- **DeepL + Gemma4 Hibrit** — DeepL tabanlı çeviri + Gemma4 ile yapay zeka düzeltmesi
- **Satır bazlı İnceleme Editörü** — Her segment için orijinal/çeviri yan yana

### Güvenlik
- API anahtarları Tauri Secure Store'da (İşletim sistemi anahtarlığı)
- WebSocket token doğrulaması (Her başlangıçta yeniden oluşturulur)
- Güvenli Alt İşlem (Subprocess) Ortamı (Anahtarlar aktarılmaz)
- Log gizleme (Gizli bilgiler filtrelenir)
- CORS, CSP, yol doğrulama, SSRF koruması
- Hassas uç noktalarda Origin doğrulaması

---

## 🏗️ Mimari

```
AutoDubStudio/
├── backend/
│   ├── main.py              # FastAPI + WebSocket + 15 uç nokta
│   ├── translator.py        # 6 motor + Gemma4 düzeltme
│   ├── shared.py            # Paylaşılan durum (döngüsel içe aktarma yok)
│   ├── workers.py           # Arka plan görevleri
│   ├── agent.py             # Yapay zeka ajanı
│   └── vram_manager.py      # VRAM optimizasyonu
├── engine.py                # Ana işlem akışı (AutoDubWorker)
├── live_engine.py           # Canlı altyazılar
├── f5_worker.py             # F5-TTS PyTorch (marduk-ra Türkçe)
├── f5_onnx_worker.py        # F5-TTS ONNX (patientxtr Türkçe)
├── *_worker.py              # TTS görevlileri (qwen3, xtts, lip_sync, diarization)
├── gui/
│   ├── src/
│   │   ├── App.tsx          # Win11 düzeni (Mica başlık çubuğu + kenar çubuğu + içerik)
│   │   ├── main.tsx         # FluentProvider kökü
│   │   ├── theme.ts         # Fluent temaları (Light/Dark/Dim)
│   │   ├── index.css        # Win11 stilleri
│   │   ├── store.ts         # i18n (3 dilde) + Tauri Store
│   │   ├── pages/           # DubbingStudio, LiveSubtitles, AIChat, Settings
│   │   ├── components/      # StatusBar, CommandPalette, ModelDownloader...
│   │   ├── hooks/           # useOllama, usePipelineWebSocket, useModelStatus...
│   │   └── lib/             # errorReporter, toast, utils
│   └── src-tauri/           # Rust: Mica, otomatik güncelleyici vb.
└── config.json              # Çökme raporları için GitHub token
```

---

## 📦 Kurulum

### Gereksinimler
- Windows 10/11
- Python 3.12 · Node.js 20+ · Rust · Ollama · FFmpeg
- NVIDIA GPU 4+ GB VRAM (önerilen)

### Geliştirme

```bash
git clone https://github.com/LiskinLabs/autodubstudio.git
cd AutoDubStudio

# Arka uç (Backend)
uv sync
python backend/main.py

# Ön uç (Frontend) - Yeni bir terminalde
cd gui
npm install
npm run tauri dev
```

### Uygulamayı Derleme (.exe / .msi)

```bash
cd gui
npm run tauri build
# Yükleyiciler: gui/src-tauri/target/release/bundle/nsis/ ve msi/
```

---

## 🗺️ Yol Haritası (Roadmap)

### v0.0.1 ✅ Mevcut Durum
- [x] Tam Fluent UI v9 geçişi
- [x] Win11 Ayarlar duyarlı düzeni
- [x] Canlı göstergeli GPU/VRAM/RAM monitörü
- [x] F5-TTS ONNX Türkçe desteği
- [x] DeepL + Gemma4 hibrit çeviri
- [x] Konuşmacı ayrımı (Diarization)
- [x] VRAM Temizleyici
- [x] Akıllı TTS referans seçimi
- [x] Otomatik hata raporlama (GitHub Issues)

### v0.0.1'de Bilinen Sorunlar
- ⚠️ ONNX TTS: Veri tipi uyumsuzluğu (int32/int64) — XTTS kullanın
- ⚠️ Qwen3 TTS: Windows bağımlılık çakışması — XTTS kullanın

### v0.1.0 🎯 Gelecek
- [ ] GitHub Releases üzerinden yayınlama
- [ ] GitHub'dan otomatik güncelleme
- [ ] Kod imzalama (Code signing)
- [ ] Mac/Linux desteği

---

## 🤝 Yazar

**Silvestr Liskin** — Kıdemli Otomasyon Mühendisi / Endüstriyel Robot Programcısı  
Teknorob Robot ve Otomasyon — Bursa, TR  
[GitHub](https://github.com/LiskinLabs) · [LinkedIn](https://www.linkedin.com/in/silvestr-liskin-ab712920b)

---

MIT Lisansı
