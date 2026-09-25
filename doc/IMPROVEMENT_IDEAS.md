# Təkmilləşdirmə ideyaları — Fly / Connectome

> 9 ideya təqdim edildi. Hər biri üçün: **verdict**, **niyə**, **nə edildi**.
> Tarix: 25 Sep 2026 · Stat: 6 tətbiq edildi, 1 tələb olunur (token), 1 yeni iş, 1 açıq qərar.

---

## Yekun xülasə

| # | İdeya | Verdict | Harada |
|---|---|---|---|
| 1 | Həqiqi `weight` ilə KC→MBON başlanğıc çəkisi | ✅ **Tətbiq edildi** | `adult_mb_wiring.json`, `loader.py`, `model.py` |
| 2 | `media_type` CTX kanalına | ⚠️ **Tətbiq edildi, amma iddia ediləni vermir** | `simulate.py`, `evaluation.py` |
| 3 | `MBON_gamma → MBON_output` inhibitor | ✅ **Tətbiq edildi** | `adult_mb_wiring.json`, `model.py` |
| 4 | Sabit şum → stoxastik (`gauss`) | ✅ **Tətbiq edildi** | `model.py` |
| 5 | Eligibility trace (associative learning) | ✅ **Tətbiq edildi** (kod düzəldildi) | `model.py` |
| 6 | Per-person kontekst kanalı | ⚠️ **Tətbiq edildi, amma iddia ediləni vermir** | `simulate.py` |
| 7 | Real FlyWire məlumatı (CAVEclient) | ⛔ **Token lazımdır** | — |
| 8 | RL baseline uyğunsuzluğu | 🔶 **Açıq qərar (dəyişdirilmədi)** | `doc/REBUILD_PROMPT.md` §8.1 |
| 9 | Yaddaş konsolidasiyası | ⏭️ **Yeni iş — sonraya** | — |

---

## 1. ✅ Həqiqi başlanğıc çəkisi (tətbiq edildi)

**İdeya:** KC→MBON düyünlərinin başlanğıc çəkisi 1.0 yox, həqiqi biomemara uyğun olsun.

**Vacib düzəliş:** Təklifdə deyilirdi ki *"The loader already reads the `weight` key"*. **Bu doğru deyildi** —
`load_wiring()` `weight`-i oxumurdu, `Edge.weight` həmişə default `1.0` idi. Əvvəlcə loader-ı düzəltmək
lazım idi, yoxsa JSON-a əlavə etdiyimiz `weight` ləğv olardı.

**Edildi:**
- `loader.py` → `weight=float(edge.get("weight", 1.0))`
- `adult_mb_wiring.json`:
  | Edge | weight | səbəb |
  |---|---|---|
  | `KC → MBON_alpha` | **0.6** | PAM-DAN mükafat neyronları MBON_alpha-nı tənqid edir → zəif başlanğıc |
  | `KC → MBON_gamma` | **1.4** | ən güclü kompartment (56000 sinaps) |
  | `KC → MBON_output` | **1.2** | hərəkət çıxışı |
- `model.py` → `decay` artıq **1.0-a deyil, `initial_weights`-ə** çəkilir
  (`updated -= decay * (current - prior)`). Əks halda 1.4/0.6 dəyərləri bir neçə yüz feedback-dən
  sonra yenidən 1.0-a sürüşürdü və bioloji prior itirdi.

**Nəticə:** `{MBON_alpha: 0.6, MBON_beta: 1.0, MBON_beta2: 1.0, MBON_gamma: 1.4,
MBON_apostrophe: 1.0, MBON_bpost: 1.0, MBON_output: 1.2}`

---

## 2. ⚠️ `media_type` kanalı — tətbiq edildi, amma **gate-ı açmır**

**İdeya iddiası:** *"This alone lets the brain distinguish image vs. audio events and makes the RL
training meaningful."*

**Bu iddia düzgün deyil.** Ölçdüm:

```
notification + topic + urgency (media_type-siz)  -> CTX drive 0.4500
notification + image                             -> CTX drive 0.5250
notification + audio                             -> CTX drive 0.5250
notification + sticker                           -> CTX drive 0.5250
notification + video                             -> CTX drive 0.5250
```

**Bütün media tipləri eyni dəyər verir.** Səbəb arxitekturdadır:

1. Beyində **tək bir `CTX` düyünü** var → o, skaler drive yaradır (`0.15 + 0.6 * covered/8`).
   `media_type` yalnız `covered` sayını dəyişir (3→4 kanal), **hansı** kanal seçildiyi yox olur.
2. Tək bir `KC` qrupu var (population 2200) → `_activity_fn` KC aktivliyini hesablaya bilir,
   amma **hansı KC alt-populasiyasının** aktivləşdiyini bilmir.
3. `policy.PATTERNS` yalnız MBON kompartmentlərinə baxır — `media_type` haqqında ümumi məlumatı yoxdur.

