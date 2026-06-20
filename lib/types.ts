export interface Hotel {
  id: string
  name: string
  rating: number
  totalRatings: number
  address: string
  phone?: string
  website?: string
  description?: string
  photoReferences: string[]
  reviews: Review[]
  types: string[]
  lat: number
  lng: number
  addedAt: string
  mapsUrl: string
  priceLevel?: number
}

export interface Review {
  author: string
  authorPhoto?: string
  rating: number
  text: string
  relativeTime: string
}
