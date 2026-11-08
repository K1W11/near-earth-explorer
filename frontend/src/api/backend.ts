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
): Promise<Narration> {
  const body: NarrationRequest = { object_name: name, object_type: type }
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
