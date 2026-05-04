// Central website configuration.
//
// Why this file exists:
// - brand/domain strings were starting to drift across layouts, pages, and docs
// - the site is no longer a single landing page; it now has multiple sections
// - future changes like a hostname move or nav rename should happen in one place
//
// Mental model:
// - content pages decide *what they say*
// - this file decides *what the site is called* and *where sections live*
//
// If you rename a section or move a top-level route, update this file first,
// then update any page copy that refers to the old name.
export const siteConfig = {
  siteName: "Diversio Engineering",
  siteUrl: "https://engineering.diversio.com",
  toolsSectionName: "Agentic Tools",
  blogSectionName: "Blog",
  githubUrl: "https://github.com/DiversioTeam/agent-skills-marketplace",
  defaultDescription:
    "Diversio Engineering shares agentic tools, deep docs, and engineering writing.",
  routes: {
    home: "/",
    tools: "/agentic-tools",
    docs: "/docs",
    registry: "/registry",
    skills: "/skills",
    pi: "/pi",
    blog: "/blog",
    community: "/community",
    security: "/security",
    terms: "/terms",
  },
  navItems: [
    { label: "Home", href: "/", key: "home" },
    { label: "Agentic Tools", href: "/agentic-tools", key: "tools" },
    { label: "Docs", href: "/docs", key: "docs" },
    { label: "Blog", href: "/blog", key: "blog" },
    { label: "Community", href: "/community", key: "community" },
  ],
};

export default siteConfig;
