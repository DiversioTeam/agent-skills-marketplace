type BlogSurfacePost = {
  id: string;
  data: {
    sourceType: "original" | "repost";
    featured?: boolean;
  };
};

export function pickFeaturedBlogPost<T extends BlogSurfacePost>(posts: T[]): T | undefined {
  const featuredOriginal = posts.find((post) => post.data.featured && post.data.sourceType === "original");
  if (featuredOriginal) return featuredOriginal;

  const featuredAny = posts.find((post) => post.data.featured);
  if (featuredAny) return featuredAny;

  const firstOriginal = posts.find((post) => post.data.sourceType === "original");
  if (firstOriginal) return firstOriginal;

  return posts[0];
}
