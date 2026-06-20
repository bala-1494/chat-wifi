import { NextRequest, NextResponse } from 'next/server'

const API_KEY = process.env.GOOGLE_MAPS_API_KEY

export async function GET(req: NextRequest) {
  const ref = req.nextUrl.searchParams.get('ref')
  const maxWidth = req.nextUrl.searchParams.get('maxwidth') || '1200'

  if (!ref || !API_KEY) return new NextResponse(null, { status: 404 })

  const photoRes = await fetch(
    `https://maps.googleapis.com/maps/api/place/photo?maxwidth=${maxWidth}&photoreference=${ref}&key=${API_KEY}`,
    { redirect: 'follow' }
  )

  if (!photoRes.ok) return new NextResponse(null, { status: 404 })

  const buffer = await photoRes.arrayBuffer()

  return new NextResponse(buffer, {
    headers: {
      'Content-Type': photoRes.headers.get('content-type') || 'image/jpeg',
      'Cache-Control': 'public, max-age=86400',
    },
  })
}
