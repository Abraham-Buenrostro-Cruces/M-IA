import { describe, expect, it } from 'vitest'
import { haceCuanto, metros, minutos } from './formato'

describe('formato', () => {
  const ahora = new Date('2026-11-24T12:00:00Z')
  it.each([
    ['2026-11-24T11:59:30Z', 'hace un momento'],
    ['2026-11-24T11:35:00Z', 'hace 25 min'],
    ['2026-11-24T09:00:00Z', 'hace 3 h'],
    ['2026-11-23T06:00:00Z', 'hace 30 h'],
    ['2026-11-22T00:00:00Z', 'hace 3 días'],
    [null, 'sin verificación'],
  ])('haceCuanto(%s) = %s', (iso, esperado) => {
    expect(haceCuanto(iso, ahora)).toBe(esperado)
  })

  it('minutos y metros', () => {
    expect(minutos(42.5)).toBe('43 min')
    expect(minutos(75)).toBe('1 h 15 min')
    expect(metros(837)).toBe('837 m')
    expect(metros(1530)).toBe('1.5 km')
  })
})
