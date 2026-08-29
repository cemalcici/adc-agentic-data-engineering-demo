# Demoyu kendi ortamınızda çalıştırın

Bu rehber, repoyu daha sonra kendi bilgisayarında denemek isteyenler içindir.
Kurulumdan başlayarak üç davranışı çalıştırır:

1. Bir şema değişikliği pipeline'ı kırar; ajan öneri üretir; insan reddeder.
2. Kalıcı arıza yeni bir incident olarak tekrar ele alınır; insan onaylar;
   ajan düzeltmeyi uygulayıp kendi başlattığı koşuyla doğrular.
3. İsteğe bağlı olarak doğrulayıcı devre dışı bırakılır; ajan sınırlı sayıda
   deneyip `unfixable` sonucuyla durur.

Bu PoC'nin temel iddiası şudur:

> Self-healing, ajanın üretime serbestçe yazması değildir. Ajan canlı kanıt
> toplar, küçük bir değişikliği gerçek araçlarla doğrular ve eylem sınırında
> insana döner.

## Gereksinimler

- Docker Desktop veya Docker Engine ile Compose desteği
- Git
- OpenAI uyumlu, structured output destekleyen bir model endpoint'i
- Aşağıdaki yerel portların kullanılabilir olması:
  - `5432`: PostgreSQL
  - `6006`: Phoenix
  - `8080`: Airflow
  - `8501`: Streamlit

İlk kurulum Docker imajlarını oluşturduğu için birkaç dakika sürebilir.

## 1. Ortam değişkenlerini hazırlayın

Repo kökünde örnek dosyayı kopyalayın:

```bash
cp .env.example .env
```

`.env` içindeki `replace-me` değerlerini değiştirin. Özellikle şunlar gereklidir:

- PostgreSQL parolası
- Airflow admin ve viewer parolaları
- Airflow JWT secret'ı
- Dashboard veritabanı parolası
- Model endpoint URL'si, API anahtarı ve model adı

Gerçek `.env` dosyasını commit etmeyin veya terminal çıktısına yazdırmayın.

## 2. Stack'i başlatın

```bash
docker compose up -d
```

Stack şu bileşenleri başlatır:

| Bileşen | Görevi | Adres |
| --- | --- | --- |
| PostgreSQL | Kaynak, warehouse ve incident store | `localhost:5432` |
| Airflow | ELT pipeline ve gerçek koşu durumu | <http://localhost:8080> |
| Agent | Hata tespiti, teşhis, öneri, uygulama ve doğrulama | Container servisi |
| Phoenix | Ajan trace'leri | <http://localhost:6006> |
| Streamlit | Operatör konsolu | <http://localhost:8501> |

## 3. Kurulumu doğrulayın

```bash
./verify-stack.sh
```

Beklenen sonuç:

```text
19 passed, 0 failed
```

Özellikle şu kontrollerin geçtiğini doğrulayın:

- Kaynak kolonunun `customer_id` olması ve drift uygulanmamış olması
- Model endpoint'inin cevap vermesi
- Bütün servislerin hazır olması

İlk Airflow koşusunun tamamlanmasını bekleyin. Ardından Streamlit'te
`PIPELINE HEALTHY` görünmelidir.

## Arayüzleri tanıyın

### Streamlit operatör konsolu

<http://localhost:8501>

Konsol pipeline sağlığını warehouse tablosundan değil, Airflow'daki son koşudan
okur. Bunun nedeni başarısız bir koşudan sonra eski mart tablosunun hâlâ
sorgulanabilir olmasıdır. Veri mevcut görünebilirken pipeline kırık olabilir.

Konsolun yetkisi bilinçli olarak dardır:

- Incident kayıtlarını okuyabilir.
- Yalnızca operatör kararını yazabilir.
- dbt projesine erişemez.
- Airflow koşusu başlatamaz.

### Airflow

<http://localhost:8080>

