// Short links (e.g. shared from the Google Maps app) redirect to the
// canonical google.com/maps URL. They carry no place info themselves,
// so they must be resolved server-side before parsing.
function isShortUrl(url: string): boolean {
  try {
    const { hostname, pathname } = new URL(url)
    return hostname === 'maps.app.goo.gl' || (hostname === 'goo.gl' && pathname.startsWith('/maps'))
  } catch {
    return false
  }
}

// Google serves a different (often interstitial/blocked) response to
// non-browser user agents on the short-link redirect, so we must look like
// a real browser to reliably get the true 30x redirect chain.
const BROWSER_USER_AGENT =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'

export async function expandShortUrl(url: string): Promise<string> {
  if (!isShortUrl(url)) return url
  try {
    const res = await fetch(url, { redirect: 'follow', headers: { 'User-Agent': BROWSER_USER_AGENT } })
    return res.url || url
  } catch {
    return url
  }
}

export function parseMapsUrl(
  url: string
): { placeId?: string; query?: string; lat?: number; lng?: number } {
  // Extract ChIJ... place ID from data parameter
  const placeIdMatch = url.match(/!1s(ChIJ[^!&]+)/)
  if (placeIdMatch) return { placeId: decodeURIComponent(placeIdMatch[1]) }

  // CID format: ?cid=12345
  const cidMatch = url.match(/[?&]cid=(\d+)/)
  if (cidMatch) return { placeId: cidMatch[1] }

  // @lat,lng,zoom viewport segment — used below as a location bias/fallback
  const latLngMatch = url.match(/@(-?\d+\.\d+),(-?\d+\.\d+)/)
  const latLng = latLngMatch
    ? { lat: parseFloat(latLngMatch[1]), lng: parseFloat(latLngMatch[2]) }
    : {}

  // Modern Maps links often encode the place as a hex Feature ID inside the
  // data parameter instead of a ChIJ id, e.g. !1s0x89c259a9b3117469:0xd134e...
  // The value after the colon is the place's CID in hex; Places Details
  // accepts a decimal CID the same way it accepts the ?cid= query param above.
  const hexFidMatch = url.match(/!1s0x[0-9a-fA-F]+:0x([0-9a-fA-F]+)/)
  if (hexFidMatch) return { placeId: BigInt('0x' + hexFidMatch[1]).toString(), ...latLng }

  // Extract name from URL path /place/Hotel+Name/. When Maps drops the name
  // (e.g. .../place/@40.7,-74,17z), this segment is the viewport instead, so
  // the [^/@?]+ class intentionally fails to match starting at "@".
  const nameMatch = url.match(/\/place\/([^/@?]+)/)
  if (nameMatch) return { query: decodeURIComponent(nameMatch[1].replace(/\+/g, ' ')), ...latLng }

  if (latLngMatch) return { ...latLng, query: url }

  return { query: url }
}
