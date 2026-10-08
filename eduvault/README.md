# EduVault — Frontend

Secure e-learning platform frontend with separate **Admin** and **Student** portals.

**Scope:** frontend only. Every screen runs against an in-browser **mock API** today. Switching to the real REST backend is a configuration change — no UI rewrites.

| | |
|---|---|
| Framework | Next.js 16 (App Router) · React 19 · TypeScript (strict) |
| UI | Tailwind CSS v4 · shadcn/ui (Base UI primitives) · Lucide icons |
| Data | TanStack Query v5 |
| Forms | React Hook Form · Zod v4 |
| Charts | Recharts via shadcn `chart` |

## Getting started

```bash
npm install
cp .env.example .env.local   # optional; mock mode is the default
npm run dev                  # http://localhost:3000
```

Other scripts: `npm run build`, `npm run start`, `npm run lint`, `npx tsc --noEmit`.

### Demo sign-in (mock mode only)

| | |
|---|---|
| Admin portal | any email containing `admin`, e.g. `admin@eduvault.example` |
| Student portal | any other email |
| Password | any value with 8+ characters |
| 2FA code | `123456` |

You can also open `/admin/dashboard` or `/student/dashboard` directly. In mock mode the "current user" is inferred from the portal you are in.

The demo student has courses in every access state (active, pending, payment required, expired). That way every CTA and screen state can be reached.

## Architecture

```
Component  →  Hook (src/hooks)  →  API service (src/lib/api)  →  REST backend
                 TanStack Query       mock impl  |  http impl
```

Components never call `fetch` or import mock data. They only use hooks.

```
src/
├── app/
│   ├── (auth)/            login, register, forgot-password, reset-password, verify-2fa
│   ├── (admin)/admin/     admin portal routes (layout = AppShell + RoleGate)
│   ├── (student)/student/ student portal routes
│   ├── layout.tsx         root providers (Query, theme, tooltips, toasts)
│   └── error.tsx, not-found.tsx
├── components/
│   ├── ui/                shadcn/ui primitives (generated; Base UI based)
│   ├── shared/            DataTable, SearchBar, FilterDropdown, StatusBadges, StatCard,
│   │                      EmptyState, ErrorState, skeletons, ConfirmationDialog, Modal,
│   │                      SideDrawer, FormField, CourseCard, ResourceCard, NotificationCenter…
│   ├── layout/            AppShell (sidebar/header), breadcrumbs, RoleGate, user menu, bell
│   ├── pdf-viewer/        protected viewer (PdfViewer, PdfToolbar, PdfPage, PdfWatermark…)
│   ├── admin/<feature>/   admin page views
│   ├── student/<feature>/ student page views
│   └── auth/              auth forms
├── hooks/                 one file per domain + query-keys.ts + use-list-state.ts
├── lib/
│   ├── api/               *Api.ts services, client.ts (fetch wrapper), config.ts
│   ├── mock/              seeded mock data (only imported by lib/api mock impls)
│   ├── format.ts, constants.ts, navigation.ts, course-access.ts, toast.ts
├── types/                 domain types (= API contract)
└── styles/globals.css     design tokens (light + dark)
```

Each page file in `app/` is a small server component that exports `metadata` and renders a client view from `components/<area>/<feature>/`.

## Connecting the backend

1. Set the environment variables in `.env.local`:
   ```
   NEXT_PUBLIC_API_BASE_URL=https://api.example.com/v1
   NEXT_PUBLIC_USE_MOCK_API=false
   ```
2. Every service in `src/lib/api/*.ts` exports an interface and two implementations, `http…Api` and `mock…Api`. The flag selects one. The `http` implementations already call the endpoints listed below. Adjust paths or payloads there if the backend contract differs.
3. The types in `src/types/index.ts` are the expected JSON shapes:
   - Money is in **minor units** (cents).
   - Dates are ISO-8601 strings.
   - Lists return `PaginatedResponse<T>`: `{ data, page, pageSize, total, totalPages }`.
   - Errors return `ApiErrorBody`: `{ message, code?, fieldErrors? }`.