Yəni media tipi beyinə **yalnız "bu hadisədə kontekst bir az daha çoxdur"** siyasəti kimi gəlir.
Görüntü ilə səs eyni cür emal olunur.

**Edildi (yenə faydalıdır, amma iddia edilən deyil):**
- `simulate.py` → `_context_channels(..., ctx.get("media_type",""))`
- `evaluation.py` → hər ssenari öz `media_type`-ini daşıyır (`image`, `audio`, `sticker`, `video`),
  beləliklə müqayisə **eyni girişlər** üzərində aparılır (əvvəl ssenari "audio" deyirdi, amma
  beyinə audio çatmayırdı).

**Həqiqi həll (8-ci ideya ilə birləşdir):** `PATTERNS` media-axarında oxuna bilən bir komponent
lazımdır — məsələn hər media tipi üçün **ayrı KC qrupu** (`KC_image`, `KC_audio`, …) və ya
`media_type`-a görə MBON-a birbaşa giriş. Bu **arxitektura dəyişikliyidir**, "5 sətir" deyil.

**Status:** `baseline_reactions()` hələ də `face_user` qaytarır (5/5) → gate hələ də bağlı.

---

## 3. ✅ `MBON_gamma → MBON_output` inhibitor (tətbiq edildi)

Həqiqi flyda γ-MBON-lar approach-avoidance çıxışını ən çox tənqid edən kompartmentdir.

**Edildi:**
- JSON: `{"from": "MBON_gamma", "to": "MBON_output", "synapses": 1500, "plastic": false,
  "physiology": "inhibitory"}`
- `model.py::_drive`:
```python
sign = -1.0 if edge.physiology == "inhibitory" else 1.0
total += sign * edge.synapses * weight * self.activity[edge.source]
```

**Ölçülən effekt** (canlı server, `process_completed`):
`MBON_output = 0.141` → digər kompartmentlər `0.176`. Əvvəl gamma output-u gücləndirirdi,
indi tənqid edir → **qaçma/yaxınlaşma (WARNING/ERROR) düzgün çıxışı bastırır.**

---

## 4. ✅ Stoxastik şum (tətbiq edildi)

Sabit `+0.0005` bias əvəzinə həqiqi variabilite.

**Edildi:**
```python
# DEFAULT_CONFIG: "noise": 0.0005  → indi standart sapma
"trace_decay": 0.85,   # yeni (5-ci ideya üçün)
"seed": None,          # yeni: None = deterministik deyil, dəyər veriləndir təkrar təkrarlanandır
```
```python
# _drive()
drive += self._rng.gauss(0.0, self.config["noise"])
```
`Brain` öz `random.Random(seed)` axınına malikdir — global `random` toxunulmur.
Testlər/eksperiment üçün `config={"seed": 7}` ilə təkrar təkrarlanandır.

**Diqqət:** `noise` artıq *bias* deyil, *standart sapma*. Dəyər kiçikdir (0.0005), qərarları
praktikada qurmur, amma eyni hadisə eyni priority ilə hər dəfə tam eyni nəticəni vermir.

---

## 5. ✅ Eligibility trace (tətbiq edildi — kod düzəldildi)

**Təklifdəki kod səhv idi:** `self.eligibility` `edge.key` (tuple) ilə qurulur, amma
`_update_plasticity` içində `self.eligibility.get(edge.source, 0.0)` — yəni **tuple ilə
axtarılan dictionary-yə string ilə baxılırdı** → həmişə `0.0` qalırdı, yəni iz (trace) heç
vaxt işləmirdi.

**Edildi (düzgün):**
```python
# Brain.__init__
self.eligibility = {edge.key: 0.0 for edge in graph.edges.values() if edge.plastic}

# step() -> activity yeniləndən sonra
def _update_traces(self):
    decay = self.config["trace_decay"]; keep = 1.0 - decay
    for edge in self.graph.plasticity_edges():
        key = edge.key
        self.eligibility[key] = (decay * self.eligibility.get(key, 0.0)
                                 + keep * self.activity.get(edge.source, 0.0))

# _update_plasticity
kc = self.eligibility.get(key, 0.0)      # əvvəl: self.activity.get(edge.source, 0.0)
```
`reset()` izləri sıfırlayır. `trace_decay = 0.85` → hər addımda 15% sönmə.

**Ölçülən nəticə:** hadisə bitdikdən 5 addım sonra gələn mükafat hələ düzgün sinapsı
dəyişir (`1.40000 → 1.40051`) — yəni "feedback gec gələndə ölür" problemi yoxdur.
**Dəyişən davranış:** dərhal gələn feedback əvvəlkindən **zəif** təsir edir (KC aktivliyi
hələ qalmadığı üçün), bu real Drosophila öyrənməsinə uyğundur.

---

## 6. ⚠️ Per-person kanal — tətbiq edildi, amma **"fərqli adama fərqli cavab" yoxdur**

