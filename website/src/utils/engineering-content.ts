import type {
  EngineeringHighlight,
  EngineeringHighlightLane,
} from "../data/engineering-highlights";

export function getOrderedEngineeringHighlightLanes(
  highlights: EngineeringHighlight[],
  orderedLanes: EngineeringHighlightLane[]
): EngineeringHighlightLane[] {
  const discoveredLanes = [...new Set(highlights.map((highlight) => highlight.lane))];
  const unknownLanes = discoveredLanes.filter((lane) => !orderedLanes.includes(lane));

  if (unknownLanes.length > 0) {
    throw new Error(
      `engineeringHighlights contains lane(s) missing from engineeringHighlightLaneOrder: ${unknownLanes.join(", ")}`
    );
  }

  return orderedLanes.filter((lane) => discoveredLanes.includes(lane));
}

export function getEngineeringHighlightsBySlug(
  highlights: EngineeringHighlight[],
  slugs: string[]
): EngineeringHighlight[] {
  const resolved = slugs.map((slug) => {
    const highlight = highlights.find((candidate) => candidate.slug === slug);
    if (!highlight) {
      throw new Error(`Missing engineering highlight for slug: ${slug}`);
    }
    return highlight;
  });

  const duplicateSlugs = slugs.filter((slug, index) => slugs.indexOf(slug) !== index);
  if (duplicateSlugs.length > 0) {
    throw new Error(`Duplicate engineering highlight slug(s) requested: ${duplicateSlugs.join(", ")}`);
  }

  return resolved;
}
