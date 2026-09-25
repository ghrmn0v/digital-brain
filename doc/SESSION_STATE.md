# Fly — Session State (continue here)

> Yazılıb: 25 Sep 2026. Növbəti sessiyada bu fayldan davam et.
> Repo: /home/sado/Desktop/Fly, branch `fly`. **Commit etmək qadağandır** (spec direktivləri).

## Canlı vəziyyət
- Python brain: `127.0.0.1:8601` (pid 58967, log `/tmp/opencode/fly_python.log`) — `connectome/`, stdlib-only, Py 3.14.7
- Spring backend: `:8080` (pid 40204, log `/tmp/opencode/fly_spring.log`)
- Desktop: yalnız `cd desktop && npm start` (istifadəçi açır/qapayır)
- Services dayandırmaq: `ss -ltnp` ilə PID tapıb `kill <pid>`. **`pkill -f electron` etmə** (lazımsız prosesləri öldürür; həmin çağırış onboarding-də çox it went-hang oldu).
- Komitə YOX; çoxlu modified + untracked fayl var (Faza A–D faylları hələ komit edilməyib).

## Testlər
- Python: `cd connectome && python3 -m unittest discover -s tests -q` → **99 OK**
- Java: `<repo>/backend` → **57 OK** (`mvn test`/`./mvnw` — fakt dərc edilib)
- Node: `cd desktop && npm test` → **20 OK**; smoke `FLY_SMOKE_OK`
- RL üçün torch var: `connectome/.venv` (torch **2.14.0+cpu**, Py3.14). NumPy yoxdur → torch warning verir, amma işləyir. Əvvəl tam CUDA wheel ~2.8GB ilə **Disk quota exceeded** idi; CPU index həll etdi: `--index-url https://download.pytorch.org/whl/cpu`. Pip cache `~/.cache/pip` 2.8GB.

## Nə edilib (ümumi)
- Brain: real adult Drosophila mushromm body (FlyWire) — `adult_mb_wiring.json`, 2414 neyron, rate-model (AI deyil).
- Faza A–D: influence gate, API auth token interceptor, Retryer, sound → tam, testləri var (untracked fayllar: DeveloperController, ApiSecurityConfig, ApiTokenInterceptor, DeveloperEventRequest/DeveloperModeRequest, Retryer, DeveloperEventMapper).
- Faza E (2D billboard):
  - Camera `(0,1.5,7.0)`, billboard hündürlüyü 0.62; animasiya offset-lərinin **yığılma bug-u** düzəldildi (`runtime.pos` eased base + hər kadr yenidən hesablanan `extra`, `fly.position.copy(runtime.pos).add(extra)`); screen-space clamp (`project(camera)`→NDC clamp→`perNdc` düzəlişi) — sprite HUD/panel altına getmir.
  - Speech bubble indi **başın üstündə** (`#speech-bubble` + `::after` caret, proyeksiya + clamp).
- Uçuş sistemi:
  - Server `--flight off|on` (env `FLY_FLIGHT_MODE`, default **on**); GET/POST `/mode` yerli endpoint; Spring `BehaviorGateway.flightMode()/setFlight`, `FlyController` GET+POST `/api/v1/mode/flight`; desktop `#flight-mode` checkbox (sync+tost).
  - **Sevincli-uçuş dizaynı** (policy.py): flight ON + təbii `SUCCESS/CURIOUS/LEARNING` + priority ≥ `FLIGHT_MIN_PRIORITY=0.3` → qərar `FLYING`; desktop `TAKEOFF→FLYING→LANDING→IDLE` zənciri (renderer `runtime.flightChain`/`playState`/`returnToIdle`). Ciddi hadisələr (IMPORTANT/ERROR/WARNING) heç vaxt uçmur. `decide(..., flight=False)` olduqda `FLIGHT_STATES` namizəd siyahısından çıxır.
  - Uçuş animasiyası: `center_upper`, scale 1.15, `fly_circle` səkkiz-fiquru (`extra.x=cos(1.5t)*0.4`, `extra.z=sin(3t)*0.12`, `extra.y=sin(2.2t)*0.16`).
  - Əvvəlki dizayn test olundu və atıldı: xalis mükafat FLYING-i +0.35 natural boost üzərində qazandıra bilmirdi; düz bonus dinamikası ciddi hadisələri də uçurdurdu → sevincli-uçuş seçildi.
- Canlı training (API round): 7 round × {process_completed@0.7, app_open@0.6, notification@0.7} `reacted_positive` → dataset +21 labeled.
- Canlı yoxlamalar: `process_completed@0.85→FLYING`, `app_open@0.5→FLYING`, `important_message@0.92→IMPORTANT`, `warning@0.9→WARNING`, `app_idle@0.2→IDLE`, health `flight_mode:"on"`, `/mode/flight` round-trip.
- Dataset export: `python3 -m connectome.training.dataset --db /home/sado/.fly/connectome.db` → `connectome/training/datasets/train_decisions.{csv,jsonl}` + `dataset_meta.json`. Son meta: **127 qərar, 97 labeled (76.38%), +76/-8/0/13, feedback_rows_total 114**.

