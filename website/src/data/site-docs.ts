/**
 * site-docs.ts — build-time doc extraction for the website's deeper pages.
 *
 * Why this file exists
 * --------------------
 * The registry cards and package summary pages are good at answering
 * "what bundle is this?", but they are not good at answering
 * "what does this individual skill or Pi extension actually do?"
 *
 * The source of truth already lives in the repo itself:
 * - plugins/<plugin>/skills/<skill>/SKILL.md
 * - pi-packages/<package>/README.md
 * - pi-packages/<package>/skills/<skill>/SKILL.md
 *
 * This file is the glue that turns those real repo files into page data for:
 * - /skills/*
 * - /pi/*
 *
 * Mental model
 * ------------
 * marketplace.json   -> card metadata and high-level catalog summaries
 * SKILL.md / README  -> human-authored deep docs and examples
 * site-docs.ts       -> conservative build-time extraction layer
 *
 * Design principle
 * ----------------
 * Keep the extraction logic simple and explainable.
 * We prefer a few stable heuristics over a "perfect" markdown parser.
 * If a page looks wrong, fix the source docs first, then teach this file the
 * new shape in a narrow, obvious way.
 */
import { execSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import marketplace from "./marketplace.json";

interface MarketplaceSkill {
  name: string;
  description: string;
}

interface MarketplacePlugin {
  name: string;
  category: string;
  title: string;
  description: string;
  version: string;
  skills: MarketplaceSkill[];
  commands: string[];
}

interface MarketplacePiPackage {
  name: string;
  title: string;
  description: string;
  version: string;
}

export interface StructuredSection {
  heading: string;
  slug: string;
  paragraphs: string[];
  bullets: string[];
  codeBlocks: { lang: string; code: string }[];
}

export interface SkillDoc {
  kind: "plugin-skill" | "pi-skill";
  name: string;
  title: string;
  description: string;
  sourcePath: string;
  sourceUrl: string;
  packageName: string;
  packageTitle: string;
  packageVersion: string;
  packageCategory: string;
  packageDocHref: string;
  allowedTools: string[];
  relatedCommands: string[];
  packageCommands: string[];
  references: string[];
  scripts: string[];
  sections: StructuredSection[];
}

export interface PiPackageDoc {
  name: string;
  title: string;
  description: string;
  version: string;
  packagePath: string;
  packageUrl: string;
  packageDocHref: string;
  extensionPath: string | null;
  extensionFiles: string[];
  packagedSkills: { name: string; href: string }[];
  commandRows: { command: string; description: string }[];
  toolRows: { tool: string; description: string }[];
  environmentItems: string[];
  shortcutItems: string[];
  installCode: string | null;
  localTestCode: string | null;
  sections: StructuredSection[];
}

const plugins = marketplace.plugins as MarketplacePlugin[];
const piPackages = marketplace.piPackages as MarketplacePiPackage[];

// Build-time pages can run from the website directory or from a bundled Astro
// execution context. Ask git for the repo root first so we can always find the
// real marketplace files, then fall back to a simple parent-directory guess.
function resolveRepoRoot(): string {
  try {
    return execSync("git rev-parse --show-toplevel", {
      cwd: process.cwd(),
      encoding: "utf8",
    }).trim();
  } catch {
    return path.resolve(process.cwd(), "..");
  }
}

const repoRoot = resolveRepoRoot();
const githubBase = "https://github.com/DiversioTeam/agent-skills-marketplace/tree/main";

function readText(relativePath: string): string {
  return readFileSync(path.join(repoRoot, relativePath), "utf8");
}

function slugify(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function stripInlineMarkdown(value: string): string {
  return value
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, "$1")
    .replace(/<[^>]+>/g, "")
    .replace(/\\/g, "")
    .trim();
}

function identifierToTitle(identifier: string): string {
  return identifier
    .split("-")
    .filter(Boolean)
    .map((part) => (part.length <= 2 ? part.toUpperCase() : `${part[0]?.toUpperCase() ?? ""}${part.slice(1)}`))
    .join(" ");
}

function titleFromHeading(rawHeading: string, fallbackIdentifier: string): string {
  const normalizedHeading = rawHeading.replace(/\s+skill$/i, "").trim();
  const normalizedIdentifier = fallbackIdentifier.replace(/-/g, " ").toLowerCase();

  if (!normalizedHeading || normalizedHeading === "Untitled") {
    return identifierToTitle(fallbackIdentifier);
  }

  if (normalizedHeading.toLowerCase().includes(normalizedIdentifier)) {
    return normalizedHeading;
  }

  return identifierToTitle(fallbackIdentifier);
}

function normalizeFrontmatterScalar(value: string): string {
  return value.replace(/^['\"]|['\"]$/g, "").trim();
}

// We only need a tiny subset of frontmatter today. Keep the parser intentionally
// narrow so future readers can see exactly what we rely on.
function parseFrontmatter(raw: string): Record<string, string | string[]> {
  const match = raw.match(/^---\n([\s\S]*?)\n---\n?/);
  if (!match) return {};

  const data: Record<string, string | string[]> = {};
  const lines = match[1].split("\n");

  for (let index = 0; index < lines.length; index += 1) {
    const parts = lines[index]?.match(/^([A-Za-z0-9_-]+):\s*(.*)$/);
    if (!parts) continue;

    const [, key, rawValue] = parts;
    const value = rawValue.trim();

    if (key === "allowed-tools") {
      if (value) {
        data[key] = normalizeFrontmatterScalar(value).split(/\s+/).filter(Boolean);
        continue;
      }

      const tools: string[] = [];
      while (index + 1 < lines.length) {
        const nextLine = lines[index + 1] ?? "";
        const listItem = nextLine.match(/^\s+-\s+(.*)$/);
        if (!listItem) break;
        tools.push(normalizeFrontmatterScalar(listItem[1] ?? ""));
        index += 1;
      }
      data[key] = tools;
      continue;
    }

    if (value === ">" || value === ">-" || value === "|") {
      const blockLines: string[] = [];
      while (index + 1 < lines.length) {
        const nextLine = lines[index + 1] ?? "";
        if (!/^\s+/.test(nextLine)) break;
        blockLines.push(nextLine.replace(/^\s+/, ""));
        index += 1;
      }

      data[key] = value === "|"
        ? blockLines.join("\n").trim()
        : blockLines.join(" ").replace(/\s+/g, " ").trim();
      continue;
    }

    if (!value) continue;
    data[key] = normalizeFrontmatterScalar(value);
  }

  return data;
}

function stripFrontmatter(raw: string): string {
  return raw.replace(/^---\n[\s\S]*?\n---\n?/, "").trim();
}

function parseCodeBlocks(content: string): { lang: string; code: string }[] {
  const blocks: { lang: string; code: string }[] = [];
  const regex = /```([^\n`]*)\n([\s\S]*?)```/g;
  let match: RegExpExecArray | null;
  while ((match = regex.exec(content)) !== null) {
    blocks.push({
      lang: match[1].trim() || "text",
      code: match[2].trim(),
    });
  }
  return blocks;
}

function stripCodeFences(content: string): string {
  return content.replace(/```[\s\S]*?```/g, "");
}

function extractBullets(content: string): string[] {
  const bullets: string[] = [];
  const lines = stripCodeFences(content).split("\n");
  let current: string | null = null;

  for (const rawLine of lines) {
    const line = rawLine.replace(/\t/g, "    ");
    const trimmed = line.trim();

    if (/^[-*]\s+/.test(trimmed)) {
      if (current) bullets.push(stripInlineMarkdown(current));
      current = trimmed.replace(/^[-*]\s+/, "");
      continue;
    }

    if (current && /^\s{2,}\S/.test(line)) {
      current += ` ${trimmed}`;
      continue;
    }

    if (current) {
      bullets.push(stripInlineMarkdown(current));
      current = null;
    }
  }

  if (current) bullets.push(stripInlineMarkdown(current));
  return bullets;
}

function extractParagraphs(content: string): string[] {
  const paragraphs: string[] = [];
  const lines = stripCodeFences(content).split("\n");
  let buffer: string[] = [];

  const flush = () => {
    if (buffer.length === 0) return;
    const text = stripInlineMarkdown(buffer.join(" ").replace(/\s+/g, " ")).trim();
    if (text) paragraphs.push(text);
    buffer = [];
  };

  for (const rawLine of lines) {
    const trimmed = rawLine.trim();
    if (!trimmed) {
      flush();
      continue;
    }
    if (
      trimmed.startsWith("#") ||
      trimmed.startsWith("|") ||
      /^[-*]\s+/.test(trimmed) ||
      /^\d+\.\s+/.test(trimmed)
    ) {
      flush();
      continue;
    }
    buffer.push(trimmed);
  }

  flush();
  return paragraphs;
}

// Split markdown into H1/H2-based chunks so route pages can show a readable,
// first-principles summary instead of dumping the whole source file inline.
function parseMarkdownSections(raw: string): { title: string; sections: StructuredSection[] } {
  const body = stripFrontmatter(raw);
  const lines = body.split("\n");
  const sections: { heading: string; lines: string[] }[] = [];
  let title = "Untitled";
  let current: { heading: string; lines: string[] } | null = null;

  for (const line of lines) {
    const heading = line.match(/^(#{1,6})\s+(.*)$/);
    if (heading) {
      const depth = heading[1].length;
      const headingTitle = stripInlineMarkdown(heading[2]);
      if (depth === 1) {
        title = headingTitle;
        continue;
      }
      if (depth === 2) {
        if (current) sections.push(current);
        current = { heading: headingTitle, lines: [] };
        continue;
      }
    }
    if (current) current.lines.push(line);
  }

  if (current) sections.push(current);

  return {
    title,
    sections: sections.map((section) => {
      const content = section.lines.join("\n").trim();
      return {
        heading: section.heading,
        slug: slugify(section.heading),
        paragraphs: extractParagraphs(content),
        bullets: extractBullets(content),
        codeBlocks: parseCodeBlocks(content),
      } satisfies StructuredSection;
    }),
  };
}

function listRelativeFiles(relativeDir: string): string[] {
  const absoluteDir = path.join(repoRoot, relativeDir);
  if (!existsSync(absoluteDir)) return [];

  const results: string[] = [];
  const walk = (dir: string, prefix = "") => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      if (entry.name === "__pycache__" || entry.name.startsWith(".")) continue;

      const rel = prefix ? `${prefix}/${entry.name}` : entry.name;
      if (entry.isDirectory()) {
        walk(path.join(dir, entry.name), rel);
        continue;
      }

      if (entry.name.endsWith(".pyc")) continue;
      results.push(rel);
    }
  };

  walk(absoluteDir);
  return results.sort();
}

// The site is meant to be skimmable. Pick the sections that usually answer
// "when should I use this?" and "what is special about it?" first.
function pickRelevantSections(sections: StructuredSection[], kind: "skill" | "pi"): StructuredSection[] {
  const preferred = kind === "skill"
    ? [
        /when to use/i,
        /example prompts|representative prompt/i,
        /modes|lane routing|digest-first preflight|detection workflow|core taste|output expectations|applicability/i,
      ]
    : [
        /what it does|problem|solution|why this package exists|mental model|how this relates|how it finds the skills|configuration|requirements/i,
      ];

  const picks: StructuredSection[] = [];
  for (const pattern of preferred) {
    const match = sections.find((section) => pattern.test(section.heading) && !picks.includes(section));
    if (match) picks.push(match);
  }

  for (const section of sections) {
    if (picks.length >= 4) break;
    if (/install|contributing|commands|llm tools|environment|ui shortcuts|team setup|verify/i.test(section.heading)) continue;
    if (!picks.includes(section)) picks.push(section);
  }

  return picks.slice(0, 4);
}

function parseTableGroups(content: string): string[][][] {
  const groups: string[][][] = [];
  let current: string[] = [];

  for (const rawLine of content.split("\n")) {
    const line = rawLine.trim();
    if (line.startsWith("|")) {
      current.push(line);
      continue;
    }

    if (current.length > 0) {
      groups.push(
        current.map((row) =>
          row
            .split("|")
            .slice(1, -1)
            .map((cell) => stripInlineMarkdown(cell.trim()))
        )
      );
      current = [];
    }
  }

  if (current.length > 0) {
    groups.push(
      current.map((row) =>
        row
          .split("|")
          .slice(1, -1)
          .map((cell) => stripInlineMarkdown(cell.trim()))
      )
    );
  }

  return groups.filter((group) => group.length >= 3);
}

function extractEnvItems(readme: string): string[] {
  const sections = [findSectionContent(readme, /^environment\b/i), findSectionContent(readme, /^configuration\b/i)]
    .filter(Boolean)
    .join("\n\n");

  if (!sections) return [];

  const bulletItems = extractBullets(sections);
  const tableItems = parseTableGroups(sections)
    .flatMap((group) => group.slice(2))
    .map((row) => {
      const variable = row[0] ?? "";
      const defaultValue = row[1] ?? "";
      const description = row[row.length - 1] ?? "";
      if (!variable || variable === "---" || !description) return "";
      return defaultValue
        ? `${variable} (default: ${defaultValue}) — ${description}`
        : `${variable} — ${description}`;
    })
    .filter(Boolean);
  const envLines = parseCodeBlocks(sections)
    .flatMap((block) => block.code.split("\n"))
    .map((line) => line.trim())
    .filter((line) => /^(export\s+)?[A-Z0-9_]+=/.test(line));

  return [...new Set([...bulletItems, ...tableItems, ...envLines])];
}

function findSectionContent(readme: string, heading: RegExp): string | null {
  const body = stripFrontmatter(readme);
  const lines = body.split("\n");
  let collecting = false;
  const chunk: string[] = [];

  for (const line of lines) {
    const match = line.match(/^##\s+(.*)$/);
    if (match) {
      if (collecting) break;
      collecting = heading.test(stripInlineMarkdown(match[1]));
      continue;
    }
    if (collecting) chunk.push(line);
  }

  return collecting ? chunk.join("\n").trim() : null;
}

function buildCommandMap(plugin: MarketplacePlugin): Map<string, string[]> {
  const map = new Map<string, string[]>();
  for (const skill of plugin.skills) map.set(skill.name, []);

  for (const command of plugin.commands) {
    const commandPath = `plugins/${plugin.name}/commands/${command}.md`;
    if (!existsSync(path.join(repoRoot, commandPath))) continue;
    const content = readText(commandPath);
    const matchedSkills = plugin.skills
      .map((skill) => skill.name)
      .filter((skillName) => content.includes(`\`${skillName}\``) || content.includes(skillName));

    if (matchedSkills.length === 1) {
      map.get(matchedSkills[0])?.push(`/${plugin.name}:${command}`);
      continue;
    }

    if (plugin.skills.length === 1) {
      map.get(plugin.skills[0].name)?.push(`/${plugin.name}:${command}`);
      continue;
    }

    const exactNameMatch = plugin.skills.find((skill) => skill.name === command);
    if (exactNameMatch) {
      map.get(exactNameMatch.name)?.push(`/${plugin.name}:${command}`);
    }
  }

  return map;
}

