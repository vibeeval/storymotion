# Destek / Support

Sorunları önce [TROUBLESHOOTING](TROUBLESHOOTING.md) ve platform rehberindeki yerel kontrollerle ayırın. Kamuya açık depo yayımlandığında, sorun takibinde yalnız gizli bilgi içermeyen bir hata kaydı paylaşın. Bu kaynak adayı belirli bir yanıt süresi veya sürekli destek taahhüt etmez.

Bir hata kaydında şunlar yeterlidir:

- StoryMotion sürümü/kaynak commit’i, OS sürümü ve mimari.
- Kaynak-only panel, runtime kurulumu, kaynak hazırlama veya render aşamalarından hangisinde durduğu; seçilen motor.
- Gizli değerlerden arındırılmış komut, sabit hata kodu ve beklenen davranış.
- İndirme veya ücretli istek başlatılıp başlatılmadığı; sonuç belirsizse bu durum.

API anahtarı, ilk oturum bağlantısı/token, özel ses kimliği, özel medya, müşteri verisi, tüm `work/` dizini veya kabul/approval receipt’i paylaşmayın. Loglar otomatik yüklenmez. Destek için önce yerel logu inceleyin, yalnız sabit hata kodunu aktarın.

Kurulum/update kısmi kaldıysa mevcut sonucu inceleyin; eski kaynak, workspace ve receipt’leri koruyun. Yetkisiz yeni indirme, ücretli tekrar, başka süreci durdurma veya OS güvenlik ayarı değişikliği hata çözüm adımı değildir. `RUNTIME_NOT_READY` kaynak hazırlamanın tamamlanmış olmasından ayrı olabilir. Mac’te `SOURCE_FFMPEG_PKG_CONFIG_REQUIRED`, mevcut kaynaktan FFmpeg tarifi için `pkg-config` önkoşulunun bulunmadığını bildirir; araç otomatik OS kurulumu yapmaz.

Özgün kod için [MIT](LICENSE), üçüncü taraflar için [bildirimler](THIRD-PARTY-NOTICES.md) geçerlidir. Teknik destek sonucu native Windows, temiz cihaz veya kapsamlı görsel kabul sertifikası sayılmaz.

## English

Use [Troubleshooting](TROUBLESHOOTING.md) first. Once the public repository is published, report a sanitized issue with source version/commit, OS/architecture, selected engine, failing stage, safe command/error code and whether a download or paid request was started. No response time or continuous support is promised.

Do not share keys, session URLs/tokens, private voice identifiers/media, customer data, whole workspaces or approval receipts. Logs are local, not automatically uploaded. Preserve partial results and inspect uncertain outcomes before retrying. Source preparation, runtime installation and rendering are different stages. Original code is MIT; third-party conditions and platform/visual verification remain separate.
