# Lisans kapsamı / Licensing scope

StoryMotion katkıcıları tarafından lisanslanan özgün kodu ve özgün proje belgeleri [MIT License](LICENSE) kapsamındadır. Bu izin kullanım, değişiklik, dağıtım, alt lisanslama ve yazılım kopyalarının satışını kapsar. MIT'nin telif ve izin bildirimi korunur. Bu aday, eski özgün kod EULA'sındaki yazılımı yeniden satma yasağını taşımaz.

MIT izni, aşağıdaki ayrı materyalleri yeniden lisanslamaz; onların telif sahiplerini, koşullarını veya eksik köken kanıtlarını değiştirmez. Paket metadata'sındaki `MIT`, StoryMotion'un özgün paket kodunu tanımlar; bütün bağımlılıkların MIT olduğu anlamına gelmez.

| Materyal | Ayrı kapsam ve korunacak kayıt |
|---|---|
| `vendor/gsap.min.js` | GSAP 3.15.0; özgün GreenSock telif başlığı ve GSAP Standard License korunur. Standart lisansın rekabet eden görsel animasyon oluşturucularına ilişkin koşulları ayrıca geçerlidir; mimari kapsam ve sınırlamalar `docs/GSAP-SCOPE.md` içinde; bu aday sınırsız görsel-builder izni alındığını iddia etmez. |
| `vendor/fonts/*.woff2` | Schibsted Grotesk, OFL-1.1; `vendor/fonts/LICENSE-OFL-schibsted-grotesk.txt` ve Schibsted-Grotesk Project Authors telifi korunur. Font dosyaları MIT'ye çevrilmez. |
| `liquid-merge`, `bauhaus-modules`, `pixel-journey` içindeki kayıtlı teknik uyarlamalar | Vincentwei1021/mg-styles-15, kayıtlı commit ve sınırlandırılmış kod kapsamı `catalog/style-adapters.json` içinde; Copyright (c) 2026 Vincentwei1021 ve tam MIT bildirimi `vendor/notices/mg-styles-15-MIT.txt` içinde korunur. Bu üçüncü taraf telifi StoryMotion katkıcılarına mal edilmez. |
| Diğer üçüncü taraf kod ve bildirim kopyaları | `vendor/licenses/`, `docs/notices/` ve [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md) kendi koşullarını korur. Bildirim eksikleri veya kaynak sağlama yükümlülükleri özgün kodun MIT seçimiyle tamamlanmış sayılmaz. |
| HyperFrames ve diğer indirilen paketler | Kilitli paketler ayrı lisanslarına tabidir. `docs/DEPENDENCY-LOCK.json` envanterdir; bütün paketlerin tam lisans incelemesi veya uygunluk onayı değildir. HyperFrames metadata'sı Apache-2.0 bildirir; bu MIT'ye dönüştürülmez. |
| İsteğe bağlı Remotion | `optional/remotion/` içindeki StoryMotion paket tanımı MIT kapsamındadır; indirilen Remotion kodu ve compositor'lar ayrı Remotion koşullarını korur. Bu metadata değişikliği Remotion'u MIT yapmaz veya kullanıcı adına sözleşme kabul etmez. |
| Codec, tarayıcı ve diğer çalışma zamanı binary'leri | Bu kaynak adayına dahil değildir. Yetkili kurulumda indirilen FFmpeg/ffprobe, Chrome ve native/WASM bileşenlerinin kendi lisans, bildirim ve varsa karşılık gelen kaynak koşulları vardır. |
| Programmatik nötr rig kaynağı | `renderers/neutral-rig.json` projenin özgün vektör kodudur; tarihli proje kaydı ve birebir kaynak hash’i `renderers/neutral-rig-origin.json` içinde. Güncel özgün kaynak MIT izni uygulanır; başka bir tarihsel insan yaratıcı, üçüncü taraf sanat veya ses hakkı iddia edilmez. |
| PNG, sessiz WAV ve sessiz MP3 teknik örnekleri | Güncel dosyalar proje tariflerinden dış medya girdisi olmadan yeniden üretildi; MIT kapsamındaki özgün teknik örneklerdir. `fixtures/GENERATION.json` gerçek tarih, tarif/encoder/output hash’leri ve sıfır-PCM kontrollerini taşır. Eski baytlarla eşleşme, eski yaratıcının kimliğini kanıtlamaz. MP3 sessizliktir; seslendirme veya klonlanmış konuşmacı değildir. |
| Kullanıcının medya, ses, referans ve AccountPack girdileri | Bu aday onlar için hak vermez. Gerekli haklar girdi sahibinden ayrıca sağlanır. |

`fixtures/raster/RIGHTS.md` güncel, kayıtlı sıfır-girdili üretimi açıklar; önceki örneklerin hash/köken kayıtları `fixtures/PROVENANCE.json` içindeki tarihsel alanlarda ayrılır. Güncel kod izni LICENSE'dır. Yeni üretim kaydı, tarihsel insan yaratıcılığı veya üçüncü taraf hakları konusunda yeni bir iddia değildir.

Bu dosya yeni bir onay, yayın veya native test makbuzu değildir. API anahtarları, ücretli sağlayıcı istekleri, indirmeler ve üçüncü taraf sözleşmeleri ayrı işlem kapsamlarıdır. Mevcut teknik/kurulum kontrolleri, özgün kodun kullanım veya dağıtım haklarına ek bir yazılım lisansı kısıtı olarak sunulmaz.

## English

Original StoryMotion code and original project documentation licensed by StoryMotion contributors are offered under the [MIT License](LICENSE), including permission to modify, distribute, sublicense and sell copies while retaining its notice. The previous original-code resale restriction is not part of this candidate's grant.

Third-party software, retained notices, OFL fonts, the attributed MIT adaptations, runtime downloads and caller assets retain their separate terms. The package-level MIT field describes StoryMotion's original code, not every dependency or asset. The neutral rig has an exact dated original-project source record. Current technical fixtures have fresh zero-input generation receipts under the project MIT grant; these do not identify historical media creators. Incomplete third-party evidence remains separate. Nothing here reassigns another author's copyright, accepts an agreement for a user, certifies native execution or publishes the candidate. See [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md) and [docs/RIGHTS.md](docs/RIGHTS.md).
