# Digital Brain Product / Connectors

Core Brain və Fly ilə inteqrasiya edən, local-first Product və Connector qatı. Bu repository Core Brain intelligence və Fly behavior implement etmir; o sahələrə yalnız stabil API/event sərhədləri təqdim edir.

## Əsas funksiyalar

- Local Tasks CRUD, due date, priority və təkrarlanan task seriyası
- Local Calendar CRUD, timezone, reminder və recurrence metadata
- LinkedIn job ingestion, normalizasiya, deduplication, status history və report
- `AUTOMATIC`, `ASK_FIRST`, `OFF` permission qaydaları
- Action registry, approval/rejection audit və structured action response
- Event/schedule automation engine; automation həmişə permission engine-dən keçir
- Generic connector event ingestion və real LinkedIn job adapterı
- SQLite durable event/delivery qatı, Core Brain delivery və Fly SSE stream
- Connector status/health UI və credential-ləri göstərmədən idarəetmə
- Product Timeline, Settings, Dashboard və responsive UI
- Runtime Zod validation, stabil API errors və mutation idempotency
- Vitest unit/integration testləri və təmiz test SQLite DB

## Texnoloji stack

- Next.js 16 App Router, React 19, TypeScript
- Tailwind CSS 4, Lucide React
- Prisma 7 + SQLite + `better-sqlite3`
- Zod 4
- EventEmitter2
- Vitest 5
- npm

## Lokal başlatma

Tələb: Node.js `22.12+`.

```powershell
cd "C:\Users\user\OneDrive\Desktop\digital-brain-product"
npm ci
Copy-Item .env.example .env
npm run db:deploy
npm run db:seed
npm run dev
```

Tətbiq: [http://localhost:3000](http://localhost:3000)

Health/readiness: [http://localhost:3000/api/health](http://localhost:3000/api/health)

Prisma Studio:

```powershell
npm run db:studio
```

Background delivery və one-time schedule worker:

```powershell
npm run worker
```

## Əsas əmrlər

| Əmr | Təyinat |
| --- | --- |
| `npm run dev` | Next.js development server |
| `npm run build` | Production build |
| `npm run worker` | Event delivery və schedule polling worker |
| `npm run lint` | ESLint |
| `npm run typecheck` | Next route type generation + TypeScript |
| `npm test` | Unit və integration testlər |
| `npm run test:coverage` | Coverage report |
| `npm run test:smoke` | Real Next.js HTTP runtime smoke test with isolated DB |
| `npm run check` | Lint + typecheck + tests |
| `npm run verify` | Prisma validation + check + production build |
| `npm run db:migrate -- --name <name>` | Yeni development migration |
| `npm run db:deploy` | Commit edilmiş migration-ları tətbiq etmək |
| `npm run db:seed` | Default permissions, connectors və settings |
| `npm run db:studio` | Prisma Studio |

## Arxitektura

```text
External services
  -> Connector normalize/ingest
  -> IntegrationEvent + EventDelivery (SQLite)
  -> Core Brain HTTP delivery
  -> Fly SSE / HTTP delivery
  -> Event automations
  -> Permission engine
  -> Action registry
  -> Tasks / Calendar / Jobs
  -> Product UI
```

Server-only modullar `src/modules` altında qruplaşır:

- `tasks`, `calendar`, `jobs`: domain validation və persistence
- `permissions`: policy resolution
- `actions`: registry, approval və execution audit
- `automations`: event/schedule conditions və action dispatch
- `connectors`: connector lifecycle və LinkedIn normalizer
- `events`: normalized event, durable delivery və SSE
- `settings`, `timeline`: product-owned data

API sənədləri: [`docs/API_CONTRACTS.md`](docs/API_CONTRACTS.md)

## Default təhlükəsizlik davranışı

- Core Brain tərəfindən task/event yaratma `ASK_FIRST`
- Task/event silmə və job application `OFF`
- Naməlum action `400 ACTION_NOT_SUPPORTED`
- Naməlum permission `ASK_FIRST`
- Disabled permission `OFF`
- Automation permission qaydasını keçə bilmir
- LinkedIn connector relevance/qərar yaratmır
- `relevanceReason` yalnız Core Brain tərəfindən göndərilən məlumat kimi göstərilir
- Raw credentials SQLite-də və UI-da göstərilmir

## Xarici integrasiyalar

`.env` də:

```dotenv
SERVICE_API_TOKEN="strong-random-service-token"
CORE_BRAIN_URL="http://localhost:4100"
CORE_BRAIN_API_TOKEN=""
FLY_EVENTS_URL="http://localhost:4200/events"
FLY_API_TOKEN=""
```

Boş URL-lərdə event hələ də SQLite-da saxlanılır; delivery `PENDING` qalır. URL konfiqurasiya edildikdə worker `core_brain` və `fly` consumer-lərinə bounded retry göndərir.

LinkedIn scraping bu layihədə yoxdur. LinkedIn endpoint yalnız authorized connector worker-ın ötürdüyü normalized vəziyyəti qəbul edir; həqiqi OAuth/acquisition hərə bir dəstəklənən provider API-si ilə ayrıca həll olunmalıdır.

## Core Brain və Fly sərhədləri

- Product Core Brain intelligence yaratmır.
- Product People/Memory məlumatını lokal DB-də saxlamır.
- Fly üçün yalnız event stream verilir; Fly behavior qərarı Fly engineer-a məxsusdur.
- Brain events `/api/brain-events` ilə qəbul edilir.
- Fly events `/api/fly-events` SSE stream ilə oxunur.
- Action intent və nəticə Core Brain tərəfindən eyni kontraktla göndərilir və qəbul edilir.

## Yoxlama

```powershell
npm run verify
npm audit
```

`npm run verify` Prisma sxemini, lint, TypeScript, 14+ test və production build-i yoxlayır.
