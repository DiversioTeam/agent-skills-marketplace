import { engineeringHighlights } from "../data/engineering-highlights";
import { engineeringStack } from "../data/engineering-stack";
import { plugins, piPackages } from "../data/marketplace.json";
import { openSourceProjects } from "../data/open-source-projects";
import { getPublishedBlogPosts, type BlogPost } from "./blog-posts";

export interface SiteMetrics {
  pluginCount: number;
  piPackageCount: number;
  toolSurfaceCount: number;
  totalSkills: number;
  publishedPostCount: number;
  originalPostCount: number;
  repostCount: number;
  systemsHighlightCount: number;
  stackLayerCount: number;
  openRepoCount: number;
}

export async function getSiteMetrics(publishedPosts?: BlogPost[]): Promise<SiteMetrics> {
  const resolvedPosts = publishedPosts ?? await getPublishedBlogPosts();
  const originalPostCount = resolvedPosts.filter((post) => post.data.sourceType === "original").length;
  const repostCount = resolvedPosts.filter((post) => post.data.sourceType === "repost").length;
  const totalSkills = plugins.reduce((sum, plugin) => sum + plugin.skills.length, 0);

  return {
    pluginCount: plugins.length,
    piPackageCount: piPackages.length,
    toolSurfaceCount: plugins.length + piPackages.length,
    totalSkills,
    publishedPostCount: resolvedPosts.length,
    originalPostCount,
    repostCount,
    systemsHighlightCount: engineeringHighlights.length,
    stackLayerCount: engineeringStack.length,
    openRepoCount: openSourceProjects.length + 1,
  };
}
