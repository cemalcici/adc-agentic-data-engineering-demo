# Demoyu sunmak

Buradaki her adım ezberden değil, bu belgeyi takip ederek çalıştırıldı. Bir adım
yazdığını üretmiyorsa, bu sistemde olduğu kadar belgede de bir kusurdur —
[Ters giderse](#ters-giderse) bölümüne bakın.

**Şekli:** yaklaşık on iki dakika demo, artı sorular. Üç ekran: konsol, terminal
ve Phoenix.

---

## Demodan önce

### 1. Başlangıç durumuna sıfırlayın

Üç adım, ve herhangi birini atlamak sizi demonun çalışmadığı bir yerden
başlatır.

```bash
git checkout dbt/          # önceki koşunun uyguladığı düzeltmeyi at
docker compose down -v     # sürüklenmiş kaynağı ve veritabanlarını at
docker compose up -d       # her şeyi yeniden kur ve başlat
```

Neden üç adım: sistemin kendi iyileşmesi **`dbt/` içine bir düzeltme yazar ve
orada bırakır** — düzeltme işe yaramamış olsa bile (ADR-0025). Ve drift
tetikleyicisi kendini geri alamaz (ADR-0014). Yani onarılmış bir transformation
ile sürüklenmiş bir kaynak *çalışan* bir pipeline demektir; demonun kıracak bir
şeyi kalmaz.

Soğuk başlangıç imaj önbelleği sıcakken yaklaşık **iki dakika**, ilk seferde
yaklaşık altı dakika sürer çünkü imajları kurar. Bunu seyirci karşısında
başlatmayın.

### 2. Gerçekten hazır mı, bakın

```bash
./verify-stack.sh
```

**19 passed, 0 failed** bekleyin. İki satır diğerlerinden önemli:

- `source identifier is 'customer_id' (no drift applied)` — demo kırılmamış
  durumda başlıyor. `cust_id` yazıyorsa sıfırlama olmamış demektir.
- `endpoint: ok (...) — endpoint answered` — dil modeli cevap verdi. Makinenin
  dışındaki tek bağımlılık bu, ve bunu insanların karşısında değil burada
  öğrenirsiniz.

### 3. Üç ekranı açın

| Ekran | Nerede | Niçin |
| --- | --- | --- |
| Konsol | http://localhost:8501 | Demo burada geçiyor |
| Terminal | bu deponun içinde herhangi bir yer | Bir komut, bir kez |
| Phoenix | http://localhost:6006 | Sonra açılacak, tek bir an için |

Phoenix'i **Projects** sayfasında bırakın. Henüz bir trace açmayın — onun anı
var.

### 4. Yedeği elinizin altında tutun

Başarılı bir koşunun kaydı, aramadan bulabileceğiniz bir yerde. Model internet
üzerinden geliyor ve yanlış anda yavaş kalabilir. Canlı görünen bir şey değil,
bilerek bir kayıt — [Ters giderse](#ters-giderse) bölümüne bakın.

---

## Demo

### 1. Kimsenin kaygılanmadığı bir pipeline

**Gösterin:** konsol. `PIPELINE HEALTHY` yazıyor.

> Bu küçük bir veri hattı. Beş dakikada bir yukarıdaki sistemden müşteri
> kayıtlarını kopyalıyor ve iş biriminin okuduğu bir tabloyu yeniden kuruyor.
> Yeşil, ve kimse onu düşünmüyor.

Bir an ekranda bırakın. Seyircinin kırmızıyı hissetmesi için önce yeşili görmüş
olması gerekiyor.

### 2. Yukarıdaki ekip bir kolonun adını değiştiriyor

**Yapın:** terminalde,

```bash
docker compose --profile drift run --rm --build drift
```

> Şirketin başka bir yerinde bir ekip kendi veritabanlarında bir kolonun adını
> değiştiriyor. `customer_id`, `cust_id` oluyor. Aşağıda birinin buna bağlı
> olduğundan haberleri yok — ve bu dikkatsizlik değil, işler böyle yürüyor.

Komut neyi değiştirdiğini ve kaç kaydın bu kolonu taşıdığını yazdırır.

### 3. Kırılıyor, ama veri gayet iyi görünüyor

**Gösterin:** konsol. Yaklaşık beş dakika içinde `PIPELINE FAILING` oluyor.

Zamanlamayı beklemek istemezseniz http://localhost:8080 adresindeki Airflow
arayüzünden tetikleyebilirsiniz — ama beklemenin bir değeri var: bu gerçek
aralık, ve öyle söylemek "anında oluyor" demekten dürüst.

> Şimdi ilginç kısım. Pipeline başarısız — ama iş biriminin okuduğu tablo hâlâ
> yerinde, hâlâ dünkü satırlarla dolu, hâlâ her sorguya cevap veriyor. *Veriye*
> bakan biri her şeyin yolunda olduğunu söylerdi. Sessiz pipeline arızası tam
> olarak böyle görünür — ve bu konsolun neden veriyi değil koşuların durumunu
> okuduğunun sebebi bu.

Demonun senaryosuz en güçlü anı burası. Tasarlanmadı, sistemi kurarken ortaya
çıktı.

### 4. Bunu kimse bildirmedi

**Gösterin:** konsol, bir dakika kadar sonra. Teşhis kendiliğinden beliriyor.

> Kimse kayıt açmadı. Ajan koşunun başarısız olduğunu fark etti, hatayı okudu,
> gidip yukarıdaki kaynakta şu anda ne olduğuna baktı ve neyin değiştiğini
> çıkardı.

Açıklamayı sesli okuyun. Sesli okunmak için yazıldı.

### 5. Bir iş arkadaşının değişikliği gibi inceleyin

**Gösterin:** teşhisin altındaki önerilen değişiklik.

> Değiştirmek istediği şey bu. Tek satır. Bunu bilerek dosya olarak değil fark
> olarak gösteriyoruz, çünkü bir iş arkadaşınızın işini de böyle incelerdiniz.
>
> Ve bunu zaten başarıyla derledi — gerçek veriye karşı, projenin tamamıyla,
> pipeline'ın kullandığı dbt'nin aynısıyla. Yani önünüzdeki soru "bu derleniyor
> mu" değil. "Doğru şeyi mi söylüyor" — ki bir insanın yapması gereken kısım da
> bu.

Sayfanın tazelemeyi bıraktığına dikkat edin. Bir karar açıkken bunu bilerek
yapıyor: siz okurken altınızda hiçbir şey oynamasın diye.

### 6. Nasıl karar verdi, ve ne tuttu

**Yapın:** **How did the agent arrive at that?** bağlantısına tıklayın. Phoenix
bu incident'ın trace'i üzerinde açılır.

Bunu sunmadan önce aşağıdaki [Phoenix'i okumak](#phoenixi-okumak) bölümüne
bakın — en yabancı gelmesi muhtemel ekran bu.

> Attığı her adım burada. Arızayı fark etti, log'u aldı, canlı şemayı inceledi,
> modeli çağırdı, bir düzeltme önerdi, o düzeltmeyi derledi, kaydetti.
>
> Ve şurada durmaya değer: model çağrısına tıklayın, gönderilen prompt'u ve
> gelen cevabı olduğu gibi görüyorsunuz. Burada kara kutu olan hiçbir şey yok.
>
> Bütün incident birkaç saniye sürdü ve bir centin çok altında kaldı.

### 7. Karar

**Yapın:** konsola dönün. **Approve**'a tıklayın.

> Şu ana kadar hiçbir şey yazılmadı. Buraya kadarki her şey okumak ve akıl
> yürütmekti. Bu tıklama, harekete geçmesine izin veren tek şey — ve harekete
> geçebilmesinin tek yolu. Bu sistemde projeye bunsuz yazan bir yol yok.

### 8. Yeniden yeşil, ve kimse bir şey yazmadı

**Gösterin:** konsol. Düzeltmenin uygulandığını, sonra bir koşunun başladığını,
sonra `PIPELINE HEALTHY` olduğunu ve incident'ın çözüldü olarak kaydedildiğini
gösterir. Bir dakikadan kısa sürer.

> Dosyayı yazdı, bir pipeline koşusu başlattı ve *o* koşuyu izledi — sonradan
> biten herhangi birini değil — ve pipeline düzeldi.
>
> Kimse bir şey yazmadı. Biri tek satırlık bir değişikliği okudu ve evet dedi.

### 9 (isteğe bağlı). "Hayır" ne yapıyor

Vakit varsa göstermeye değer, çünkü insanların şüphe ettiği iddia bu.

Sıfırlayın, tekrar drift uygulayın ve bu kez **Reject**'e basın. Pipeline
kırmızı kalır, transformation projesine dokunulmaz, ve geçmiş sizin
reddettiğinizi kaydeder. Sistemde ret işleyen hiçbir kod yok — reddetmek,
ajanın gidecek bir yeri olmadığı için çalışıyor.

Vakit darsa göstermek yerine bunu söyleyin.

---

## Phoenix'i okumak

Bu ekranı hiç kullanmamış biri için yazıldı. Buradan dört şeye ihtiyacınız var.

**Nereye düşersiniz.** Projects sayfası iki proje listeler:
`self-healing-pipeline` bu demonun, `default` Phoenix'in kendisinin ve boş.
Birincisine girin.

**Spans değil, Traces.** **Traces** sekmesi her ajan geçişi için tek satır
verir; istediğiniz bu. **Spans** sekmesi her geçişin her adımını tek tek
listeler, ve ajan yirmi saniyede bir yokladığı için bunların çoğu yapacak bir
şey bulamamış geçişlerdir. Onların duvarıyla açmak istediğiniz izlenim değil.

**Asıl mesele span ağacı.** Bir trace açtığınızda ortada şunu görürsünüz:

```
agent_pass → detect_failure → fetch_failure_log → inspect_schema
           → diagnose → ChatOpenAI
           → propose_fix → ChatOpenAI → validate_candidate
           → record_proposal
```

Bu ağaç, "nasıl karar verdi" sorusunun *cevabının kendisi*. Anlatmak yerine
gösterin.

**Bir `ChatOpenAI` span'ine tıklayın.** Gönderilen prompt'un ve gelen cevabın
tamamını gösterir. Seyircinin beklemediği kısım burası, ve raporun incelenebilir
ajan davranışı argümanını en doğrudan destekleyen kısım da bu.

**Sayılar.** Trace başlığı gecikmeyi, toplam maliyeti ve token sayısını taşır.
Ölçülen bir incident yaklaşık altı buçuk saniye ve bir centin çok altındaydı.
Proje başlığı ise oturum boyunca toplamları taşır. Maliyet rakamını bilerek
ekrana koyun — "bunu çalıştırmak ne tutuyor" size sorulacak bir soru, ve rakamın
görünür olması söylemekten iyidir.

---

## Ters giderse

### Bir şeyin gerçekten ters gittiğine karar vermeden önce ne kadar beklenir

| Adım | Normal | Ters |
| --- | --- | --- |
| Drift sonrası kırmızıya dönme | 5 dakikaya kadar (zamanlama) | 6 dakikayı geçerse |
| Teşhisin belirmesi | koşu başarısız olduktan sonra 1 dakikanın altında | 3 dakikayı geçerse |
| Düzeltmenin uygulanıp yeşile dönmesi | 1 dakikanın altında | 3 dakikayı geçerse |

Sabitlenmiş model üzerinde ölçüldü. Daha yavaş bir model ortadaki satırı uzatır
— önceki bir model aynı iş için üç dakikaya yakın sürüyordu; runbook'un varsaymak
yerine bakmayı söylemesinin sebebi bu.

### Hiçbir şey belirmedi

Konsol *"Nothing has been recorded for this failure yet"* diyor — ajan
düşünüyorken de, çalışmıyorken de. İkisini ayırt edemiyor; bu bilinçli bir sınır,
gözden kaçmış bir şey değil. Hangisi olduğuna siz bakın:

```bash
docker compose logs --tail 20 agent
```

- `watching customer_elt every 20s` ve sonrasında bir şey yoksa — hayatta ve
  çalışıyor.
- Hiç yeni satır yoksa ya da konteyner gitmişse — yeniden başlatın:
  `docker compose up -d agent`.

### Model yavaş kalıyor ya da kullanılamaz bir şey döndürüyor

Ajan derlenmeyen kendi çıktısını iki kez düzeltir, dolayısıyla kötü bir ilk
cevap çoğu zaman kendi kendine toparlanır — olursa bunu sesli söylemeye değer,
çünkü raporun öne sürdüğü iddialardan biri.

Dört dakika içinde toparlamazsa **durun ve kayda geçin**. Açıkça söyleyin:

> Model bugün cevap vermiyor. Şimdi daha önceki bir koşuyu göstereceğim — aynı
> sistem, aynı senaryo.

Hazır bir sonucu canlı ekrana yerleştirmeye çalışmayın. Bunun için bilerek bir
mekanizma yok (ADR-0028): prova edilmiş bir cevabı ajanın kendi cevabıymış gibi
sessizce gösterebilen bir demo, kendi konusunun aleyhine argüman üretir.

### Pipeline kırmızıya dönmedi

Neredeyse her zaman sıfırlamadır. Bakın:

```bash
git status --short dbt/     # boş olmalı
./verify-stack.sh           # başlamadan önce 'no drift applied' demeli
```

### Phoenix açılmıyor

Onun yerine konsolu gösterin ve trace'in sonradan da bakılabilir olduğunu
söyleyin. Ajan ona bağlı değil — izler düşer, başka hiçbir şey değişmez.

---

## Size sorulacak sorular

### "Önceki incident'ları hatırlıyor mu?"

Hayır, bilerek. Her incident sıfırdan teşhis edilir: daha önceki bir sonucu
yeniden kullanmak yerine transformation'ı yeniden okur ve canlı kaynağı yeniden
inceler (ADR-0020). Güvenli olan varsayılan bu — hatırlayan bir ajan, değişmiş
bir sistem hakkında kendinden emin biçimde yanılabilir.

Hafıza gerçek ve iyi anlaşılmış bir genişleme: çözülmüş incident'ları teşhis
adımına geri beslemek. Burada yok, çünkü demonun sonra savunmak zorunda kalacağı
yeni bir arıza biçimi ekliyor.

### "Planlama yapıyor mu, yoksa sıra sabit mi?"

Sabit. Adımlar ajanın içinden geçtiği bir graf, kendi kurduğu bir plan değil.

Bu, raporun anlattığı planlayıcı/uygulayıcı ayrımının uygulayıcı yarısı — ve
hasar yarıçapı küçük olan yarısı. Planlayan bir ajan ne yapılacağına karar
verir; bu ajan, bilinen belirli bir sorunun neye ihtiyacı olduğuna karar verir.
Bir pilot için doğru sıralama bu.

### "Neden MCP değil?"

Airflow ve Postgres'e sıradan istemci kütüphaneleriyle ulaşıyor (ADR-0019). MCP
yükselen standart, ama iki aracı olan tek bir ajan için gösterilebilir bir
karşılığı olmadan iki servis ve bir hata ayıklama katmanı ekler. Araç katmanını
MCP sunucularıyla değiştirmek grafı değiştirmezdi — doğal bir sonraki adım bu, ve
bir eksiklik değil bilinçli bir tercih.

### "Çalıştırmak ne tutuyor?"

Şu an sabitlenmiş modelde incident başına bir centin altında, Phoenix'te trace
başına görünür. Demonun tamamı — bir teşhis, bir öneri, bir doğrulama derlemesi —
birkaç cent. Model seçimi üç modelin aynı arıza üzerinde ölçülmesiyle
sabitlendi; karşılaştırmanın kaydı geliştirme deposunda tutuluyor.

### "Ajan yanılırsa ne olur?"

Üç ayrı cevap, ve birbirlerinden farklılar:

- **Derlenmeyen bir şey yazarsa** — size hiç ulaşmaz. Ajan her adayı sunmadan
  önce derler, kendini iki kez düzeltir, olmazsa incident'ı bir açıklamayla
  `unfixable` olarak kapatır (ADR-0022).
- **Derlenen ama yanlış bir şey yazarsa** — sizin incelemeniz tam da bunun için.
  Doğrulama çalıştığını kanıtlar, doğru şeyi söylediğini değil; ve sistem aksini
  iddia etmiyor.
- **Düzeltme uygulanır ve pipeline yine de düzelmezse** — incident "uygulandı,
  düzelmedi" olarak biter, diğer bütün sonlanmalardan ayrı, ve düzeltme sessizce
  geri alınmaz, diskte kalır (ADR-0025). Geri almak, ikinci bir onay olmadan
  ikinci bir yazma olurdu.

### "Düzeltmeleri doğrudan uygulayamaz mı?"

Uygulayabilirdi, ve bu sistem bilerek bir aşama geride duruyor. Rapor kademeli
otonomiyi anlatıyor — izle, öner, korumalı değişiklik, otonom — ve burası
*öner artı onaylanmış değişiklik* aşamasında; raporun pilot için önerdiği aşama
da bu. Kapıyı kaldırmak için gereken her şey mevcut; eksik olan güven, ve o da
önce bu aşamada çalıştırarak kazanılıyor.

---

## Hâlâ çalıştığını doğrulamak

```bash
./verify-stack.sh    # yığının hazır olduğuna dair 19 doğrulama
./smoke-tests.sh     # demonun dayandığı iki iddia
```

`smoke-tests.sh` drift'in pipeline'ı gerçekten kırdığını ve onaylanmış bir
düzeltmenin onu gerçekten düzelttiğini kontrol eder. İki doğrulama da dil modeli
çağırmaz, dolayısıyla ikisi de "model bugün farklı cevap verdi" diye başarısız
olamaz — ve ikisi de ajanın açıklamasının iyi okunup okunmadığı ya da
değişikliğin bir bakışta anlaşılacak kadar küçük olup olmadığı hakkında hiçbir
şey kanıtlamaz. Onlar provanın işi.

Çalıştırmadan önce bilinmesi gereken iki şey: ajan yanı başında koşuyor ve
testlerin yol açtığı arızayı teşhis ediyor, dolayısıyla bir koşu hiç değil bir
centin küçük bir kesri kadar tutar; ve testler yığını senaryonun ortasında
bırakır, o yüzden prova etmeden önce sıfırlayın.
