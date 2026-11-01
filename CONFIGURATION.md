# Yapılandırma / Configuration

Mac ve Windows aynı JSON sözleşmelerini ve paneli kullanır. Platforma özgü runtime kurulumu için [QUICKSTART](QUICKSTART.md) ve [Windows](docs/WINDOWS.md) rehberlerini kullanın.

## Motor ve workspace

HyperFrames varsayılandır. `preflight`, `install`, `smoke`, `start` ve kaynak CLI `setup` seçimleri bu varsayılanı kullanır. Remotion ayrı `optional/remotion/` paket graph’ı ve lock dosyasıyla, yalnız açık `--engine remotion` seçimiyle kurulur. `--engine all` her ikisini seçer. Remotion’un kendi koşulları ayrıca incelenir; otomatik motor fallback’i yoktur.

Kurulum receipt’i seçili graph, package/lock hash’leri ve kurulu paketlere bağlıdır. Eski/farklı graph receipt’i kurulum kontrolünü atlatmaz. Core HyperFrames kontrolü Remotion addon’unu gerektirmez. Global motor kurarak, lock integrity değiştirerek veya `--omit=optional` ile kontrolleri geçmeye çalışmayın.

macOS arm64 ffprobe tarifi sabit FFmpeg kaynağını mevcut Command Line Tools/SDK ile derler; kaynak/lisans `.runtime/probe/` altında tutulur. Kaynaktan tam FFmpeg geliştirme tarifi ayrıca mevcut `pkg-config` ister. Windows ayrı sabit medya arşivini kullanır. Diğer platformların genel uyumluluğu, doğrulanmış native runtime tarifi anlamına gelmez. Kaynak pakette kurulu runtime binary’leri yoktur.

Kaynak-only panel örneği `work/local-studio`, first-run `start` ise sabit `work/first-studio` kullanır. `--workspace` ile kendi panel yolunuzu açıkça seçebilirsiniz. Bu çalışma alanları otomatik birleştirilmez. Kaynak kökünü ve mevcut işleri koruyun; güncellemeleri yeni boş dizinde inceleyin.

Kurucu güncel LICENSE’ın `--license-sha256` değerini ve ayrı `--allow-downloads` iznini ister. Eski `--accept-eula-sha256` alias olarak kalır. Özgün kod [MIT](LICENSE) kapsamındadır; hash kaydı ek MIT sözleşmesi veya üçüncü taraf kabulü değildir. Kaynak/manifest bütünlük kontrolü ile render runtime hazırlığı ayrı kapılardır. Kaynak değişikliklerinden sonra incelenmiş commit ve manifest üretimi için [RELEASING](RELEASING.md) akışını izleyin.

## Kendi AccountPack’iniz

Tek nötr örnek `accountpacks/neutral/neutral.json` altındadır. Tam dosyayı proje köküne göre `work/accountpacks/my-pack.json` olarak kopyalayıp uyarlayın. `id`, `profile.id`, `fixture.brand` ve varsa `legacy_fixture.brand` değerlerini dosya köküyle eşleşen aynı benzersiz kimliğe (`my-pack`) çevirin. `display_name` ve `profile.name` için kendi adınızı seçin. Bundled kimliklerin üzerine yazmayın. Paneli yeniden başlatıp kataloğu yükleyin.

Gerekli alanlar `id`, `display_name`, `niche`, `procedures`, `visual_families`, `scene_vocab`, `series_rules`, `voice_defaults` ile sürümlü `profile`, `fixture`, `capabilities`, `formats`, `scene_contract` ve kural alanlarını kapsar. Tam örnekteki sözleşmeleri koruyun. Yalnız uygulanmış görsel aileler ve sahne türleri geçerlidir; yeni pack JSON’u yeni motor veya keyfi çalıştırılabilir kod eklemez. Renkler doğrulanan renk değeri, sayısal stiller sınırlı ve sonlu sayı olmalıdır; HTML/CSS/JS bir stil değeri değildir. Bozuk veya yinelenen pack diğer geçerli pack’lerden ayrılarak hata verir.

