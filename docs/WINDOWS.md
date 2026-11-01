# Windows 10/11 x64

Mac ve Windows aynı StoryMotion kodunu kullanır; bu rehber Windows runtime ve dosya koşullarını açıklar. **Gerçek Windows bilgisayarında kurulum, tarayıcı ve render henüz doğrulanmış değildir.** Kaynak kontrolleri native kabul sayılmaz.

## Paneli kurulumdan önce inceleyin

Python 3.9+ x64 ile proje kökünde PowerShell açın:

```powershell
python -X utf8 -B -m storymotion.dashboard --workspace work/local-studio --port 4402 --llm off --elevenlabs off
```

Terminaldeki tam yerel bağlantıyı açın; oturum bilgisini paylaşmayın. Ctrl+C ile durdurun. Panel yerel workspace oluşturur; renderer indirmez ve sağlayıcıları kapalı tutar. Eksik runtime ile render ayrı engellenir.

## Render kurulumu

Windows 10/11 x64, Python 3.9+ x64, Node **22.23.2–22.x** ve npm gerekir. Kaynağı kendi hesabınıza ait yerel **NTFS** diskte yeni, normal bir klasöre klonlayın veya açın. Ağ paylaşımı, FAT/exFAT, junction/symlink, Windows ARM64/x64 emülasyonu ve 32-bit hedefler kapsam dışıdır. Mevcut kaynak ve çalışmalarınızın üzerine açmayın.

Proje kökünde:

```powershell
.\install.ps1 preflight
Get-Content -LiteralPath .\LICENSE
```

Preflight indirme veya ücretli çağrı yapmaz. İlk kurulum öncesi runtime `ok:false` olabilir. Kaynak manifesti/LICENSE için `source_install_ready`, seçili bağımlılıklar için `install_plan` alanlarını inceleyin. `customer_release_ready` ayrı kabul alanıdır ve MIT izninden farklıdır.

[MIT LICENSE](../LICENSE), [lisans kapsamı](../LICENSING.md) ve [üçüncü taraf koşullarını](../THIRD-PARTY-NOTICES.md) inceledikten ve indirmelere izin verdikten sonra:

```powershell
$licenseHash = (Get-FileHash -LiteralPath .\LICENSE -Algorithm SHA256).Hash.ToLowerInvariant()
.\install.ps1 install --allow-downloads --license-sha256 $licenseHash
.\install.ps1 start --port 4402
```

`--license-sha256` mevcut LICENSE hash’ini kaydeder; MIT’ye ek sözleşme veya üçüncü taraf anlaşması kabulü değildir. Eski `--accept-eula-sha256` aynı işlemin geriye uyumlu alias’ıdır. İndirme yetkisi ücretli içerik üretimine izin vermez. Kurulu launcher `work/first-studio` kullanır; kaynak-only örnekteki `work/local-studio` ayrı workspace’tir.

HyperFrames varsayılandır. Remotion ayrı eklentidir; koşullarını ayrıca inceleyip kurulum/preflight komutlarına açık `--engine remotion` ekleyin. Otomatik motor değişimi yapılmaz.

PowerShell `.ps1` çalıştırmıyorsa execution policy’yi değiştirmeyin. Aynı işlemler doğrudan Python ile yapılabilir:

```powershell
python -X utf8 -B .\tools\first_run.py preflight
python -X utf8 -B .\tools\first_run.py install --allow-downloads --license-sha256 LICENSE_SHA256
python -X utf8 -B .\tools\first_run.py start --port 4402
```

`LICENSE_SHA256` yerine incelediğiniz dosyanın küçük harfli hash’ini yazın. Bu belgeler komutların gerçek Windows’ta başarıyla çalıştırılmış olduğunu iddia etmez.

## Runtime, workspace ve güncelleme

`renderers/windows-media.json` sabit yayıncı URL’si ve SHA256 ile Gyan FFmpeg/ffprobe **9.0.2 x64** arşivini tanımlar. Açık kurulum izniyle indirilen dosyanın hash’i, PE/x64 biçimi ve sürümü kontrol edilir; arşiv ve lisansı `.runtime/windows-media` altında tutulur. Chrome for Testing **152.0.7977.30** kilitli tarayıcı kurucusuyla kurulur. Kaynak dağıtımında kurulu runtime binary’leri bulunmaz; macOS kaynak derleme tarifi Windows’ta kullanılmaz.

Yeni özel dizinler mevcut kullanıcı, SYSTEM ve Administrators ile sınırlı DACL kullanır; mevcut ACL’ler otomatik onarılmaz. Güvensiz sahiplik/izin, reparse yolu veya uygunsuz disk kurulumu durdurur. Yeni boş yerel workspace seçin; eski `work/` dizinini silmeyin. Kilitler LockFileEx, uygulamanın başlattığı süreçlerin iptali sahipli Job Object üzerinden yürür.

Arşiv güncellemesi için `.\update.ps1 stage` ve `.\update.ps1 verify` kullanılır; argümanlar [QUICKSTART](../QUICKSTART.md) içindedir. Yeni boş hedefe staging yapılır; eski kaynak/work otomatik taşınmaz, silinmez veya etkinleştirilmez. Kısmi sonucu yeniden denemeden inceleyin.

## English

Mac and Windows use one codebase. Windows targets 10/11 x64 with Python 3.9+ x64, Node 22.23.2–22.x/npm and an owner-controlled local NTFS directory. Browse with the source-only command first; rendering retains its own runtime gates. Use the PowerShell or direct Python first-run commands above without changing execution policy. The reviewed LICENSE hash is an integrity record, not an extra MIT contract or third-party acceptance; downloads and paid generation retain separate authorization.

The pinned FFmpeg/ffprobe and browser are installed only through explicit setup, not bundled in source. Private state uses DACLs, LockFileEx and owned Job Objects; existing ACLs are not repaired. Network shares, reparse paths, non-NTFS and unsupported architectures are refused. Native Windows installation/browser/render has not been performed; no clean-device or comprehensive visual acceptance is claimed. Public release is planned for 2 November 2026, not reported as completed.
