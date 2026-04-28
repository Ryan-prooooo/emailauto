import { beforeEach, describe, expect, it, vi } from 'vitest'

const { getMock, postMock, putMock } = vi.hoisted(() => ({
  getMock: vi.fn(),
  postMock: vi.fn(),
  putMock: vi.fn(),
}))

vi.mock('./index', () => ({
  default: {
    get: getMock,
    post: postMock,
    put: putMock,
  },
  unwrap: <T>(promise: Promise<T>) => promise,
}))

import { systemApi } from './system'

describe('systemApi', () => {
  beforeEach(() => {
    getMock.mockReset()
    postMock.mockReset()
    putMock.mockReset()
  })

  it('returns typed scheduler parse results without page-level casting', async () => {
    postMock.mockResolvedValue({ processed: 3, failed: 1 })

    await expect(systemApi.triggerParse()).resolves.toEqual({
      processed: 3,
      failed: 1,
    })
  })

  it('returns typed scheduler sync results without page-level casting', async () => {
    postMock.mockResolvedValue({ success: true, synced: 5, errors: [] })

    await expect(systemApi.triggerSync()).resolves.toEqual({
      success: true,
      synced: 5,
      errors: [],
    })
  })
})
