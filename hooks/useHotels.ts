'use client'

import { useState, useEffect } from 'react'
import { Hotel } from '@/lib/types'

export function useHotels() {
  const [hotels, setHotels] = useState<Hotel[]>([])

  useEffect(() => {
    const stored = localStorage.getItem('hotelify_hotels')
    if (stored) setHotels(JSON.parse(stored))
  }, [])

  const addHotel = (hotel: Hotel) => {
    const updated = [hotel, ...hotels.filter(h => h.id !== hotel.id)]
    setHotels(updated)
    localStorage.setItem('hotelify_hotels', JSON.stringify(updated))
  }

  const removeHotel = (id: string) => {
    const updated = hotels.filter(h => h.id !== id)
    setHotels(updated)
    localStorage.setItem('hotelify_hotels', JSON.stringify(updated))
  }

  return { hotels, addHotel, removeHotel }
}