4. **Auth** is cookie-based. Requests use `credentials: "include"`, and the frontend stores no tokens. The backend should set an httpOnly session cookie. `src/proxy.ts` (Next 16's renamed middleware) adds optimistic redirects when the mock is off. It expects `eduvault_session` and a non-sensitive `eduvault_role` hint cookie. It is a UX convenience only. **The backend must authorise every request.**

### Endpoints the frontend calls

| Area | Method & path |
|---|---|
| Auth | `POST /auth/login` · `POST /auth/2fa/verify` · `POST /auth/2fa/resend` · `POST /auth/register` · `POST /auth/forgot-password` · `POST /auth/reset-password` · `POST /auth/logout` · `GET /auth/me` |
| Dashboard | `GET /admin/dashboard` · `GET /student/dashboard` |
| Registrations | `GET /admin/registrations` · `GET /admin/registrations/:id` · `PATCH /admin/registrations/:id` `{status, note}` · `POST /student/registrations` `{courseId, message}` |
| Students | `GET /admin/students` · `GET /admin/students/:id` · `POST /admin/students/:id/suspend` · `POST /admin/students/:id/reinstate` · `GET /admin/students/:id/{access,payments,activity}` |
| Courses | `GET/POST /admin/courses` · `GET/PATCH /admin/courses/:id` · `PATCH /admin/courses/:id/status` · `GET /courses/categories` · `GET /student/courses` · `GET /student/courses/:id` · `GET /student/my-courses` |
| Resources | `GET /admin/courses/:id/resources` · `POST /admin/courses/:id/resources` (multipart) · `PUT /admin/resources/:id/file` (multipart) · `PATCH /admin/resources/:id` · `DELETE /admin/resources/:id` · `GET /student/courses/:id/resources` |
| Viewer | `POST /student/resources/:id/session` · `POST /admin/resources/:id/preview` · `GET /viewer/resources/:id/pages/:n` · `POST /student/resources/:id/progress` |
| Access | `GET /admin/access` · `GET /admin/access/summary` · `PATCH /admin/access/:id` · `POST /admin/access/:id/extend` |
| Payments | `GET /admin/payments` · `GET /student/payments` · `GET /student/checkout/:courseId` · `POST /student/checkout/sessions` → `{ redirectUrl }` |
| Notifications | `GET /{admin\|student}/notifications` · `GET …/unread-count` · `POST …/:id/read` · `POST …/read-all` |
| Reports | `GET /admin/reports/:type` · `POST /admin/reports/:type/export` → `{ downloadUrl }` |
| Audit / Settings | `GET /admin/audit-logs` · `GET /admin/settings` · `PUT /admin/settings/:section` |
| Learning | `GET /student/learning-history` · `GET /student/learning-history/recent` |

List endpoints accept `page`, `pageSize`, `search` and the filters shown in each `*ListParams` type (for example `status`, `courseId`, `from`, `to`).

### Protected PDF viewer contract

The frontend **never receives a PDF file or a PDF URL**.

1. The viewer opens a session with `POST /student/resources/:id/session`. The backend checks access and returns a `ResourceViewerSession`: page count, the watermark text (name, email, course/resource) and an expiry.
2. The viewer then requests one page at a time with `GET /viewer/resources/:id/pages/:n`. Each response is a `ResourcePage` with a short-lived, session-bound image (signed URL or data URI) rendered server-side.
3. The client overlays a dynamic watermark. Copying, the context menu, dragging and printing are discouraged. These are deterrents only. In production the backend should also burn the watermark into the rendered images.
4. The viewer reports reading progress with `POST /student/resources/:id/progress`.

### Payments

Checkout is designed for a hosted payment page (for example Stripe Checkout):

1. The frontend calls `POST /student/checkout/sessions` and redirects to the `redirectUrl` it receives.
2. The provider returns the student to `/student/payments/checkout?course=<id>&status=success|failed|cancelled`.
3. The backend (via webhooks) is the source of truth for payment status.

No keys or card data touch the frontend.

## Conventions

- **Base UI, not Radix:** there is no `asChild`. Use the `render` prop, for example `<Button nativeButton={false} render={<Link href="…" />}>`. `DropdownMenuLabel` must sit inside a `DropdownMenuGroup`.
- **Status display** uses the typed badges in `components/shared/status-badge.tsx`. Labels and tones live in `lib/constants.ts`.
- **What a student can do** with a course in each access state comes from `lib/course-access.ts` (`getCourseCta`).
- **Every data view** has a loading skeleton, an error state with retry and an empty state.
- **Important or destructive actions** go through `ConfirmationDialog`. Mutations show a toast via `notify` (`lib/toast.ts`).
- **List pages** use `useListState` (debounced search, filters, pagination) together with `DataTable`.