`procedures` alanına kendi içerik üretim adımlarınızı yazın. Örnekteki `TODO`, tamamlanmış bir yöntemin verilmediğini belirtir; bunu hazırladığınız yöntemin veya çıktının otomatik onayı saymayın. Kaynak, dil, anlatım ve son görüntüyü kendiniz inceleyin. `voice_defaults` başlangıçta provider `off`, voice ID `null` kullanır. Kendi ses seçiminizin ve medyanızın kullanım haklarını ayrıca değerlendirin. [AccountPack notları](docs/ACCOUNT-PACKS.md) desteklenen sınırları açıklar.

## BYOK ve ücretli istekler

Sağlayıcılar ilk açılışta **off** durumundadır. `.env.example` otomatik okunmaz; gerçek anahtarı env dosyası, Git, log veya örnek JSON’a koymayın. Ayrı ve açıkça seçilmiş live oturumunda kendi anahtarınızı panelin oturum bağlantısına girin. Demo modu sentetik örnektir; gerçek sağlayıcı sonucu veya ses değildir.

Bağlantı, ücretli çağrı onayı değildir. Her istek için tam sağlayıcı/model/ses, girdi, bütçe ve onay snapshot’ı kontrol edilir. Metin ve ElevenLabs bağlantıları bağımsızdır; birinin anahtarı diğerini açmaz. Katalog kaydı veya model seçimi canlı hesap erişimi/başarısı kanıtı değildir. API servis ücretleri ayrı kalır; belirsiz sağlayıcı sonucu otomatik yeniden gönderilmez. Bu kaynak adayı için canlı sağlayıcı kabulü tamamlanmış iddia edilmez.

## Şablonlarla çalışma

Panelde 91 şablonun listesini yükleyip AccountPack, şablon, örnek girdi ve hazırlama motorunu seçin. Yedi temel kimlik: `kinetic-grid`, `causal-path`, `exploded-blueprint`, `isometric-process`, `liquid-merge`, `bauhaus-modules`, `pixel-journey`. Diğer 84 development şablonu sabit hash’li yerel modül kaydından gelir; kullanıcı kodu çalıştırılmaz. 182 örnek girdi bu katalog içindedir; kaynak referansları ve paletler ek şablon sayılmaz.

**Alanları yükle** 89 şablon için kısmi sürümlü alan kontrollerini getirir; `tile-quest-state` ve `toon-dialogue-blocking` JSON-only kalır. Yalnız beyanlı türler/sınırlar alan kontrolüdür; diğer alanları JSON ile düzenleyin. Boş sayı sıfıra çevrilmez. Alanları JSON’a uygulama, varsayılan ekleme ve koleksiyon düzenleme açık işlemlerdir. Değişmeyen sayı/metin yazımı ile bilinmeyen alanlar korunur. JSON ve alan taslağı çakışıyorsa önce taslağı açıkça bırakın veya özgün JSON’a dönün.

**Yerel doğrula** girdi sözleşmesini kontrol eder; iş, render veya sağlayıcı isteği oluşturmaz. Normalize değerler ayrı gösterilir, ham JSON’a otomatik uygulanmaz. **Kaynak hazırla** `family-inputs/` ve `family-renders/` altında düzenlenebilir kaynak üretir; bu, ses veya MP4 renderi değildir. Görünür sayısal/fiyat iddiaları için panelde kaydedilmiş kaynakla bağlı kapsamlı iddia gerekir; doğruluk yine insan incelemesi ister. Development metinlerinde HTML işaretleri, URL şemaları ve CSS yönergeleri kabul edilmez.

14 medya şablonunun paketli teknik örneği gerçek içerik medyası sayılmaz. Uygun ve kullanım hakkınız olan kendi medyanızı sağlayın. Development etiketi, kaynak hazırlama başarısı ve alan kapsam sayacı; native/görsel/yayın kabulü değildir.

## Galeri taslağı, planı ve geçmişi

Taslaklar AccountPack + şablon + örnek bazında sayfa RAM’inde tutulur. Filtre sıfırlama veya katalog yükleme taslağı silmez; sayfayı tamamen yenilemek/kapatmak RAM taslaklarını temizler. Bekleyen istek, özgün bağlamıyla görünür; farklı şablona geçmek eski yanıtı yeni şablonun sonucu yapmaz. Hata otomatik tekrar edilmez.

