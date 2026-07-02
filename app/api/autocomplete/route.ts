import { NextRequest, NextResponse } from 'next/server'

const API_KEY = process.env.GOOGLE_MAPS_API_KEY

export async function GET(req: NextRequest) {
  if (!API_KEY) {
    return NextResponse.json({ error: 'Google Maps API key not configured' }, { status: 500 })
  }

  const input = req.nextUrl.searchParams.get('input')?.trim()
  if (!input) return NextResponse.json({ predictions: [] })

  const params = new URLSearchParams({
    input,
    types: 'lodging',
    key: API_KEY,
  })

  const res = await fetch(
    `https://maps.googleapis.com/maps/api/place/autocomplete/json?${params.toString()}`
  )
  const data = await res.json()

  if (data.status !== 'OK' && data.status !== 'ZERO_RESULTS') {
    return NextResponse.json({ error: `Places API: ${data.status}` }, { status: 400 })
  }

  const predictions = (data.predictions ?? []).map((p: {
    place_id: string
    description: string
    structured_formatting?: { main_text: string; secondary_text?: string }
  }) => ({
    placeId: p.place_id,
    mainText: p.structured_formatting?.main_text ?? p.description,
    secondaryText: p.structured_formatting?.secondary_text ?? '',
  }))

  return NextResponse.json({ predictions })
}