// Wrapper commands live at the plugin level, but skill pages need to answer
// "which slash command should I actually run?" This map bridges that gap.
const pluginCommandMaps = new Map<string, Map<string, string[]>>();
for (const plugin of plugins) {
  pluginCommandMaps.set(plugin.name, buildCommandMap(plugin));
}

function collectPiPackageSkillDocs(): SkillDoc[] {
  const docs: SkillDoc[] = [];

  for (const pkg of piPackages) {
    const skillsDir = `pi-packages/${pkg.name}/skills`;
    const absoluteSkillsDir = path.join(repoRoot, skillsDir);
    if (!existsSync(absoluteSkillsDir)) continue;

    for (const entry of readdirSync(absoluteSkillsDir, { withFileTypes: true })) {
      if (!entry.isDirectory()) continue;
      const skillName = entry.name;
      const skillPath = `${skillsDir}/${skillName}`;
      const skillMdPath = `${skillPath}/SKILL.md`;
      if (!existsSync(path.join(repoRoot, skillMdPath))) continue;

      const raw = readText(skillMdPath);
      const parsed = parseMarkdownSections(raw);
      const frontmatter = parseFrontmatter(raw);
      docs.push({
        kind: "pi-skill",
        name: skillName,
        title: titleFromHeading(parsed.title, skillName),
        description: String(frontmatter.description ?? `Pi-local skill shipped with ${pkg.title}.`),
        sourcePath: skillPath,
        sourceUrl: `${githubBase}/${skillPath}`,
        packageName: pkg.name,
        packageTitle: pkg.title,
        packageVersion: pkg.version,
        packageCategory: "Pi Package",
        packageDocHref: `/pi/${pkg.name}`,
        allowedTools: Array.isArray(frontmatter["allowed-tools"]) ? frontmatter["allowed-tools"] as string[] : [],
        relatedCommands: [],
        packageCommands: [],
        references: listRelativeFiles(`${skillPath}/references`),
        scripts: listRelativeFiles(`${skillPath}/scripts`),
        sections: pickRelevantSections(parsed.sections, "skill"),
      });
    }
  }

  return docs;
}

