import type { paths } from './backend-api'

type ActiveSatellitesResponse =
  paths['/api/satellites/active']['get']['responses']['200']['content']['application/json']

export type Satellite = ActiveSatellitesResponse['satellites'][number]

const apiBaseUrl = 'http://localhost:8000'

export async function fetchActiveSatellites(limit = 50): Promise<ActiveSatellitesResponse> {
  const response = await fetch(
    `${apiBaseUrl}/api/satellites/active?limit=${encodeURIComponent(limit)}`,
  )

  if (!response.ok) {
    throw new Error(`Satellite request failed with status ${response.status}`)
  }

  const payload: unknown = await response.json()
  if (!payload || typeof payload !== 'object' || !('satellites' in payload)) {
    throw new Error('Satellite response did not contain a satellite list')
  }

  const satellites = (payload as { satellites: unknown }).satellites
  if (!Array.isArray(satellites) || satellites.some((satellite) => (
    !satellite
    || typeof satellite !== 'object'
    || typeof (satellite as { name?: unknown }).name !== 'string'
    || typeof (satellite as { altitude_km?: unknown }).altitude_km !== 'number'
  ))) {
    throw new Error('Satellite response is missing altitude data; restart the backend')
  }

  return payload as ActiveSatellitesResponse
}
