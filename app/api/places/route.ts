import { NextRequest, NextResponse } from 'next/server'
import { parseMapsUrl, expandShortUrl } from '@/lib/places'

const API_KEY = process.env.GOOGLE_MAPS_API_KEY

// Accommodation-related types actually returned by the legacy Place Details
// endpoint (Table A). Newer granular types like "hotel"/"motel"/"resort_hotel"
// belong to the Places API (New) taxonomy and are never returned here.
const HOTEL_TYPES = new Set(['lodging', 'campground', 'rv_park'])

async function resolvePlaceIdFromUrl(url: string): Promise<string | undefined> {
  const expandedUrl = await expandShortUrl(url)
  const { placeId, query, lat, lng } = parseMapsUrl(expandedUrl)
  if (placeId) return placeId
  if (!query) return undefined

  const params = new URLSearchParams({
    input: query,
    inputtype: 'textquery',
    fields: 'place_id',
    key: API_KEY!,
  })
  if (lat !== undefined && lng !== undefined) {
    params.set('locationbias', `point:${lat},${lng}`)
  }
  const res = await fetch(
    `https://maps.googleapis.com/maps/api/place/findplacefromtext/json?${params.toString()}`
  )
  const data = await res.json()
  return data.candidates?.[0]?.place_id
}

export async function POST(req: NextRequest) {
  if (!API_KEY) {
    return NextResponse.json({ error: 'Google Maps API key not configured' }, { status: 500 })
  }

  const body = await req.json()
  const directPlaceId: string | undefined = body.placeId
  const url: string | undefined = body.url

  if (!directPlaceId && !url) {
    return NextResponse.json({ error: 'URL is required' }, { status: 400 })
  }

  const resolvedPlaceId = directPlaceId ?? (await resolvePlaceIdFromUrl(url!))

  if (!resolvedPlaceId) {
    return NextResponse.json({ error: 'Could not identify a place from this URL.' }, { status: 400 })
  }

  const fields = [
    'place_id', 'name', 'rating', 'user_ratings_total', 'formatted_address',
    'international_phone_number', 'website', 'editorial_summary', 'photos',
    'reviews', 'types', 'geometry', 'url', 'price_level',
  ].join(',')

  const detailsRes = await fetch(
    `https://maps.googleapis.com/maps/api/place/details/json?place_id=${resolvedPlaceId}&fields=${fields}&reviews_sort=most_relevant&key=${API_KEY}`
  )
  const details = await detailsRes.json()

  if (details.status !== 'OK') {
    return NextResponse.json({ error: `Places API: ${details.status}` }, { status: 400 })
  }

  const place = details.result
  const isHotel = place.types?.some((t: string) => HOTEL_TYPES.has(t))

  if (!isHotel) {
    return NextResponse.json(
      { error: 'This location does not appear to be a hotel or lodging property.' },
      { status: 400 }
    )
  }

  const hotel = {
    id: place.place_id,
    name: place.name,
    rating: place.rating ?? 0,
    totalRatings: place.user_ratings_total ?? 0,
    address: place.formatted_address,
    phone: place.international_phone_number,
    website: place.website,
    description: place.editorial_summary?.overview,
    photoReferences: (place.photos ?? []).slice(0, 10).map((p: { photo_reference: string }) => p.photo_reference),
    reviews: (place.reviews ?? []).slice(0, 5).map((r: {
      author_name: string
      profile_photo_url?: string
      rating: number
      text: string
      relative_time_description: string
    }) => ({
      author: r.author_name,
      authorPhoto: r.profile_photo_url,
      rating: r.rating,
      text: r.text,
      relativeTime: r.relative_time_description,
    })),
    types: place.types ?? [],
    lat: place.geometry.location.lat,
    lng: place.geometry.location.lng,
    addedAt: new Date().toISOString(),
    mapsUrl: url ?? place.url,
    priceLevel: place.price_level,
  }

  return NextResponse.json({ hotel })
}
