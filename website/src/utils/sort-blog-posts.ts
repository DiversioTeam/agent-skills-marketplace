type BlogLikePost = {
  id: string;
  data: {
    publishDate: Date;
    updatedDate?: Date;
    slug?: string;
    title: string;
  };
};

export function sortBlogPosts<T extends BlogLikePost>(posts: T[]): T[] {
  return [...posts].sort((a, b) => {
    const publishDelta = b.data.publishDate.getTime() - a.data.publishDate.getTime();
    if (publishDelta !== 0) return publishDelta;

    const updatedA = a.data.updatedDate?.getTime() ?? 0;
    const updatedB = b.data.updatedDate?.getTime() ?? 0;
    const updatedDelta = updatedB - updatedA;
    if (updatedDelta !== 0) return updatedDelta;

    const slugA = (a.data.slug ?? a.id).replace(/\.md$/, "");
    const slugB = (b.data.slug ?? b.id).replace(/\.md$/, "");
    const slugCompare = slugA.localeCompare(slugB);
    if (slugCompare !== 0) return slugCompare;

    return a.data.title.localeCompare(b.data.title);
  });
}
