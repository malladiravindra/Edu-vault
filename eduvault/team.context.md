# Team Context

Daily work log for EduVault. Add a new entry at the top for each day.

---

## 2026-10-06

| Field      | Value |
| ---------- | ----- |
| Name       | Guru  |
| Date       | 2026-10-06 |
| Git branch | `main` |

### Done today

**Login page redesigned to match the supplied design (Student Login)**
- Dark navy page with a background photo. On the left: the EduVault shield logo, "Learn Anytime, **Anywhere**", the tagline, and three features (Protected Content, Learn at Your Pace, Track Your Progress). On the right: a glass-style "Student **Login**" card.
- Card: email and password fields with icons, show/hide password, "Remember me" (ticked by default), "Forgot password?", "Sign In →", "or", "Continue with Google", "Don't have an account? **Sign Up**".
- The sign-in logic is unchanged: validation, error messages, the 2FA redirect and admin/student routing all work as before.
- "Continue with Google" only shows a "coming soon" toast; there is no Google sign-in yet.
- The mock-API hint is now a small collapsible "Demo logins" tag in the top-right corner.
- This replaces the earlier attempt that was reverted on 2026-10-01; it was rebuilt at the user's request.

**Register and Forgot Password pages restyled to match**
- Same photo, left panel and card as Login.
- Register ("Create **Account**"): full name, email, password and confirm password side by side (stacked on phones), a live password checklist, the terms checkbox, "Create Account →" and "Already have an account? **Sign In**". After submitting, it shows a "Check your inbox" screen.
- Forgot Password ("Forgot **Password?**"): email, "Send Reset Link →" and "← Back to Sign In". After sending, it shows a "Check your email" screen with "Use a different email".
- The register and reset-request logic is unchanged.

**Fits on one screen**
- On desktop, text, icons, inputs, buttons and spacing scale with the window height (CSS `clamp` with `vh`), so Login and Forgot Password fit without scrolling, even on short or zoomed windows (checked at 1400×630). Register is taller and scrolls on phones.

**Background photo**
- `public/images/login-hero.jpg`: a free Unsplash photo by Julio Lopez (Unsplash License), https://unsplash.com/photos/young-woman-wearing-headphones-studying-at-desk-Imz-pn2LMbg
- The original is a bright daytime shot, so it is tinted navy in CSS to look like night. If the exact photo from the design turns up, replace this file; no code change is needed.

**Structure**
- New route group `src/app/(hero-auth)/` with its own layout, holding `login`, `register` and `forgot-password`. The URLs are unchanged.
- `reset-password` and `verify-2fa` stay in `src/app/(auth)/` with the old light layout.
- Files: `src/components/auth/auth-hero-shell.tsx` (photo, left panel, card frame), `src/components/auth/auth-hero-ui.tsx` (dark inputs, buttons, checkbox, status screens, logo, Google icon), `src/components/auth/login-view.tsx`, `src/components/auth/register-view.tsx`, `src/components/auth/forgot-password-view.tsx`, `src/app/(hero-auth)/layout.tsx`

### Verification
- Lint and `next build` pass.
- Headless Chrome screenshots of all three pages checked at 1390×1132 (the design size), 1400×630 (short window) and 500px wide (phone).

### Notes / follow-ups
- Reset Password and the 2FA page still use the old light design, so the email reset link lands on a page that doesn't match. Restyle both with the `auth-hero-ui` pieces.
- Google sign-in needs a backend before the button can work.
- The Terms of Service and Privacy Policy links on Register are placeholders (`#terms`, `#privacy`).
- The logo is an inline SVG drawn to match the design; swap in the official logo file when one exists.
- Restart `next dev` if pages look stale; the route folders moved while the dev server was running.
- Nothing is committed yet.

---

## 2026-10-01

| Field      | Value |
| ---------- | ----- |
| Name       | Guru  |
| Date       | 2026-10-01 |
| Git branch | `main` |

### Done today

