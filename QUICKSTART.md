# Hızlı başlangıç / Quick start

Mac ve Windows aynı kaynak ağacını kullanır. Komutları klonladığınız veya arşivden açtığınız projenin kökünde çalıştırın. Mevcut çalışmaların üzerine açmayın.

## 1. Paneli kaynak koddan açın

Python 3.9+ ile, renderer kurmadan paneli inceleyebilirsiniz:

```sh
python3 -B -m storymotion.dashboard --workspace work/local-studio --port 4402 --llm off --elevenlabs off
```

Windows PowerShell:

```powershell
python -X utf8 -B -m storymotion.dashboard --workspace work/local-studio --port 4402 --llm off --elevenlabs off
```

Terminaldeki tam bağlantıyı açın. Panel yalnız `127.0.0.1` üzerinde çalışır; bağlantıdaki oturum bilgisini paylaşmayın. Ctrl+C ile durdurun. `work/local-studio` bu örneğin yerel workspace’idir. Sağlayıcılar kapalıdır. Bu adım runtime indirmez ve render hazırlığı kanıtlamaz; eksik runtime render aşamasında ayrı engel olur.

## 2. Render önkoşullarını kontrol edin

Render kurulumu Python 3.9+, Node **22.23.2–22.x** ve npm ister. macOS Apple Silicon tarifi ayrıca mevcut Xcode Command Line Tools, clang, make ve zlib başlıkları içeren macOS SDK ister. Kaynaktan tam FFmpeg geliştirme tarifi mevcut `pkg-config` de gerektirir. Kurucu OS araçlarını kurmaz. Windows 10/11 x64, Python x64 ve yerel NTFS koşulları [Windows rehberinde](docs/WINDOWS.md) bulunur. Diğer platformlarda genel uyumluluk kontrolünden geçmek, doğrulanmış render kurulum tarifi olduğu anlamına gelmez.

macOS:

```sh
sh ./install.sh preflight
```

Windows:

```powershell
.\install.ps1 preflight
```

Bu kontrol indirme veya sağlayıcı çağrısı yapmaz. `ok` mevcut renderer runtime durumudur; ilk kurulumdan önce `false` olabilir. `source_install_ready` kaynak manifesti ve LICENSE bütünlüğünü, `install_plan` seçili bağımlılık planını gösterir. `customer_release_ready` ayrı kapsamlı kabul alanıdır; `false` olması tek başına kaynak kullanımını yasaklamaz veya MIT iznini geri almaz. Kaynak dosyalarını değiştirirseniz manifest güncelliğini kaybeder ve kurucu durabilir. İncelenmiş commit ve manifest üretimi için [RELEASING](RELEASING.md) akışını izleyin; manifest bayraklarını elle değiştirerek kontrolü atlamayın.

## 3. İncelediğiniz kaynak için runtime kurun

[LICENSE](LICENSE), [Lisans kapsamı](LICENSING.md) ve [Üçüncü taraf bildirimlerini](THIRD-PARTY-NOTICES.md) inceleyin. İndirmelere izin verdiğinizde, yerel LICENSE dosyasının SHA256 değerini kullanın.

macOS:

```sh
shasum -a 256 LICENSE
sh ./install.sh install --allow-downloads --license-sha256 LICENSE_SHA256
```

`LICENSE_SHA256` yerine ilk komutun verdiği 64 karakterlik küçük harfli değeri yazın.

Windows PowerShell:

```powershell
$licenseHash = (Get-FileHash -LiteralPath .\LICENSE -Algorithm SHA256).Hash.ToLowerInvariant()
.\install.ps1 install --allow-downloads --license-sha256 $licenseHash
```

`--license-sha256` incelenen mevcut LICENSE’ın hash’ini kaydeder; MIT’ye ek sözleşme veya üçüncü taraf anlaşması kabulü değildir. Eski `--accept-eula-sha256` bayrağı aynı işlemin geriye uyumlu adıdır. `--allow-downloads` bağımlılık ve tarayıcı indirmelerine verilen ayrı izindir; ücretli içerik üretimine izin vermez. Kurulum proje içindeki sabit bağımlılıkları kullanır; macOS ffprobe’u kaynaktan derler, Windows sabit medya arşivini kullanır. Kaynak dağıtımında kurulu runtime binary’leri bulunmaz.

HyperFrames varsayılandır. Remotion istiyorsanız kendi lisans koşullarını ayrıca inceleyip preflight/install komutlarına açıkça `--engine remotion` ekleyin. Otomatik motor geçişi yapılmaz.

## 4. Kurulu runtime ile açın

macOS:

```sh
sh ./install.sh start --port 4402
```

Windows:

```powershell
.\install.ps1 start --port 4402
```

Bu yol runtime kontrolünü geçmek zorundadır ve sabit `work/first-studio` workspace’ini kullanır. 1. adımdaki `work/local-studio` ayrı bir workspace’tir; işler aralarında otomatik taşınmaz. Sağlayıcılar yine kapalı başlar. Panelden AccountPack ve şablon seçin; doğrulama, kaynak hazırlama ve renderi ayrı adımlarda başlatın. Sesli veya model destekli üretim için [BYOK ayarlarını](CONFIGURATION.md) okuyun.

## Kaynak güncellemesi

Git kullanıyorsanız kaynak değişikliklerinizi ve özel `work/` verilerinizi koruyun; yeni sürümü ayrı checkout’ta incelemek mevcut işlerinizi değiştirmez. Kaynak arşivi güncelleme aracı da yeni boş hedef kullanır. Yayınlanan arşivin bağımsız doğruladığınız SHA256 değeriyle:

```sh
sh ./update.sh stage --archive release.zip --destination new-source --sha256 ARCHIVE_SHA256 --preserve-workspace work/local-studio
sh ./update.sh verify --archive release.zip --destination new-source --sha256 ARCHIVE_SHA256 --preserve-workspace work/local-studio
```

Windows’ta aynı argümanlarla `.\update.ps1` kullanın. `new-source` mevcut kaynak/work dışında yeni boş hedef olmalıdır; örnek yolları kendi düzeninize göre değiştirin. Stage kurulum, aktivasyon veya veri taşıma yapmaz. Belirsiz sonuçta yeniden stage etmeden önce verify kullanın.

## English

Browse the local panel with the source-only commands in step 1; Python 3.9+ is sufficient for this entry point, and providers remain off. Rendering is checked separately. Runtime setup requires Node 22.23.2–22.x/npm and the platform prerequisites above; Windows details are in its linked guide. Run preflight first, review LICENSE and third-party notices, then explicitly authorize downloads with the current LICENSE hash. The historical EULA-named flag remains an alias; no additional MIT contract or third-party agreement is implied. HyperFrames is default; Remotion requires explicit selection. The first-run launcher uses `work/first-studio`, while the source-only example uses `work/local-studio`. Preserve existing work and inspect uncertain installation/update results before retrying. These instructions do not assert native Windows or clean-device validation.
