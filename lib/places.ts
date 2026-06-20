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