## Phase 7 (offline RL) — bug və qalan
- İcra edildi: `.venv/bin/python -m connectome.training.rl.offline_exp --episodes 4000` → warm-up 3.37s, **80%** razılaşma (RL vs prototype cədvəli; audio DIFF). Checkpoint `connectome/training/rl/experiments/brain_model.pt`, report `rl_experiment_latest.json`.
- Sonra `.venv/bin/python -m connectome.training.evaluation` → **verdict: COLLECT_MORE_DATA**, `safe_to_influence_production: False`, heç degradasiya yox (mean_reward_delta 0.0).
- **Tapıntı/uyğunsuzluq (açıq problem):**
  - `offline_exp` RL-ni `rl_brain.baseline_behavior(type_code)` sabit cədvəlinə öyrədir (image→frontflip, sticker→backflip, text/audio→face_user).
  - Amma REAL production əsas `evaluation.baseline_reactions()` = real beyni işlədir → `STATE_REACTION` xəritəsi ilə bütün 5 ssenari `face_user` çıxır.
  - Yəni RL əsl beyinlə müqayisədə həmişə ~20% → gate heç vaxt CANDIDATE deyə bilmir, halbuki heç nə pisləşməyib.
- **İstifadəçi qərarı (açıq sual):**
  - (a) RL hədəfini real beynin qərarlarına yönəlt (offline_exp düzəlişi + `test_rl_experiment.py` yenilə) → yenidən işlə → CANDIDATE hədəflə.
  - (b) Pipeline-ə toxunmadan app-də daha çox feedback yığ.
  - (c) Gate-i keçmədən `FLY_LEARNED_INFLUENCE=on` (dizaya zidd, tövsiyə edilmir).
  - Sual question-tool ilə verildi, istifadəçi dismiss etdi → **davam üçün ilk iş: istifadəçidən (a)/(b)/(c) seçimini öyrən.**
- `FLY_LEARNED_INFLUENCE=auto` yalnız verdict `CANDIDATE_FOR_PRODUCTION` olduqda açılmalıdır.

## Qalan işlər
1. Phase 7 davam (a–c arası seçim; RL hədəfini real beyinə görə düzəltmək ən sağlam).
2. İstifadəçi `desktop`-i açıb vizual yoxlama: bubble başın üstündə, kenar/border kliplənməsi yox, flight checkbox → TAKEOFF→FLYING→LANDING zənciri.

## Əsas fayllar
- `connectome/connectome/policy.py` — `FLIGHT_STATES`, `FLIGHT_CELEBRATION`, `FLIGHT_MIN_PRIORITY`, celebration override `decide()`, `NATURAL_STATE`, `PRIORITY_LEVEL`, `PATTERNS`
- `connectome/connectome/server.py` — `--flight`, `FlyBrainService(flight=...)`, GET/POST `/mode`, health `flight_mode`, nəticə `flight` field
- `connectome/tests/test_policy.py`, `test_server.py` — 99 yaşıl
- `connectome/connectome/training/rl/offline_exp.py` + `rl_brain.py` — RL boru xətti (hədəf uyğunsuzluğu burada)
- `connectome/connectome/training/evaluation.py` — Əsas qarşılaşdırma + verdict `evaluation_reports/evaluation_latest.json`
- `connectome/connectome/training/dataset.py` — DB→dataset export (`FLY_DB`/`/home/sado/.fly/connectome.db`)
- `desktop/src/renderer.js` — `runtime.pos` ayırması, `playState`, `runtime.flightChain`, `positionBubble`, screen clamp, `#flight-mode`, `demoDecision` flight xəritəsi
- `desktop/src/animations.js` — FLYING/TAKEOFF/LANDING specs, `fly_circle` səkkiz-fiqur
- `desktop/src/index.html` — `#flight-mode`, `#speech-bubble` (+caret), `#msg`, `#toast`
- `backend/.../gateway/BehaviorGateway.java` (+`Retryer.java`), `backend/.../api/FlyController.java`, `DeveloperController.java` — HTTP bridge
- `desktop/models/fly.png` — 36MB, kompressiya təklifi (offer ~1–2MB)

## Qeydlər
- Model şəkliləri oxuya bilmir → vizual varlıq üçün istifadəçidən vizual izahı/ink. Río diagnosis üçün renderer localStorage `fly.debug` instrumentation istifadə olunurdu; temp capture/debug skriptləri silinib.
- Py 3.14-də torch CPU wheel (`download.pytorch.org/whl/cpu`) quraşdırılıb — full CUDA wheel disk limiti/daha böyük.