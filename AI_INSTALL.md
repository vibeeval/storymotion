# AI ile yerel kurulum / AI-assisted local setup

Önce [README](README.md), [QUICKSTART](QUICKSTART.md), [CONFIGURATION](CONFIGURATION.md) ve hedef platform rehberini okuyun. Mac ve Windows aynı kaynak kodunu kullanır; runtime tarifleri platforma bağlıdır. Yalnız bu proje kökünde ve kullanıcının seçtiği workspace’te çalışın.

## Kapsam

- Önce kaynak ve komutları salt okunur inceleyin. Paneli incelemek için `python3 -B -m storymotion.dashboard --workspace work/local-studio --port 4402 --llm off --elevenlabs off` yolu vardır; Windows’ta `python -X utf8 -B` kullanılır. Panel açmak, render runtime hazır demek değildir.
- Mevcut kaynak, `work/`, veritabanı, medya ve receipt’leri koruyun. Bağlantılı yolları takip etmeyin, lock silmeyin, başka süreçleri durdurmayın. Gerekiyorsa yeni boş klasör seçin.
- Preflight indirme yapmaz. Kurulum indirmeleri ancak kullanıcının yetkisiyle `--allow-downloads` üzerinden başlatılır. OS aracı, global paket veya güvenlik/PowerShell policy değişikliği yapmayın.
- Özgün kod MIT’dir. Kurucu `--license-sha256` ile kullanıcının incelediği güncel LICENSE’ın tam hash’ini ister; eski `--accept-eula-sha256` aynı alanın alias’ıdır. Bunu ek MIT sözleşmesi veya üçüncü taraf anlaşması kabulü olarak anlatmayın; inceleme/kabul uydurmayın.
- Dağıtım manifesti, hash ve bağımlılık kontrollerini atlamayın. Kaynak değişikliğinden sonra incelenmiş commit ve yeniden manifest üretimi için [RELEASING](RELEASING.md) akışını izleyin; manifest bayraklarını elle ayarlamayın. Klonlanmış kaynakta kurulumun engellenmesi, MIT izinlerinin yokluğu anlamına gelmez. Eksik runtime ayrı raporlanır.
- HyperFrames varsayılandır. Remotion yalnız açık seçimle ve ayrı koşul incelemesiyle kurulur. Motoru sessizce değiştirmeyin.
- Sağlayıcılar kapalı başlar. Anahtar aramayın, keşfetmeyin veya kalıcı dosyaya yazmayın. BYOK bağlantısı ücretli çağrı izni değildir; tam girdi/provider/model/voice/bütçe için ayrı onay gerekir. Kurulum bu onayı vermez.
- Belirsiz indirme/sağlayıcı sonucunu otomatik tekrarlamayın; önce mevcut durum ve receipt’i inceleyin. Ek satın alma, kredi yükleme veya abonelik değişikliği bu kurulumun parçası değildir.

Sonuçta çalıştırılan komutları, kaynak/preflight/runtime durumlarını ve kalan engelleri ayrı bildirin. Kaynak testi, prepare, bir render veya CI yapılandırması; temiz kurulum, tüm şablonların görsel kabulü ya da başarılı yayın olarak sunulmaz. Kamuya açma 2 Kasım 2026 için planlıdır; bu dosya yayının gerçekleştiği iddiasını taşımaz.

## English

Read the linked setup/configuration documents first. Stay within the project and selected workspace; preserve all existing work. Source-only UI browsing and render readiness are separate. Do not install OS/global tools or change security policy. Downloads require authorization, and the reviewed LICENSE hash is an integrity record, not an extra MIT contract or third-party acceptance. Keep providers off unless explicitly requested; keys stay in the session and each paid request retains its own exact approval. Do not replay uncertain requests or infer publication/native/clean-device acceptance from source checks. Report performed checks and remaining blockers accurately.
