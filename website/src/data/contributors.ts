/**
 * contributors.ts - build the community page's contributor cards from git.
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
import { createHash } from "node:crypto";

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

function isShallowRepository(repoPath: string): boolean {
  try {
    return execSync("git rev-parse --is-shallow-repository", {
      cwd: repoPath,
      encoding: "utf8",
    }).trim() === "true";
  } catch {
    return false;
  }
}

const repoRoot = resolveRepoRoot();
const shallowRepository = isShallowRepository(repoRoot);

// Hand-maintained profile metadata for humans we know should collapse into one
// card even when they have multiple commit identities.
const contributorProfiles: Record<string, { name: string; github?: string }> = {
  "ashwini-chaudhary": { name: "Ashwini Chaudhary", github: "https://github.com/ashwch" },
  "amal-raj-br": { name: "Amal Raj B R", github: "https://github.com/amalrajdiversio" },
  "umanga-bhattarai": { name: "Umanga Bhattarai", github: "https://github.com/bumang" },
  ashish581d: { name: "ashish581d", github: "https://github.com/ashish581d" },
  "little-person": { name: "Little Person", github: "https://github.com/little-person" },
};

function hashEmail(email: string): string {
  return createHash("sha256").update(email).digest("hex");
}

// Hashed email -> canonical contributor id. The source repo already contains
// commit-author emails in git history, but the website source does not need to
// repeat those literal addresses just to merge known aliases.
const contributorAliases: Record<string, string> = {
  "9c7ab890b573f70c062d3858ffbd343d062b08398efd8eefe5c2b6b1d6ff147d": "ashwini-chaudhary",
  "bb1aa0ae5d62afa0607a9b2cc5adfee4fcc84d79127a350b5ea177d8f64b4b5b": "ashwini-chaudhary",
  "c8d63c056019e471b8e05049ad79be6cfb279e633c975d2275c69d9120bf5bb3": "amal-raj-br",
  "4a79bcb2a4c30fa5a0fa0eebe67365a63422ff08a490ab1f0dcad0ba39eb23c3": "amal-raj-br",
  "06acac4f6b18a4724a1bc9daa2b620f8cc699ddf8406dc29869665d99525bc80": "umanga-bhattarai",
  "f0338f36ac3d11404f0d475a835e01bfac36b6ee2e611cf051757f24a082a0fa": "umanga-bhattarai",
  "d224ba123ab97d168d01ef253c22a99e87608ffbe2177b00280fab54178abe1e": "ashish581d",
  "b80d90359dac5ca72d3f003acf329ee50ee187e236ddd2cc9f94713aecc5312d": "ashish581d",
  "00e63def06e3e8aed42ee11bd60b87ba1756450783b565974ad31b3cb1099c94": "little-person",
};

// Safety net for environments where the git checkout is shallow, missing, or
// otherwise unavailable at build time.
//
// Why shallow checkouts matter:
// - CI often clones only the newest commit by default
// - `git log --all` then makes the site think the repo has only one author
// - a small, hand-maintained fallback is less wrong in public than showing a
//   fake "1 contributor" result on the live site
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

    const id = contributorAliases[hashEmail(email)] ?? slugify(name);
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

export const contributorsSource: "git" | "fallback" = (() => {
  if (shallowRepository) return "fallback";

  try {
    return getContributorsFromGit().length > 0 ? "git" : "fallback";
  } catch {
    return "fallback";
  }
})();

export const contributors: Contributor[] = (() => {
  if (contributorsSource === "fallback") return fallbackContributors;
  return getContributorsFromGit();
})();