`.env` dosyasında tanımladığınız admin kullanıcısıyla giriş yapın.
`customer_elt` DAG'ı iki task içerir:

1. `extract_customers`: Kaynak tablonun o anki şemasını warehouse'a kopyalar.
2. `dbt_run`: Staging ve mart modellerini oluşturur.

### Phoenix

<http://localhost:6006>

`self-healing-pipeline` projesi ajanın trace'lerini içerir. Bir incident'ın
Streamlit'teki **How did the agent arrive at that?** bağlantısı sizi ilgili
trace'e götürür.

## Senaryo 1: Öneriyi reddedin, sonra iyileşmeyi onaylayın

Bu senaryo insan onay kapısının iki tarafını gösterir. İlk incident reddedilir;
dbt projesi değişmez. Arıza kalıcı olduğu için ajan yeni bir incident açar.
İkinci incident onaylanır ve pipeline iyileşir.

### 1. Sağlıklı başlangıcı kontrol edin

Streamlit'i açın ve `PIPELINE HEALTHY` durumunu doğrulayın.

İsterseniz başlangıçtaki dbt çalışma ağacını da kontrol edin:

```bash
git status --short dbt/
```

Çıktı boş olmalıdır.

### 2. Upstream şema değişikliğini uygulayın

```bash
docker compose --profile drift run --rm --build drift
```

Komut kaynak tablodaki `customer_id` kolonunu `cust_id` olarak değiştirir.
Beklenen çıktı eski kolonun gittiğini, yeni kolonun geldiğini ve değişiklikten
etkilenen kayıt sayısını gösterir.

Drift servisi yalnızca kaynak veritabanına erişebilir. dbt projesini göremez ve
değişikliği geri alamaz.

### 3. Pipeline'ı Airflow'dan manuel tetikleyin

Pipeline normalde beş dakikada bir çalışır. Beklemek istemiyorsanız:

1. Airflow'da **DAGs** listesini açın.
2. `customer_elt` DAG'ını seçin.
3. DAG'ın unpaused olduğunu doğrulayın.
4. Sağ üstteki **Trigger DAG** düğmesine basın.
5. Yapılandırma ekranı açılırsa varsayılan değerlerle onaylayın.

Airflow sürümüne bağlı olarak düğmenin konumu veya etiketi küçük farklılık
gösterebilir.

Yeni koşuda beklenen sonuç:

- `extract_customers`: başarılı
- `dbt_run`: başarısız
- Bütün DAG run'ı: başarısız

`dbt_run` log'unda `customer_id` kolonunun bulunamadığını görebilirsiniz.

### 4. Yanlış yeşil durumunu gözlemleyin

Streamlit kısa süre sonra `PIPELINE FAILING` gösterir. Buna rağmen son başarılı
mart tablosu warehouse'da durmaya devam eder. Bu, görünür veri ile onu üreten
son sürecin sağlığının aynı şey olmadığını gösterir.

Henüz incident görünmüyorsa ajan bir sonraki polling turunu bekliyor olabilir.
Varsayılan polling aralığı 20 saniyedir.

### 5. İlk teşhis ve öneriyi inceleyin

Ajan şu kanıtları canlı olarak toplar:

- Son başarısız Airflow run'ı ve failing task
- Task log'u
- Kaynak sistemin mevcut kolonları
- Hata veren dbt modelinin güncel içeriği

Ardından kök neden teşhisi ve tam dosya içeriği olarak bir aday düzeltme üretir.
Aday, operatöre sunulmadan önce:

- dbt projesinin scratch kopyasına yazılır,
- ayrı validation şemalarında bütün proje build edilir,
- build başarısızsa hata modele geri verilerek en fazla iki kez yeniden denenir.

Streamlit'te teşhisi ve önerilen diff'i inceleyin. Bu aşamada gerçek dbt
dosyasına hiçbir şey yazılmamıştır.

### 6. Trace'i inceleyin