**İdeya iddiası:** *"The fly would literally learn to respond differently to messages from
different people."*

**Bu iddia da düzgün deyil** — eyni arxitektura səbəbi (tək `CTX` skaler + tək `KC` qrupu).
Ölçülən fərq yalnız **ümumi qalxma**dır:

| Sorğu | CTX drive | Nəticə |
|---|---|---|
| `user_message` (person yox) | 0.375 | LISTENING (conf 0.377) |
| `person_alim` | 0.450 | LISTENING (conf 0.388) |
| `person_boss` | 0.450 | LISTENING (conf 0.390) |

**Edildi:** `simulate.py` → `person_id = (event.person or {}).get("id", "")` `_context_channels`-ə
əlavə olundu. Faylı hazırlayan şəxs üçün bu, gələcəkdə **hər şəxsə ayrı KC qrupu** əlavə edildikdə
hazır olacaq.

**Həqiqi həll:** `nodes`-a `KC_p_<hash>` qrupları əlavə etmək və `inject_event` bunlardan birini
seçmək — yəni arxitektura dəyişikliyi.

---

## 7. ⛔ Real FlyWire məlumatı (CAVEclient)

Tələb olunur: **flywire.ai-də pulsuz hesab + API token**. 50 000+ edge, sinaps sayları
fərdi neyron cütü səviyyəsində dəqiq olacaq.

**Status:** token olmadan edilə bilməz. Token verilsə:
1. `connectome/reference/flywire_live_service.py` genişləndirilir (hazır stub var).
2. Yeni JSON neyron səviyyəli edge-lərlə yazılır.
3. `loader.py` **eyni qalır** (README-də yazılıb: "expandable with real FlyWire exports through
   the same loader") — əgər yeni format `from/to/synapses/plastic/physiology/weight`
   saxlayırsa, heç bir kod dəyişikliyi lazım deyil.
4. `population` > 1 olan qruplar üçün `PATTERNS` təkrar nəzərdan keçirilməlidir.

---

## 8. 🔶 RL baseline uyğunsuzluğu (açıq qərar)

Dəyişdirilmədi — bu **qərar tələb edir**. İki fərqli əsas var:

- **Baseline A** (`rl_brain.baseline_behavior`): sabit cədvəl — `image→frontflip`,
  `sticker→backflip`. RL bunun öhdəsindən öyrənir (Faza-5 hesabatı: 80%).
- **Baseline B** (`evaluation.baseline_reactions`): **əsl beyin** — 5 ssenarinin hamısı
  `face_user` (Faza-6 hesabatı: 20%, verdict `COLLECT_MORE_DATA`).

2 və 6-cı ideyalar bu müqayisəni yaxşılaşdırdı, amma **həll etmədi** — səbəb yuxarıda
arxitektura səbəbidir.

**Seçimlər:** (a) RL hədəfini əsl beyinə yönəlt + `STATE_REACTION`-ı torch-suz paylaşılan
leaf modula köçürmək; (b) daha çox real feedback toplamaq; (c) `FLY_LEARNED_INFLUENCE=on`
(məsl axımdan keçir — **tövsiyə edilmir**).

---

## 9. ⏭️ Yaddaş konsolidasiyası (yeni iş)

Real-time plastislik əvəzinə "yuxu" fazasında batch yeniləmə. Yeni modul, yeni CLI, yeni testlər.
Faza 7 gate-ini dəyişmir. Sonraya.

---

## Kənardan aşkarlanan problem (bu tapşırıqda dəyişdirilmədi)

**`_context_channels` hash toqquşusu → mövzu sətrinə görə davranış dəyişir.**

```
topic "job"/"system"/"general"/"b"/"c" -> 4 kanal -> drive 0.4500
topic "work"/"build"/"demo"/"a"        -> 3 kanal -> drive 0.3750
```

`CTX_CHANNELS = 8`, 4 hissə → 3 və ya 4 unikal kanal (50/50). Nəticə: **eyni hadisə, eyni
priority, fərqli topic sətri → fərqli beyin aktivliyi.** `kc_theta = 0.35` bu səviyyəyə
çox yaxındır, ona görə sərhəd keçidi də var.

Bu mövcud davranışdır (mənim dəyişikliyim yaratmayıb — `media_type`/`person` əlavəsi yalnız
0.375 → 0.450 fərqini genişlətdi). Amma "öyrənən fly" üçün bu **arzuolunmayan** davranışdır.

**Mümkün həllər (seçim tələb edir):**
- `covered` sayını deyil, **hər kanalın öz drive-unu** toplamaq (hər hissə ayrıca drive verir,
  toplam clamped) — daha sabit, az toqquşma hassaslığı.
- `CTX_CHANNELS`-ı artırmaq (8 → 16/32) → toqquşma ehtimalı azalır.
- `_context_channels`-ı kompartment seçən funksiyaya çevirmək (6-cı ideyanın həqiqi həlli).
