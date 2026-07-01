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

export async function expandShortUrl(url: string): Promise<string> {
  if (!isShortUrl(url)) return url
  try {
    const res = await fetch(url, { redirect: 'follow' })
    return res.url || url
  } catch {
    return url
  }
}

export function parseMapsUrl(url: string): { placeId?: string; query?: string } {
  // Extract ChIJ... place ID from data parameter
  const placeIdMatch = url.match(/!1s(ChIJ[^!&]+)/)
  if (placeIdMatch) return { placeId: decodeURIComponent(placeIdMatch[1]) }

  // CID format: ?cid=12345
  const cidMatch = url.match(/[?&]cid=(\d+)/)
  if (cidMatch) return { placeId: cidMatch[1] }

  // Extract name from URL path /place/Hotel+Name/
  const nameMatch = url.match(/\/place\/([^/@?]+)/)
  if (nameMatch) return { query: decodeURIComponent(nameMatch[1].replace(/\+/g, ' ')) }

  return { query: url }
}
