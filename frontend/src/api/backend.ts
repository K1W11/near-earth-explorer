import type { paths } from './backend-api'

type ActiveSatellitesResponse =
  paths['/api/satellites/active']['get']['responses']['200']['content']['application/json']

export type Satellite = ActiveSatellitesResponse['satellites'][number]

export type SatelliteOverview = {
  name: string
  norad_catalog_number: string
  classification: string
  international_designator: string
  elements_epoch: string
  altitude_km: number | null
  orbit_class: string
  orbit_description: string
  orbital_period_minutes: number
  inclination_degrees: number
  eccentricity: number
  right_ascension_ascending_node_degrees: number
  argument_of_perigee_degrees: number
  mean_anomaly_degrees: number
  mean_motion_revolutions_per_day: number
  revolutions_at_epoch: string
  tle1: string
  tle2: string
}
export type SatelliteNarrationCategory = 'overview' | 'orbital_position' | 'tracking'
export type AssistantResponse = {
  query: string
  executed_tools: Array<{ name: string; args: Record<string, unknown>; result: unknown }>
  response: string
}

const apiBaseUrl = 'http://localhost:8000'

export async function askAssistant(query: string): Promise<AssistantResponse> {
  const response = await fetch(`${apiBaseUrl}/api/assistant/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  })
  if (!response.ok) {
    let detail = `Assistant request failed with status ${response.status}`
    try {
      const body: unknown = await response.json()
      if (typeof (body as { detail?: unknown })?.detail === 'string') {
        detail = (body as { detail: string }).detail
      }
    } catch {
      // Use the status message when the backend response is not JSON.
    }
    throw new Error(detail)
  }
  const payload: unknown = await response.json()
  if (!payload || typeof payload !== 'object' || typeof (payload as { response?: unknown }).response !== 'string') {
    throw new Error('Assistant response did not contain an answer')
  }
  return payload as AssistantResponse
}

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
    || !(
      typeof (satellite as { altitude_km?: unknown }).altitude_km === 'number'
      || (satellite as { altitude_km?: unknown }).altitude_km === null
    )
  ))) {
    throw new Error('Satellite response is missing altitude data; restart the backend')
  }

  return payload as ActiveSatellitesResponse
}

export async function fetchSatelliteOverview(name: string): Promise<SatelliteOverview> {
  const response = await fetch(
    `${apiBaseUrl}/api/satellites/overview?name=${encodeURIComponent(name)}`,
  )
  if (!response.ok) {
    throw new Error(`Satellite overview request failed with status ${response.status}`)
  }
  return response.json() as Promise<SatelliteOverview>
}

type NarrationRequest =
  paths['/api/audio/narrate']['post']['requestBody']['content']['application/json']

export type NarrationTargetType = NarrationRequest['object_type']

export type Narration = {
  /** Object URL for the mp3. Release it with URL.revokeObjectURL when done. */
  audioUrl: string
  /** The exact text that was spoken ('' if the backend didn't send it). */
  transcript: string
}

/** Turn a failed response into a readable message (the backend sends `{ detail }`). */
async function narrationErrorMessage(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json()
    const detail = (body as { detail?: unknown } | null)?.detail
    if (typeof detail === 'string' && detail) return detail
  } catch {
    // Body was not JSON; fall through to the generic message.
  }
  return `Narration request failed with status ${response.status}`
}

/**
 * Fetch the narration for one map object.
 *
 * The route is a POST, so an <audio src> tag cannot call it; we fetch the mp3
 * as a blob and give the player an object URL instead. The spoken text arrives
 * percent-encoded in the X-Narration-Text header.
 */
export async function narrateTarget(
  name: string,
  type: NarrationTargetType,
  category: SatelliteNarrationCategory = 'overview',
): Promise<Narration> {
  const body: NarrationRequest = { object_name: name, object_type: type, category }
  const response = await fetch(`${apiBaseUrl}/api/audio/narrate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    throw new Error(await narrationErrorMessage(response))
  }

  const header = response.headers.get('X-Narration-Text') ?? ''
  let transcript = header
  try {
    transcript = decodeURIComponent(header)
  } catch {
    // Malformed escape sequence: show the raw header rather than failing.
  }

  const audioBlob = await response.blob()
  return { audioUrl: URL.createObjectURL(audioBlob), transcript }
}
