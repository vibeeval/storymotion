# Sık sorulan sorular / FAQ

**Mac ve Windows ayrı ürünler mi?** Aynı kaynak kodunu kullanırlar. Runtime kurulum tarifi ve dosya güvenliği platforma göre ayrılır. Windows 10/11 x64 yolu vardır; gerçek Windows kurulumu, tarayıcı ve render çalıştırması henüz doğrulanmış değildir. macOS Apple Silicon runtime tarifi, temiz Mac kurulumu garantisi vermez.

**Panel için renderer kurmak gerekiyor mu?** Kaynak koddan providers-off panel açılabilir; komutlar [QUICKSTART](QUICKSTART.md) içindedir. Eksik runtime render başlatmayı ayrıca engeller. Kaynak hazırlama başarıyla bitmiş olsa bile MP4 üretilmiş sayılmaz.

**HyperFrames mi, Remotion mı?** HyperFrames varsayılandır. Remotion ayrı lock’a sahip isteğe bağlı eklentidir; `--engine remotion` ile açıkça seçilir ve kendi lisans koşulları ayrı incelenir. Eksik motor yerine otomatik başka motor kullanılmaz.

**Lisans neye izin veriyor?** Özgün StoryMotion kodu ve özgün proje belgeleri MIT kapsamındadır. MIT bildirimini koruyarak kullanabilir, değiştirebilir, dağıtabilir, alt lisanslayabilir ve yazılım kopyalarını satabilirsiniz. Eski özgün kod yeniden satış kısıtlaması bu adayın MIT lisansı değildir. Üçüncü taraf kod, font, medya ve runtime hakları ayrıca değerlendirilir: [LICENSE](LICENSE), [LICENSING](LICENSING.md), [THIRD-PARTY-NOTICES](THIRD-PARTY-NOTICES.md).

**Kurucu neden lisans hash’i istiyor?** `--license-sha256`, incelediğiniz güncel LICENSE dosyasını kaynak manifestiyle eşleştiren mevcut kurulum kaydıdır. MIT’ye yeni bir sözleşme şartı eklemez ve üçüncü taraf anlaşması kabul etmez. Eski `--accept-eula-sha256` bayrağı geriye uyumlu alias olarak kalır. `--allow-downloads` ayrı indirme iznidir.

**API ücreti oluşur mu?** Yerel panel ve deterministik kaynak hazırlama model çağırmaz. Sağlayıcılar kapalı başlar. İsteğe bağlı canlı metin/ses işlemleri kendi API anahtarınızı, sağlayıcı hesabınızı ve her tam isteğin girdi/model/ses/bütçe onayını gerektirir. API servis ücretleri ayrıdır; kaynak kod API kredisi sağlamaz. Bağlantı kurmak üretim onayı değildir. Belirsiz sonuç otomatik yeniden gönderilmez.

**Hazır bir içerik yöntemi veya ses dahil mi?** Nötr AccountPack teknik bir başlangıçtır; tamamlanmış içerik üretim yöntemi sunmaz. Kendi `procedures` adımlarınızı ve tercihlerinizi tanımlayın. Ses seçimi ve medya haklarını ayrıca çözün; anahtar veya kişisel ses kimliği paketlenmez.

**Yeni AccountPack için kod yazmak gerekiyor mu?** Desteklenen sözleşmeler içinde tam örnek JSON’u kopyalayıp benzersiz kimliklerle uyarlayabilirsiniz. `work/accountpacks/` yolu ve alanlar [CONFIGURATION](CONFIGURATION.md) içindedir. JSON yeni renderer veya keyfi çalıştırılabilir kod eklemez.

**Kaç şablon var; hepsi tamamlanmış mı?** Katalog 7 temel + 84 development olmak üzere 91 şablon ve 182 örnek girdi içerir. 89’unda kısmi alan editörü vardır; `tile-quest-state` ve `toon-dialogue-blocking` JSON ile düzenlenir. Development kaydı, tüm platformlarda veya her medya girdisiyle görsel/native kabul anlamına gelmez. 14 medya şablonunda kendi uygun medyanızı sağlamalısınız.

**Güncelleme işlerimi taşır mı?** Hayır. Kaynak staging yeni boş dizine yapılır; eski kaynak/work ezilmez veya otomatik taşınmaz. Kaynak-only panel örneği `work/local-studio`, first-run launcher ise `work/first-studio` kullanır. Bunlar ayrı çalışma alanlarıdır.

**Proje yayımlandı mı?** Bu aday için kamuya açma 2 Kasım 2026’ya planlanmıştır; yayın gerçekleşmiş gibi sunulmaz. Bir kaynak testi, manifest veya çalışma dosyası; native Windows, temiz kurulum, tüm şablonların görsel kabulü veya CI green kanıtı değildir.

## English

Mac and Windows share one codebase; platform runtime recipes differ. HyperFrames is default and Remotion is optional. You can browse the local source-only dashboard with providers off before installing a renderer. Native Windows and clean-device validation remain unverified.

Original code/documentation are MIT, permitting modification, redistribution and software-copy sales with the required notice. Third-party components and media retain separate terms. The installer’s LICENSE hash records the reviewed file; it adds no MIT contract and accepts no third-party agreement. Downloads and every paid generation request require their separate authorizations.

The neutral AccountPack contains no complete production method. Define your own workflow and use your own keys and rights-cleared inputs. The catalog has 91 templates/182 examples; source preparation is separate from MP4 and visual acceptance. Workspaces are local and updates do not migrate them automatically. Public release is planned for 2 November 2026, not reported as completed.
