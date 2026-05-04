# 004 - Blog and syndication content model

## v1 publishing model

Use local Astro content collections inside `website/src/content/blog/`.

This keeps the first version explicit, reviewable, and git-based.

## Supported post types

- `original` - an original Diversio Engineering post
- `repost` - a curated repost from an external source such as `ashwch.com`

## Minimum schema

Defined in `website/src/content.config.ts`.

Fields:

- `title`
- `slug`
- `summary`
- `publishDate`
- `updatedDate`
- `author`
- `tags`
- `sourceType`
- `sourceSiteName`
- `sourceUrl`
- `canonicalUrl`
- `heroImage`
- `socialImage`
- `socialTitle`
- `socialDescription`
- `draft`

## Canonical and attribution rules

- original posts may use the site URL as canonical
- reposts must include both `sourceUrl` and `canonicalUrl`
- repost pages must visibly label the source
- repost pages should keep attribution explicit in both UI and metadata decisions

## Operations note

To add a post:

1. add a markdown file under `website/src/content/blog/`
2. fill in the collection schema fields
3. use `sourceType: repost` only when source attribution and canonical URL are ready
4. run `cd website && npm run build`