const pluginSkillDocs: SkillDoc[] = plugins.flatMap((plugin) => {
  const commandMap = pluginCommandMaps.get(plugin.name) ?? new Map<string, string[]>();
  return plugin.skills.map((skill) => {
    const skillPath = `plugins/${plugin.name}/skills/${skill.name}`;
    const raw = readText(`${skillPath}/SKILL.md`);
    const parsed = parseMarkdownSections(raw);
    const frontmatter = parseFrontmatter(raw);

    return {
      kind: "plugin-skill",
      name: skill.name,
      title: titleFromHeading(parsed.title, skill.name),
      description: skill.description,
      sourcePath: skillPath,
      sourceUrl: `${githubBase}/${skillPath}`,
      packageName: plugin.name,
      packageTitle: plugin.title,
      packageVersion: plugin.version,
      packageCategory: plugin.category,
      packageDocHref: `/docs/${plugin.name}`,
      allowedTools: Array.isArray(frontmatter["allowed-tools"]) ? frontmatter["allowed-tools"] as string[] : [],
      relatedCommands: commandMap.get(skill.name) ?? [],
      packageCommands: plugin.commands.map((command) => `/${plugin.name}:${command}`),
      references: listRelativeFiles(`${skillPath}/references`),
      scripts: listRelativeFiles(`${skillPath}/scripts`),
      sections: pickRelevantSections(parsed.sections, "skill"),
    } satisfies SkillDoc;
  });
});

