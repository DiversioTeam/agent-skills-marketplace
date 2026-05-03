/**
 * contributors.ts — build the community page's contributor cards from git.
 *
 * First principles
 * ----------------
 * A contributor list should age with the repository, not with a hardcoded array
 * buried in a component. Git already knows who authored the history, so we ask
 * git first and only fall back to static data when git metadata is unavailable
 * during a build.
 *
 * The logic here stays intentionally simple:
 * - drop obvious bot authors
 * - merge known human aliases across multiple emails
 * - infer GitHub profile links from noreply addresses when possible
 * - keep a tiny fallback list so static builds never fail
 */
import { execSync } from "node:child_process";

export interface Contributor {
  id: string;
  name: string;
  commits: number;
  initials: string;
  github?: string;
}

function resolveRepoRoot(): string {
  try {
    return execSync("git rev-parse --show-toplevel", {
      cwd: process.cwd(),
      encoding: "utf8",
    }).trim();
  } catch {
    return process.cwd();
  }
}

const repoRoot = resolveRepoRoot();

// Hand-maintained profile metadata for humans we know should collapse into one
// card even when they have multiple commit identities.
const contributorProfiles: Record<string, { name: string; github?: string }> = {
  "ashwini-chaudhary": { name: "Ashwini Chaudhary", github: "https://github.com/ashwch" },
  "amal-raj-br": { name: "Amal Raj B R", github: "https://github.com/amalrajdiversio" },
  "umanga-bhattarai": { name: "Umanga Bhattarai", github: "https://github.com/bumang" },
  ashish581d: { name: "ashish581d", github: "https://github.com/ashish581d" },
  "little-person": { name: "Little Person", github: "https://github.com/little-person" },
};

// Email -> canonical contributor id. This is the smallest, easiest-to-audit
// place to teach the site that two commit emails belong to one person.
const contributorAliases: Record<string, string> = {
  "ashwch3018@gmail.com": "ashwini-chaudhary",
  "ashwch@users.noreply.github.com": "ashwini-chaudhary",
  "amal@diversio.com": "amal-raj-br",
  "97768599+amalrajdiversio@users.noreply.github.com": "amal-raj-br",
  "umangabhattarai11@gmail.com": "umanga-bhattarai",
  "44160507+bumang@users.noreply.github.com": "umanga-bhattarai",
  "ashish@diversio.com": "ashish581d",
  "ashishsiwal13@gmail.com": "ashish581d",
  "109978238+little-person@users.noreply.github.com": "little-person",
};

// Safety net for environments where the git checkout is shallow, missing, or
// otherwise unavailable at build time.
const fallbackContributors: Contributor[] = [
  { id: "ashwini-chaudhary", name: "Ashwini Chaudhary", commits: 194, initials: "AC" },
  { id: "amal-raj-br", name: "Amal Raj B R", commits: 30, initials: "AR", github: "https://github.com/amalrajdiversio" },
  { id: "umanga-bhattarai", name: "Umanga Bhattarai", commits: 17, initials: "UB", github: "https://github.com/bumang" },
  { id: "ashish581d", name: "ashish581d", commits: 14, initials: "AS", github: "https://github.com/ashish581d" },
  { id: "little-person", name: "Little Person", commits: 1, initials: "LP", github: "https://github.com/little-person" },
];

function isBot(name: string, email: string): boolean {
  const haystack = `${name} ${email}`.toLowerCase();
  return haystack.includes("[bot]") || haystack.includes(" bot") || haystack.includes("bot@");
}

function slugify(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function inferGitHubProfile(email: string): string | undefined {
  if (!email.endsWith("@users.noreply.github.com")) return undefined;
  const local = email.split("@", 1)[0] ?? "";
  const handle = local.includes("+") ? local.split("+", 2)[1] : local;
  return handle ? `https://github.com/${handle}` : undefined;
}

function initialsFromName(name: string): string {
  const parts = name
    .split(/[^A-Za-z0-9]+/)
    .filter(Boolean);

  if (parts.length === 0) return "??";
  if (parts.length === 1) {
    return parts[0].slice(0, 2).toUpperCase();
  }
  return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
}

function pickDisplayName(names: string[]): string {
  return [...names].sort((a, b) => {
    const aHasSpace = a.includes(" ") ? 1 : 0;
    const bHasSpace = b.includes(" ") ? 1 : 0;
    if (aHasSpace !== bHasSpace) return bHasSpace - aHasSpace;
    if (a.length !== b.length) return b.length - a.length;
    return a.localeCompare(b);
  })[0];
}

function getContributorsFromGit(): Contributor[] {
  // We count authored commits, not merged PRs or review activity, because git is
  // the source we always have locally during a static build.
  const output = execSync("git log --format='%aN|%aE' --all", {
    cwd: repoRoot,
    encoding: "utf8",
  }).trim();

  const grouped = new Map<string, { commits: number; names: Set<string>; github?: string }>();

  for (const line of output.split("\n")) {
    const [rawName = "", rawEmail = ""] = line.split("|");
    const name = rawName.trim();
    const email = rawEmail.trim().toLowerCase();
    if (!name || !email || isBot(name, email)) continue;

    const id = contributorAliases[email] ?? slugify(name);
    const existing = grouped.get(id) ?? {
      commits: 0,
      names: new Set<string>(),
      github: contributorProfiles[id]?.github,
    };

    existing.commits += 1;
    existing.names.add(name);
    existing.github ||= inferGitHubProfile(email);
    grouped.set(id, existing);
  }

  return [...grouped.entries()]
    .map(([id, entry]) => {
      const profile = contributorProfiles[id];
      const name = profile?.name ?? pickDisplayName([...entry.names]);
      return {
        id,
        name,
        commits: entry.commits,
        initials: initialsFromName(name),
        github: profile?.github ?? entry.github,
      } satisfies Contributor;
    })
    .sort((a, b) => b.commits - a.commits || a.name.localeCompare(b.name));
}

export const contributors: Contributor[] = (() => {
  try {
    const fromGit = getContributorsFromGit();
    return fromGit.length > 0 ? fromGit : fallbackContributors;
  } catch {
    return fallbackContributors;
  }
})();
