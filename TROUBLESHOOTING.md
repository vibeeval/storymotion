# Sorun giderme / Troubleshooting

Paneli incelemek ile render almak ayrı yollardır. Kaynak-only panel komutu [QUICKSTART](QUICKSTART.md) içindedir; sağlayıcıları kapalı açar ve renderer kurmaz. Runtime için macOS’ta `sh ./install.sh preflight`, Windows’ta `.\install.ps1 preflight` kullanın. `ok`, `source_install_ready`, `install_plan` ve platform durumunu ayrı değerlendirin.

| Kod / durum | Yapılacak işlem |
|---|---|
| `OWNER_EULA_PENDING` | Tarihsel kod adı: LICENSE eksik, geçersiz veya placeholder. Geçerli kaynak kopyasındaki MIT LICENSE’ı kontrol edin; hash uydurmayın. |
| `OWNER_RELEASE_PENDING` / `INSTALL_SOURCE_HASH_MISMATCH` | Kaynak dağıtım manifesti eksik veya incelenen dosyalar değişmiş olabilir. Aynı sürümün doğrulanmış kaynak/manifest eşleşmesini kullanın; kontrol bayraklarını elle aşmayın. MIT izni bu kurulum durumundan ayrıdır. |
| `EULA_ACCEPTANCE_REQUIRED` | Tarihsel kod adı: `--license-sha256` ile mevcut LICENSE’ın tam küçük harfli SHA256 değerini verin. Eski `--accept-eula-sha256` alias’ı da geçerlidir. Bu, üçüncü taraf kabulü değildir. |
| `INSTALL_PERMISSION_REQUIRED` | Bağımlılık indirmesi için açık yetki gerekir; yetki varsa `--allow-downloads` kullanılır. Sağlayıcı üretimi ayrı onay ister. |
| `DEPENDENCY_PLAN_BLOCKED` | Seçilen bağımlılık graph’ı, lock veya sabit probe metadata’sı uyuşmuyor. Global motor eklemeyin veya integrity değerini değiştirerek geçmeyin. |
| `RUNTIME_NOT_READY` / `INDEPENDENT_PROBE_NOT_READY` | Seçilen renderer veya ffprobe hazır değil. Panelin açılması ve kaynak hazırlama, runtime kurulumunun geçtiği anlamına gelmez. Preflight engelini giderin. |
| `PROBE_PLATFORM_UNVERIFIED` | Mevcut macOS kaynaktan probe tarifi yalnız arm64 için doğrulanmıştır. Genel platform uyumluluğu tam render tarifini kanıtlamaz. Windows ayrı medya tarifini kullanır. |
| `PROBE_TOOLCHAIN_REQUIRED` | Mevcut clang, make ve zlib başlıkları içeren macOS SDK önkoşullarını kontrol edin. Kurucu bunları otomatik kurmaz. |
| `SOURCE_FFMPEG_PKG_CONFIG_REQUIRED` | Kaynaktan FFmpeg geliştirme tarifi mevcut `pkg-config` istiyor. OS/global araç kurulumunu bu komut otomatik yapmaz. |
| `UPDATE_STAGING_INCOMPLETE` | Yeni hedef kısmi olabilir; eski kaynak/work korunur. Yeniden stage etmeden `verify` ile inceleyin. |
| `UPDATE_TARGET_EXISTS` / `UPDATE_TARGET_OVERLAPS_WORKSPACE` | Yeni, boş ve mevcut kaynak/work dışında hedef seçin. Mevcut veriyi silmeyin. |
| `CUSTOMER_PROFILE_MALFORMED` / `CUSTOMER_PROFILE_DUPLICATE` | Tam nötr AccountPack şemasını, dosya adı/ID eşleşmesini ve benzersiz kimlikleri kontrol edin. Geçerli diğer pack’ler kullanılabilir. |
| `LOCAL_SESSION_REQUIRED` | Terminaldeki tam ilk bağlantıyı açın. Tüketilmiş link ve bitmiş oturum için yalnız kendi panelinizi yeniden başlatın; bağlantıyı paylaşmayın. |
| `LOCAL_STATE_PERMISSIONS` | Mevcut özel state’in sahipliği/izinleri uygun değil. Yeni boş özel workspace seçin veya dar kapsamlı manuel inceleme yapın. Recursive chmod, ACL sıfırlama veya veri silme uygulamayın. |
| Kilit veya port dolu | Başka süreci durdurmayın, lock dosyasını silmeyin. Yalnız kendi servisinizi durdurun veya boş port/yeni workspace seçin. |
| Belirsiz sağlayıcı sonucu | Aynı isteğin durumunu ve receipt’ini inceleyin. Otomatik veya kör ücretli tekrar yapmayın. |

