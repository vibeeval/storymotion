# StoryMotion

Yerel JSON brief’leri ve AccountPack’leri düzenlenebilir video kaynaklarına dönüştüren açık kaynak proje. **Mac ve Windows aynı kod tabanını kullanır. HyperFrames varsayılan motordur; Remotion ayrı, isteğe bağlı eklentidir.**

Kaynak adayında 91 şablon (7 temel, 84 development) ve 182 örnek girdi bulunur. 89 şablon kısmi alan editörü, diğerleri JSON düzenleme sunar. Development etiketi bir kalite onayı değildir. Medya bekleyen 14 şablonun teknik örneklerini kendi kullanım hakkınız olan medyayla değiştirin.

## İlk kullanım

Depoyu klonlayın veya kaynak arşivini yeni bir klasöre açın. Proje kökünde, yalnız yerel paneli incelemek için:

```sh
python3 -B -m storymotion.dashboard --workspace work/local-studio --port 4402 --llm off --elevenlabs off
```

Windows PowerShell’de:

```powershell
python -X utf8 -B -m storymotion.dashboard --workspace work/local-studio --port 4402 --llm off --elevenlabs off
```

Python 3.9+ gerekir. Terminalde yazan tam yerel bağlantıyı açın; oturum bağlantısını paylaşmayın. Ctrl+C paneli durdurur. Bu yol paneli açar ve yerel workspace oluşturur; renderer veya sağlayıcı kurulumu yapmaz. **Eksik runtime ile render ayrı olarak engellenir.** Render kurulumu için [Hızlı başlangıç](QUICKSTART.md), Windows ayrıntıları için [Windows rehberi](docs/WINDOWS.md) kullanılır.

## Çalışma biçimi

- Nötr AccountPack’i kendi içerik yönteminiz, görsel tercih ve kaynaklarınızla uyarlayın. Hazır bir içerik üretim yöntemi veya özel hesap profili dahil değildir.
- Şablonu, örnek girdiyi ve motoru seçin; metni veya JSON’u düzenleyip doğrulayın. Kaynak hazırlama, MP4 render ve son görüntü incelemesi ayrı adımlardır.
- Çalışmalar `work/` altında kalır. Panel yerel bağlantıya bağlanır. Sağlayıcılar kapalı başlar; BYOK bağlantısı, her ücretli isteğin ayrı girdi/model/ses/bütçe onayının yerini tutmaz. API servis ücretleri sağlayıcıya aittir.

## Lisans ve mevcut durum

Özgün StoryMotion kodu ve özgün proje belgeleri [MIT License](LICENSE) kapsamındadır. MIT, bildirimi koruyarak kullanım, değişiklik, dağıtım ve yazılım kopyalarının satışına izin verir. Üçüncü taraf kod, font, medya ve runtime koşulları ayrı kalır: [Lisans kapsamı](LICENSING.md), [Üçüncü taraf bildirimleri](THIRD-PARTY-NOTICES.md).

Kamuya açma **2 Kasım 2026 için planlanmıştır**; bu kaynak adayı yayımlanmış sürüm olarak sunulmaz. Native Windows kurulumu/render, temiz cihaz kurulumu ve 91 şablonun kapsamlı görsel kabulü tamamlanmış sayılmaz. macOS Apple Silicon için mevcut runtime tarifi bulunur; bu, temiz Mac kurulumu garantisi değildir. Güncel kontrol kapsamını [Sorun giderme](TROUBLESHOOTING.md) açıklamaktadır.

[Başla](BAŞLA.md) · [Kaynak sürümü hazırlama](RELEASING.md) · [Yapılandırma](CONFIGURATION.md) · [SSS](FAQ.md) · [Destek](SUPPORT.md) · [AI ile kurulum](AI_INSTALL.md)

## Kaynak kontrolleri

Proje kökünde yerel Python birim kontrollerini çalıştırabilirsiniz:

```sh
python3 -B -m unittest discover -s tests -v
```

Windows’ta `python -X utf8 -B -m unittest discover -s tests -v` kullanılır. Bu komut yerel birim/sözleşme kontrolleridir; native Windows, tarayıcı, temiz kurulum veya tüm şablonların görsel kabul testi değildir. Bu belge kendi başına testlerin geçtiği veya barındırılan CI’ın başarılı olduğu iddiasını taşımaz. İncelenmiş kaynak commit’i ve dağıtım manifesti hazırlama süreci [RELEASING.md](RELEASING.md) içindedir.

## English

StoryMotion prepares editable video sources from local JSON briefs and AccountPacks. Mac and Windows share one codebase. HyperFrames is the default; Remotion is an optional separate addon. The catalog contains 91 bounded templates and 182 input examples, with partial field controls for 89 templates. Supply suitable, rights-cleared media for media-dependent examples.

Use the source-only dashboard commands above to browse locally with providers off. Rendering retains separate runtime checks. See [Quick start](QUICKSTART.md) for installation and [Windows](docs/WINDOWS.md) for its platform requirements. Define your own production method in a neutral AccountPack; model/voice services require your own keys and separate per-request approval. Original code is MIT; third-party terms remain separate. Publication is planned for 2 November 2026, not represented as completed. Native Windows, clean-device and comprehensive visual acceptance remain unverified.
