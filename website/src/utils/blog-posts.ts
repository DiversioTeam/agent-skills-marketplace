import { getCollection, type CollectionEntry } from "astro:content";
import { sortBlogPosts } from "./sort-blog-posts";

export type BlogPost = CollectionEntry<"blog">;

export async function getPublishedBlogPosts(): Promise<BlogPost[]> {
  const posts = sortBlogPosts(
    (await getCollection("blog")).filter((post) => !post.data.draft)
  );

  const featuredPosts = posts.filter((post) => post.data.featured);
  if (featuredPosts.length > 1) {
    const slugs = featuredPosts.map((post) => post.data.slug ?? post.id).join(", ");
    throw new Error(`Only one blog post may set featured: true. Found: ${slugs}`);
  }

  return posts;
}