Streamlit'teki **How did the agent arrive at that?** bağlantısını açın.
Phoenix'te aşağıdakine benzer bir span ağacı görmelisiniz:

```text
agent_pass → detect_failure → fetch_failure_log → inspect_schema
           → diagnose → ChatOpenAI
           → propose_fix → ChatOpenAI → validate_candidate
           → record_proposal
```

İnceleyebileceğiniz noktalar:

- `fetch_failure_log`: Airflow'dan alınan hata
- `inspect_schema`: Canlı kaynak şeması
- `ChatOpenAI`: Modele gönderilen bağlam ve structured output
- `validate_candidate`: İzole dbt build sonucu
- Trace başlığı: Gecikme, token ve maliyet

### 7. İlk incident'ı reddedin

Streamlit'e dönün ve **Reject** düğmesine basın.

Beklenen davranış:

- Incident `rejected` terminal durumuna geçer.
- dbt projesine hiçbir değişiklik yazılmaz.
- Ajan Airflow koşusu başlatmaz.
- Pipeline kırmızı kalır.

History bölümünde `rejected` kaydını görebilirsiniz.

### 8. Yeni incident'ı bekleyin

Ret yalnızca mevcut incident'ı kapatır; upstream şema değişikliği devam eder.
In-flight incident kalmadığı için ajan sonraki turunda hâlâ başarısız olan son
run'ı tekrar ele alır ve yeni bir incident açar.

Bu davranış hakkında iki önemli sınır vardır:

- Yeni kayıt, önceki incident'ın revizyonu değil ayrı bir incident'tır.
- Ajan önceki ret gerekçesini bilmez ve incident'lar arasında hafıza taşımaz.

Bu nedenle ikinci öneri ilk öneriyle aynı olabilir. Ajan canlı log, şema ve
modeli sıfırdan okuyarak tekrar teşhis üretir.

### 9. İkinci incident'ı onaylayın

İkinci öneri `proposed` durumuna ulaştığında diff'i inceleyin ve **Approve**
düğmesine basın.

Konsol yalnızca incident durumunu `approved` yapar. Değişikliği kendisi
uygulamaz. Ajan bir sonraki turunda bu durumu okuyunca grafın eylem dalına
geçer.

### 10. İyileşmeyi doğrulayın

Ajan:

1. Onaylanan tam dosya içeriğini dbt projesine yazar.
2. Airflow API üzerinden yeni bir pipeline run'ı başlatır.
3. Başlattığı run'ın ID'sini incident'a kaydeder.
4. Yalnızca bu run'ı izler.
5. Run başarılıysa incident'ı `resolved` yapar.

Streamlit'te önce uygulama durumunu ve `verifying_run_id` değerini, ardından
`PIPELINE HEALTHY` sonucunu görmelisiniz. History bölümünde ilk incident
`rejected`, ikinci incident `resolved` olarak kalır.

Airflow'da `verifying_run_id` ile eşleşen run'ı açarak iki task'ın da başarılı
olduğunu doğrulayabilirsiniz.

### 11. Uygulanan dosya değişikliğini inceleyin

```bash
git diff -- dbt/
```

Beklenen değişiklik staging modelinde yeni upstream ismini okuyup downstream
sözleşmesini koruyan küçük bir alias'tır:

```sql
cust_id as customer_id
```

## Senaryo 2: Doğrulayıcı yoksa ajan durur

Bu isteğe bağlı senaryo kontrollü fault injection kullanır. Amaç modeli kötü
cevap vermeye zorlamak değil, aday düzeltme doğrulanamadığında grafın sınırlı
retry sonrasında durduğunu göstermektir.

Senaryonun beklenen sonucu:

```text
validator unavailable → bounded retries → give_up → unfixable
```

### 1. Temiz başlangıca dönün

```bash
git restore dbt/
docker compose down -v
docker compose up -d
./verify-stack.sh
```

