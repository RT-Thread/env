import { describe, expect, it } from 'vitest'
import { communityWebsites, isCommunityView } from './community'

describe('built-in community views', () => {
  it('exposes documentation as the only external view', () => {
    expect(communityWebsites).toEqual([
      { id: 'documentation', title: '文档中心', url: 'https://www.rt-thread.org/document/site/' },
    ])
    expect(isCommunityView('documentation')).toBe(true)
  })

  it('rejects the removed forum and other unsupported views', () => {
    for (const view of ['forum', 'home', 'plugins', 'settings', '', 'https://club.rt-thread.org']) {
      expect(isCommunityView(view)).toBe(false)
    }
  })
})
