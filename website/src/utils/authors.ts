export interface AuthorRecord {
  name: string;
  url?: string;
}

export interface AuthorSummary {
  slug: string;
  name: string;
  url?: string;
  postCount: number;
}

export function slugifyAuthorName(name: string): string {
  return name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export function getAuthorHref(name: string): string {
  return `/authors/${slugifyAuthorName(name)}`;
}

export function summarizeAuthors(authors: AuthorRecord[]): AuthorSummary[] {
  const grouped = new Map<string, AuthorSummary>();

  for (const author of authors) {
    const slug = slugifyAuthorName(author.name);
    const existing = grouped.get(slug);
    if (existing) {
      existing.postCount += 1;
      existing.url ||= author.url;
      continue;
    }
    grouped.set(slug, {
      slug,
      name: author.name,
      url: author.url,
      postCount: 1,
    });
  }

  return [...grouped.values()].sort((a, b) => b.postCount - a.postCount || a.name.localeCompare(b.name));
}