Niş/konu planı hesap bazında kaydedilir. Katalog etiketlerinden türetilen başlangıç seçenekleri tüm olası konuları temsil etmez. Özel kayıt sınırı hesap başına 1000’dir. Seçimi uygulama veya temizleme açık işlemdir; plan, JSON taslağını veya doğruluk/kanon kabulünü otomatik değiştirmez. Revizyon çakışmasında yeniden yükleyip mevcut durumu inceleyin.

Korumalı panel hazırlamaları yerel geçmişten açılır. Ayrıntı ve indirme tüm manifesti, dosya hash’lerini ve hazırlamaya bağlı intake receipt’ini yeniden doğrular. CLI/Engine hazırlamaları bu panel receipt’ini oluşturmaz; eski kayıtlar otomatik kabul edilmez. Kaynak hazırlama geçmişi MP4, native render veya yayın kabulü sağlamaz.

Kayıtlı hazırlamayı açıp **Render durumunu yenile** kullanın. Ayrı onay seçili kayda ve sabit motoruna yerel sessiz render başlatır; RAM JSON taslağını kullanmaz. İptal seçili girişime bağlıdır. Eksik runtime, hata veya kesintiden sonra yeni girişim açık işlem ister; kurulum, motor geçişi ve sağlayıcı çağrısı otomatik yapılmaz. Tamamlanmış ve doğrulanmış MP4 indirmelerinde bütünlük tekrar kontrol edilir.

Seri bölüm/taslak geçmişleri hesap ve isteğe bağlı seri kapsamında ayrı sayfalıdır; görünür ilk sayfa bütün arşiv değildir. Arşiv gezinmesi yerel taslakları silmez, yeni bölüm veya kanon kabulü oluşturmaz. Ses değiştiğinde önceki kelime/altyazı zamanları yeni ses için doğrulanmış sayılmaz.

## Kaynak referansları ve paletler

Kaynak referansları mevcut üç MIT kod uyarlamasının commit bağlantılarını/atıflarını gösterir. Kod lisansı film, ses veya başka medya haklarını kapsamaz. Dış bağlantı yalnız kaynak sayfasını açar; otomatik kod/medya içe aktarılmaz.

Dört yerel palet renk kümesidir, yeni hareket/renderer değildir. Üçü 84 development şablonunda; **Gece planı** ise `torn-edge-layer-transfer` hariç 83’ünde desteklenir. Yedi temel şablon ortak palet girdisi kabul etmez. Paleti taslağa uygulama yalnız mevcut JSON palet alanını değiştirir; ardından doğrulama/hazırlama/render yine ayrı yapılır. Uyumluluk bir kaynak sözleşmesidir, görsel kabul değildir.

## Yerel veriler

`work/` ve `.runtime/` özel değişebilir verileri içerir; depoya göndermeyin. Yeni POSIX state dizinleri 0700, özel dosyalar 0600 kullanır. Windows özel state için sınırlı DACL uygular. Mevcut uygunsuz izinler otomatik onarılmaz. Linked/reparse veya güvensiz yollar reddedilir; yeni boş özel workspace seçin ve [Sorun giderme](TROUBLESHOOTING.md) rehberini izleyin. Bu kontroller eski dosyalardaki bilinmeyen sırları temizlemez.

## English

Use one codebase on Mac/Windows; install runtimes according to the platform guides. HyperFrames is default, Remotion a separately selected addon. Source-only browsing and first-run use different example workspaces, and source preparation is distinct from MP4 rendering. Runtime/source-integrity gates remain in place; the reviewed LICENSE hash adds no MIT contract or third-party acceptance.

Copy the complete neutral AccountPack into `work/accountpacks/my-pack.json`, keep its versioned contracts and update all matching IDs. Define your own procedures; no complete production method is bundled. Providers start off, `.env` is not automatically read, and live keys belong only in an explicitly selected session. Each paid request needs exact input/provider/model/voice/budget approval.

The 91-template catalog has 182 examples and partial typed fields for 89 templates. Validate, prepare and render explicitly; supply rights-cleared media where needed. Drafts remain in page RAM, protected preparation history rechecks receipts/hashes, and saved renders retain runtime/approval controls. Planning metadata, source references, palettes and source checks are not factual, native, creative or publication acceptance. Preserve work and report uncertain outcomes before retrying.