// Final page payloads used by /skills/* routes.
export const skillDocs: SkillDoc[] = [...pluginSkillDocs, ...collectPiPackageSkillDocs()].sort((a, b) =>
  a.title.localeCompare(b.title)
);

// Pi package READMEs already document commands/tools in markdown tables.
// Reuse that authoring format instead of creating a second website-only schema.
function parseReadmeTable(readme: string, heading: RegExp): { name: string; description: string }[] {
  const content = findSectionContent(readme, heading);
  if (!content) return [];

  return parseTableGroups(content)
    .flatMap((group) => group.slice(2))
    .map((row) => ({
      name: row[0] ?? "",
      description: row[row.length - 1] ?? "",
    }))
    .filter((row) => row.name && row.description && row.name !== "---");
}

function parseReadmeBullets(readme: string, heading: RegExp): string[] {
  const content = findSectionContent(readme, heading);
  return content ? extractBullets(content) : [];
}

function firstCodeBlockForHeading(readme: string, heading: RegExp): string | null {
  const content = findSectionContent(readme, heading);
  if (!content) return null;
  return parseCodeBlocks(content)[0]?.code ?? null;
}

// Final page payloads used by /pi/* routes.
export const piPackageDocs: PiPackageDoc[] = piPackages.map((pkg) => {
  const readmePath = `pi-packages/${pkg.name}/README.md`;
  const rawReadme = readText(readmePath);
  const parsedReadme = parseMarkdownSections(rawReadme);
  const extensionBase = `pi-packages/${pkg.name}/extensions`;
  const extensionNames = existsSync(path.join(repoRoot, extensionBase))
    ? readdirSync(path.join(repoRoot, extensionBase), { withFileTypes: true })
        .filter((entry) => entry.isDirectory())
        .map((entry) => entry.name)
    : [];
  const primaryExtension = extensionNames[0] ? `${extensionBase}/${extensionNames[0]}` : null;
  const commandRows = parseReadmeTable(rawReadme, /^commands$/i).map((row) => ({
    command: row.name,
    description: row.description,
  }));
  const toolRows = parseReadmeTable(rawReadme, /^llm tools$/i).map((row) => ({
    tool: row.name,
    description: row.description,
  }));

  return {
    name: pkg.name,
    title: pkg.title,
    description: pkg.description,
    version: pkg.version,
    packagePath: `pi-packages/${pkg.name}`,
    packageUrl: `${githubBase}/pi-packages/${pkg.name}`,
    packageDocHref: `/docs/${pkg.name}`,
    extensionPath: primaryExtension,
    extensionFiles: primaryExtension ? listRelativeFiles(primaryExtension) : [],
    packagedSkills: skillDocs
      .filter((skill) => skill.kind === "pi-skill" && skill.packageName === pkg.name)
      .map((skill) => ({ name: skill.name, href: `/skills/${skill.name}` })),
    commandRows,
    toolRows,
    environmentItems: extractEnvItems(rawReadme),
    shortcutItems: parseReadmeBullets(rawReadme, /^ui shortcuts$/i),
    installCode: firstCodeBlockForHeading(rawReadme, /^install$/i),
    localTestCode:
      firstCodeBlockForHeading(rawReadme, /^verify$/i) ??
      firstCodeBlockForHeading(rawReadme, /^contributing and local testing$/i),
    sections: pickRelevantSections(parsedReadme.sections, "pi"),
  } satisfies PiPackageDoc;
}).sort((a, b) => a.title.localeCompare(b.title));

export function getSkillDoc(name: string): SkillDoc | undefined {
  return skillDocs.find((skill) => skill.name === name);
}

export function getPiPackageDoc(name: string): PiPackageDoc | undefined {
  return piPackageDocs.find((pkg) => pkg.name === name);
}
