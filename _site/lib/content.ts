import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';

const ROOT = process.cwd();

const CONTENT_DIRS = ['work', 'diary', 'reviews', 'knowledge', 'skills', 'thoughts'];

const EXCLUDED_PATTERNS = [
  'node_modules', '.next', '.vercel', '.git', '.cursor',
  'app', 'lib', 'public',
];

const DIR_LABELS: Record<string, string> = {
  work: '工作',
  diary: '日记',
  reviews: '复盘',
  knowledge: '知识',
  skills: '技能',
  thoughts: '想法',
};

export interface FileNode {
  name: string;
  path: string;
  type: 'file' | 'directory';
  children?: FileNode[];
}

function shouldExclude(name: string): boolean {
  return name.startsWith('.') || EXCLUDED_PATTERNS.includes(name) || name.endsWith('.log');
}

function scanDir(dirPath: string, relativeTo: string): FileNode[] {
  if (!fs.existsSync(dirPath)) return [];

  const entries = fs.readdirSync(dirPath, { withFileTypes: true });
  const nodes: FileNode[] = [];

  for (const entry of entries) {
    if (shouldExclude(entry.name)) continue;

    const fullPath = path.join(dirPath, entry.name);
    const relPath = path.relative(relativeTo, fullPath);

    if (entry.isDirectory()) {
      const children = scanDir(fullPath, relativeTo);
      if (children.length > 0) {
        nodes.push({ name: entry.name, path: relPath, type: 'directory', children });
      }
    } else if (entry.name.endsWith('.md')) {
      nodes.push({
        name: entry.name,
        path: relPath.replace(/\.md$/, ''),
        type: 'file',
      });
    }
  }

  nodes.sort((a, b) => {
    if (a.type !== b.type) return a.type === 'directory' ? -1 : 1;
    return b.name.localeCompare(a.name);
  });

  return nodes;
}

export function getContentTree(): { label: string; key: string; children: FileNode[] }[] {
  return CONTENT_DIRS
    .map((dir) => ({
      label: DIR_LABELS[dir] || dir,
      key: dir,
      children: scanDir(path.join(ROOT, dir), ROOT),
    }))
    .filter((section) => section.children.length > 0);
}

export function getAllMarkdownPaths(): string[] {
  const paths: string[] = [];

  function collect(nodes: FileNode[]) {
    for (const node of nodes) {
      if (node.type === 'file') paths.push(node.path);
      if (node.children) collect(node.children);
    }
  }

  for (const dir of CONTENT_DIRS) {
    collect(scanDir(path.join(ROOT, dir), ROOT));
  }

  return paths;
}

export function getMarkdownContent(filePath: string): {
  content: string;
  title: string;
  frontmatter: Record<string, unknown>;
} | null {
  const fullPath = path.join(ROOT, filePath + '.md');
  if (!fs.existsSync(fullPath)) return null;

  const raw = fs.readFileSync(fullPath, 'utf-8');
  const { data, content } = matter(raw);

  const titleMatch = content.match(/^#\s+(.+)$/m);
  const title = (data.name as string) || (titleMatch ? titleMatch[1] : path.basename(filePath));

  return { content, title, frontmatter: data };
}
