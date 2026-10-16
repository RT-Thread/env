export const communityWebsites = [
  { id: 'documentation', title: '文档中心', url: 'https://www.rt-thread.org/document/site/' },
] as const

export type CommunityWebsite = typeof communityWebsites[number]

export function isCommunityView(view: string): boolean {
  return communityWebsites.some((website) => website.id === view)
}