**Student dashboard redesigned to match the supplied design**
- Four panels: Statistic (progress ring round the avatar, level badge, welcome, average progress, course-status split, In progress / Upcoming / Completed counts), Your courses (coral carousel of active courses), Study process (minutes read per day this week) and AI assistant.
- All figures come from the existing hooks (`useProfile`, `useStudentDashboard`, `useMyCourses`). No new APIs.
- Removed from the dashboard: "Continue learning", "Recent courses" and "Recent notifications". Notifications are still in the navbar bell.
- The AI assistant is UI only. Sending a question, "Model" and "⋯" all show a "coming soon" toast.
- How the numbers are worked out:
  - Level badge: below 35% average progress is Beginner, 35–69% is Intermediate, 70% and above is Advanced.
  - In progress = active courses below 100%. Upcoming = pending or awaiting payment. Completed = 100%.
  - Study process bars show minutes read per day this week; the busiest day is coral.
- Avatars show initials, because users have no profile photos yet.
- Files: `src/components/student/dashboard/student-dashboard-view.tsx`

**Student portal navbar**
- Floating rounded navbar on a grey background. The links sit in one rounded group, and the current page shows as a dark rounded button with its icon. Admin navbar unchanged.
- New colour tokens in `src/styles/globals.css`: `canvas`, `coral`, `blush`, `sun` (with dark-mode values).
- File: `src/components/layout/app-shell.tsx`

**Login page redesign tried and reverted**
- Built a dark-navy "Student Login" design from a reference image, then reverted it because the original page looks more professional.
- The login page, auth layout and other auth pages are back to how they were before today. No auth changes are left.

### Verification
- Type check, lint and `next build` pass.
- Headless Chrome screenshots checked at 1440px, 900px and 500px wide. Headless Chrome won't go below about 500px, so true phone width (390px) hasn't been checked.
- The restored login page was checked in a screenshot after the revert.

### Notes / follow-ups
- Nothing is committed yet.
- AI assistant needs a backend before it can answer questions.
- The design's "x/y classes" tags show category and resource count instead, because completed-resource counts aren't in the data yet.
- Check the dashboard on a real phone, and in dark mode.
- `src/components/ui/sidebar.tsx` is still unused (from 2026-10-01).

---

## 2026-10-06

| Field      | Value |
| ---------- | ----- |
| Name       | Guru  |
| Date       | 2026-10-06 |
| Git branch | `main` |

### Done today

**Navigation: sidebar replaced with a top navbar (Admin and Student portals)**
- Removed the collapsible sidebar from both portals; both now use a sticky top navbar.
- All modules are direct links on the same row as the EduVault logo (no dropdowns, no second row).
- Admin nav label "Access Management" shortened to "Access" to fit; the page breadcrumb still shows the full name.
- The account menu shows only the avatar below 1536px wide, then the user's name too.
- If the window is too narrow, the nav links scroll sideways. Below 1024px, all pages move into a ☰ slide-out menu that also has Log out.
- Files: `src/components/layout/app-shell.tsx`, `src/lib/navigation.ts`, `src/components/layout/user-menu.tsx`

**Breadcrumbs: removed duplicate page title**
- Breadcrumbs now show only on nested pages (e.g. Courses › Create), so top-level pages no longer repeat their own heading, e.g. "Dashboard" twice.
- File: `src/components/layout/breadcrumbs.tsx`

**Animations**
- Navbar slides in on load; the current page's link shows a coloured underline that grows from its centre.
- Each page fades in and rises slightly when opened.
- Dashboard stat cards and "Continue learning" cards appear one after another.
- Stat cards and course cards lift slightly on hover.
- Mobile menu links appear one after another when the menu opens.
- Animations are switched off for users whose device is set to reduce motion.
- Uses the existing `tw-animate-css` package; no new dependencies.
- Files: `src/styles/globals.css`, `src/components/shared/stat-card.tsx`, `src/components/shared/course-card.tsx`, `src/components/admin/dashboard/admin-dashboard-view.tsx`, `src/components/student/dashboard/student-dashboard-view.tsx`

### Verification
- Type check, lint and production build (`next build`) pass.
- Not yet checked in a browser.

### Notes / follow-ups
- `src/components/ui/sidebar.tsx` is no longer used; delete it unless the sidebar is coming back.
- Admin login (mock API mode): any email containing "admin", any password of 8+ characters, 2FA code `123456`.
- These changes are not yet committed.
