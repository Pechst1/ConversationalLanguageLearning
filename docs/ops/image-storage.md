# Durable image storage (Cloudflare R2)

Generated images (Feuilleton panels, Revue plates, Le Papier's story pictures, panel art)
must outlive a deploy. Render's container disk is wiped on every deploy, so production
keeps them in an S3-compatible bucket. Until the bucket is set, `GRAPHIC_NOVEL_IMAGE_GENERATION_ENABLED`
and the plate painters stay on the SVG / known-plate fallback and draw nothing: each
Papier story shows its place's season plate instead of its own picture (WP-119 §8.4).

Once the bucket is set, the next morning's intake paints the week's story pictures (one
each, final, about $0.06 apiece). To paint them the same day: `POST /api/v1/revue/admin/paint`
as an admin (queued; `?enqueue=false` paints in the request and returns the report).

Cloudflare R2 is the cheapest fit: 10 GB, 1 M uploads and 10 M reads a month free, and
no charge for downloads. A panel is ~1–2 MB, so the free tier holds several thousand.

## 1. Create the bucket (Cloudflare)

1. Sign in at <https://dash.cloudflare.com> (a free account works).
2. Left menu → **R2 Object Storage**. The first time, Cloudflare asks for a payment
   method to enable R2; nothing is charged inside the free tier.
3. **Create bucket** → name `atelier-images` → Location: Automatic (or the
   *Western Europe* hint, next to Render Frankfurt) → **Create bucket**.
4. In the bucket → **Settings** → **Public Development URL** → **Enable** → type
   `allow` → copy the URL (`https://pub-….r2.dev`). The app links images from it.
5. Back on **R2 Object Storage** → **API** → **Manage API tokens** → **Create
   Account API token**: name `atelier-render`, permission **Object Read & Write**,
   *Apply to specific buckets only* → `atelier-images` → **Create**.
6. Copy the three values the next page shows once: **Access Key ID**, **Secret
   Access Key**, and the S3 endpoint `https://<account-id>.r2.cloudflarestorage.com`.

## 2. Tell the API (Render)

Render dashboard → **atelier-api** → **Environment** → set these, then **Save, rebuild,
and deploy**. The worker inherits them from the API (render.yaml `fromService`).

| Key | Value |
|---|---|
| `GRAPHIC_NOVEL_IMAGE_STORAGE` | `s3` |
| `GRAPHIC_NOVEL_IMAGE_S3_BUCKET` | `atelier-images` |
| `GRAPHIC_NOVEL_IMAGE_S3_REGION` | `auto` |
| `GRAPHIC_NOVEL_IMAGE_S3_ENDPOINT_URL` | `https://<account-id>.r2.cloudflarestorage.com` |
| `GRAPHIC_NOVEL_IMAGE_S3_ACCESS_KEY_ID` | the Access Key ID |
| `GRAPHIC_NOVEL_IMAGE_S3_SECRET_ACCESS_KEY` | the Secret Access Key |
| `GRAPHIC_NOVEL_IMAGE_S3_PUBLIC_BASE_URL` | `https://pub-….r2.dev` |

Leave `GRAPHIC_NOVEL_IMAGE_S3_ACL` unset: R2 has no object ACLs; the public URL is
what makes the images readable.

## Later

The `r2.dev` URL is rate-limited and meant for development. Once the app is public,
connect a custom domain to the bucket (bucket → Settings → Custom Domains) and change
`GRAPHIC_NOVEL_IMAGE_S3_PUBLIC_BASE_URL` to it. Stored images keep their keys, so
only the new links change.
