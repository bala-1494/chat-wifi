# Hotelify

AI-powered hotel management software. Import any hotel from Google Maps and generate a full marketing page with photos, reviews, and location data.

## Tech Stack

- **Framework**: Next.js 14 (App Router, TypeScript)
- **Styling**: Tailwind CSS — red (`#C41E3A`) and white theme
- **APIs**: Google Places API (Place Details, Find Place, Photo proxy)
- **Storage**: localStorage (MVP — replace with Supabase/Prisma later)

## Architecture

### Auth
Mock OAuth via `AuthProvider` context (`components/AuthProvider.tsx`). Demo account: `admin@hotelify.com`. Replace with NextAuth.js + real Google OAuth when ready.

### Hotel Import Flow
1. User pastes a Google Maps URL into `AddHotelModal`
2. `POST /api/places` parses the URL → extracts Place ID
3. Calls Google Places API `place/details` → validates `lodging` type
4. Returns structured `Hotel` object → saved to localStorage via `useHotels`
5. Redirects to `/hotel/[placeId]` — the generated marketing page

### API Routes
| Route | Method | Purpose |
|---|---|---|
| `/api/places` | POST | Accept Maps URL → return hotel data |
| `/api/photo` | GET | Proxy Google Places photos (keeps key server-side) |

### Key Files
```
app/
  layout.tsx          — root layout with AuthProvider
  page.tsx            — redirect to /login or /dashboard
  login/page.tsx      — mock Google OAuth login
  dashboard/page.tsx  — hotel list + Add Hotel empty state
  hotel/[id]/page.tsx — generated marketing page
  api/places/route.ts — Places API integration
  api/photo/route.ts  — photo proxy
components/
  AuthProvider.tsx    — auth context + useAuth hook
  Navbar.tsx
  AddHotelModal.tsx   — URL input + import flow
lib/
  types.ts            — Hotel, Review interfaces
  places.ts           — Google Maps URL parser
hooks/
  useHotels.ts        — localStorage hotel list
```

## Environment Variables

```env
GOOGLE_MAPS_API_KEY=               # server-side — Places API + photo proxy
NEXT_PUBLIC_GOOGLE_MAPS_API_KEY=   # client-side — Maps Embed iframe
```

Both can be the same key. Recommended: restrict the server key to Places API only; restrict the public key to Maps Embed API only.

## Setup

```bash
npm install
cp .env.example .env.local
# Add API keys to .env.local
npm run dev
```

## Roadmap

- [ ] Real Google OAuth (NextAuth.js)
- [ ] Database persistence (Supabase)
- [ ] AI-generated room/property descriptions
- [ ] Booking engine integration
- [ ] Multi-property analytics dashboard
- [ ] White-label hotel page export
