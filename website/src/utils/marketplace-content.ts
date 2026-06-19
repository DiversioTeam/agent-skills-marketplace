type NamedMarketplaceItem = {
  name: string;
};

export function getMarketplaceItemsBySlug<T extends NamedMarketplaceItem>(
  items: T[],
  slugs: readonly string[]
): T[] {
  const duplicateSlugs = slugs.filter((slug, index) => slugs.indexOf(slug) !== index);
  if (duplicateSlugs.length > 0) {
    throw new Error(`Duplicate marketplace slug(s) requested: ${duplicateSlugs.join(", ")}`);
  }

  return slugs.map((slug) => {
    const item = items.find((candidate) => candidate.name === slug);
    if (!item) {
      throw new Error(`Missing marketplace item for slug: ${slug}`);
    }
    return item;
  });
}
