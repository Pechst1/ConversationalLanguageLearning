export type GraphicNovelPanelImageSource = {
  image_url?: string | null;
  image_payload?: {
    url?: unknown;
  } | null;
} | null | undefined;

export function panelImageUrl(panel: GraphicNovelPanelImageSource) {
  const directUrl = typeof panel?.image_url === 'string' ? panel.image_url.trim() : '';
  if (directUrl) return directUrl;
  const payloadUrl = panel?.image_payload?.url;
  return typeof payloadUrl === 'string' && payloadUrl.trim() ? payloadUrl.trim() : '';
}