## Dosyalar ve oturum

İlk-run launcher `work/first-studio`, kaynak-only örnek `work/local-studio` kullanır. Farklı workspace’lerdeki işler otomatik birleşmez. Kendi AccountPack dosyaları proje köküne göre `work/accountpacks/` altından okunur.

Yeni POSIX özel state dizinleri 0700, özel veri dosyaları 0600 ile oluşturulur; mevcut uygunsuz izinler otomatik düzeltilmez. Windows yeni özel state için sınırlı DACL, kilitler için LockFileEx kullanır; reparse/bağlantılı yollar ve NTFS dışı workspace’ler reddedilir. OS güvenlik veya PowerShell execution policy ayarını değiştirmeyin; `.ps1` kısıtlıysa [Windows rehberindeki](docs/WINDOWS.md) doğrudan Python komutlarını kullanın.

Beklenmeyen HTTP hataları seçilen workspace’in `logs/local.log` dosyasında sabit olay kodu ve izinli hata sınıfıyla kaydedilir; en çok üç 64 KiB dosya tutulur. Anahtar, token, URL/header/body ve ham hata değeri loglanmaz; telemetri gönderilmez. Tüm logu veya workspace’i otomatik paylaşmayın.

## Hazırlama ve render sonuçları

Galeri RAM taslakları sayfa kapanınca kaybolur; doğrulanmış panel hazırlamaları yerel geçmişte kalır. Tarihsel dosya açılışı manifest/hash ve korumalı intake receipt’ini yeniden kontrol eder. Eksik kanıtı uydurmayın; CLI hazırlamasının panel receipt’i oluşturduğunu varsaymayın.

Kayıtlı bir renderi yeniden başlatmadan durumunu yenileyin. Tamamlanmış ve sunucuda doğrulanmış MP4’ler için indirme sunulur. Ses değiştiyse eski altyazı veya kelime zamanları doğrulanmış sayılmaz. Rig/görsel revizyonunda parent kanıtı değişmişse eski işten kanıt dosyası kopyalayarak kontrolü geçmeyin.

Platform uyumluluk kapıları macOS arm64/x64, Linux glibc arm64/x64 ve Windows 10/11 x64 içindir. Bunlar aynı kapsamda doğrulanmış kurulum tarifleri değildir. Native Windows kurulumu/tarayıcı/render, temiz Mac kurulumu ve 91 şablonun tüm girdileriyle kapsamlı görsel kabulü tamamlanmış olarak sunulmaz. Kaynak testi, bir prepare sonucu veya CI dosyası bu kabulleri sağlamaz.

## English

Separate source-only UI browsing, source preparation and render runtime readiness. Run the platform preflight and read runtime, source-manifest and dependency-plan results independently. Historical EULA-named error codes/flag refer to the reviewed LICENSE hash; original code is MIT and no third-party agreement is accepted. Preserve partial outputs, workspaces and receipts; never bypass source/lock checks or replay uncertain paid requests.

Use a new private local workspace for state-permission problems. Do not change OS security or PowerShell execution policy, delete locks, stop unrelated processes or reset permissions recursively. Source-only and first-run examples use different workspaces. Native Windows, clean-device and comprehensive visual acceptance are not established by compatibility/source checks. Share only sanitized fixed error codes when requesting support.