`19 passed, 0 failed` ve Streamlit'te `PIPELINE HEALTHY` bekleyin.

### 2. Doğrulayıcı arızasını enjekte edin

Agent container'ını, yalnızca bu senaryo için var olmayan bir dbt executable
yoluyla yeniden oluşturun:

```bash
AGENT_DBT_EXECUTABLE=/demo-fault/dbt-unavailable docker compose up -d --force-recreate agent
```

Bu override:

- model endpoint'ini değiştirmez,
- Airflow ve PostgreSQL erişimini bozmaz,
- incident store'u değiştirmez,
- yalnızca adayın izole dbt build'ini çalıştırılamaz hâle getirir.

### 3. Drift'i uygulayıp pipeline'ı çalıştırın

```bash
docker compose --profile drift run --rm --build drift
```

Senaryo 1'deki adımlarla `customer_elt` DAG'ını Airflow UI üzerinden manuel
tetikleyin.

### 4. `unfixable` sonucunu gözlemleyin

Ajan gerçek modelle teşhis ve aday üretir. Her `validate_candidate` çağrısı dbt
executable bulunamadığı için başarısız olur. İlk deneme ve iki retry sonrasında
`give_up` düğümü incident'ı `unfixable` olarak kapatır.

Streamlit'te beklenen durum:

- History içinde `unfixable` incident
- Onaylanabilir proposal veya diff bulunmaması
- Pipeline'ın kırmızı kalması

Agent log'unu kontrol edin:

```bash
docker compose logs --tail 40 agent
```

Phoenix trace'inde tekrar eden aşağıdaki dalı inceleyin:

```text
propose_fix → validate_candidate
      ↑              │
      └──── retry ───┘
                     └→ give_up → unfixable
```

Buradaki anlam “ajan düzeltmenin yanlış olduğunu kanıtladı” değildir. Ajan
düzeltmenin doğru olduğunu kanıtlayamadığı için operatöre uygulanabilir bir
öneri sunmadan durmuştur.

### 5. Fault injection'ı kaldırın

Stack'i yeniden kurduğunuzda ajan varsayılan gerçek dbt executable'ına döner:

```bash
git restore dbt/
docker compose down -v
docker compose up -d
./verify-stack.sh
```

Komuttaki değişkeni `export` etmeyin. Export ettiyseniz yeniden başlatmadan önce:

```bash
unset AGENT_DBT_EXECUTABLE
```

## Sistemi başlangıç durumuna döndürün

Ana senaryoda onaylanan değişiklik dbt dosyasında kalır. Drift ise PostgreSQL
volume'unda kalır. Tam sıfırlama için ikisini de temizleyin:

```bash
git restore dbt/
docker compose down -v
docker compose up -d
./verify-stack.sh
```

Neden iki temizlik gerekir:

- `git restore dbt/`, ajanın uyguladığı takip edilen dbt değişikliğini atar.
- `docker compose down -v`, sürüklenmiş kaynağı ve veritabanı durumunu atar.

Yalnızca birini çalıştırırsanız kaynak ve transformation birbirine uyumlu veya
ters yönde uyumsuz kalabilir; sonraki denemeniz beklediğiniz başlangıç
durumundan başlamaz.

## Sorun giderme

### Bir servisin durumunu kontrol edin

```bash
docker compose ps
```

### Ajan sonucu görünmüyor

```bash
docker compose logs --tail 40 agent
```

- `watching customer_elt every 20s`: Ajan çalışıyor ve polling yapıyor.
- `pass failed`: Hata tipi aynı satırda görünür.
- Container durmuşsa: `docker compose up -d agent`.

### Pipeline kırmızıya dönmedi

1. Airflow'da manuel run'ın gerçekten oluştuğunu kontrol edin.
2. `./verify-stack.sh` çıktısında kaynak kolonunun `cust_id` olduğunu doğrulayın.
3. Önceki düzeltmenin kalıp kalmadığını kontrol edin:

```bash
git status --short dbt/
```

### Reject sonrasında yeni incident oluşmadı

1. History'de ilk incident'ın `rejected` olduğunu doğrulayın.
2. Agent log'unda yeni bir pass olup olmadığına bakın.
3. En az bir polling aralığı ve model yanıt süresi kadar bekleyin.

### Model endpoint'i çalışmıyor

```bash
./verify-stack.sh
docker compose logs --tail 40 agent
```

Endpoint URL'sini, model adını, API anahtarını ve structured output desteğini
kontrol edin. Hazırlanmış bir incident'ı canlı ajan çıktısı gibi incident
store'a yazmayın; bu repo böyle bir fallback sağlamaz (ADR-0028).

### Phoenix açılmıyor

Phoenix gözlemlenebilirlik katmanıdır; ajanın çalışması ona bağlı değildir.
Phoenix log'unu kontrol edin:

```bash
docker compose logs --tail 40 phoenix
```

### Onaylandı ancak pipeline düzelmedi

Incident `verification_failed` olur ve uygulanan dosya diskte kalır. Ajan sessiz
rollback yapmaz; rollback ikinci bir yazma eylemi ve ayrı bir yetki kararıdır.
`git diff -- dbt/` ile uygulanan değişikliği inceleyip ardından stack'i
sıfırlayın.

## Davranışın sınırları

### Incident'lar arasında hafıza var mı?

Hayır. Her incident canlı run, log, şema ve dbt modeli üzerinden sıfırdan
teşhis edilir. Reddedilen önerinin gerekçesi sonraki incident'a aktarılmaz.

### Ajan serbest planlama yapıyor mu?

Hayır. LangGraph adımların sırasını sabitler. Model teşhis ve düzeltmenin
içeriğini seçer; hangi sistemlere hangi sırayla gidileceğini planlamaz.

### Neden MCP kullanılmıyor?

PoC iki araca Airflow REST API ve PostgreSQL istemcisiyle erişir. MCP doğal bir
genişleme noktasıdır; fakat tek başına grafın yetki veya doğrulama modelini
değiştirmez.

### Ajan yanlış bir şey üretirse ne olur?

- Aday build olmazsa operatöre ulaşmaz; retry sınırında `unfixable` olur.
- Aday build olur ancak semantik olarak yanlışsa insan diff'i reddedebilir.
- Onaylanan aday pipeline'ı düzeltmezse `verification_failed` olur.
- Hedef dosyayı model seçmez; hedef başarısız dbt log'undan çıkarılır.
- Yazma kapsamı yalnızca `models/*.sql` altındadır.

### Onay kapısı nasıl uygulanıyor?

- Veritabanı yalnızca `proposed → approved` geçişine izin verir.
- Ajanın yazma dalı yalnızca `approved` durumundan ulaşılabilir.
- Streamlit yalnızca karar sütununu güncelleyebilir.
- Streamlit'in dbt mount'u ve Airflow run başlatma yetkisi yoktur.

### İyileşme nasıl doğrulanıyor?

Ajan değişikliği yazdıktan sonra kendisi yeni bir Airflow run'ı başlatır ve
yalnızca kaydettiği run ID'sini izler. Düzeltmeden önce başlamış başka bir
koşunun sonucunu kullanmaz (ADR-0024).

## Otomatik kontroller

Stack hazır olduğunda:

```bash
./verify-stack.sh
./smoke-tests.sh
```

`verify-stack.sh` servis ve başlangıç durumu kontrollerini çalıştırır.
`smoke-tests.sh`, model çağırmadan iki temel iddiayı sınar:

- Drift pipeline'ı gerçekten kırar.
- Onaylanmış doğru düzeltme pipeline'ı gerçekten iyileştirir.

Smoke test stack'i senaryonun ortasında bırakabilir. Manuel denemeden önce
**Sistemi başlangıç durumuna döndürün** bölümündeki adımları yeniden uygulayın.
