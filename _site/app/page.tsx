import Link from 'next/link';
import { getContentTree, type FileNode } from '@/lib/content';

function FileTree({ nodes, depth = 0 }: { nodes: FileNode[]; depth?: number }) {
  return (
    <ul className={depth === 0 ? '' : 'ml-4 border-l border-slate-200 pl-3'}>
      {nodes.map((node) => (
        <li key={node.path} className="py-0.5">
          {node.type === 'directory' ? (
            <>
              <span className="text-slate-500 text-sm font-medium">
                📂 {node.name}
              </span>
              {node.children && <FileTree nodes={node.children} depth={depth + 1} />}
            </>
          ) : (
            <Link
              href={`/view/${node.path}`}
              className="text-blue-600 hover:text-blue-800 text-sm hover:underline block py-0.5"
            >
              📄 {node.name.replace(/\.md$/, '')}
            </Link>
          )}
        </li>
      ))}
    </ul>
  );
}

export default function HomePage() {
  const tree = getContentTree();

  return (
    <main className="max-w-2xl mx-auto px-4 py-6">
      <header className="mb-6">
        <h1 className="text-xl font-bold text-slate-800">个人空间</h1>
        <p className="text-sm text-slate-500 mt-1">工作待办 · 复盘记录 · 知识沉淀</p>
      </header>

      <div className="space-y-4">
        {tree.map((section) => (
          <section
            key={section.key}
            className="bg-white rounded-lg border border-slate-200 p-4"
          >
            <h2 className="text-base font-semibold text-slate-700 mb-2">
              {section.label}
            </h2>
            <FileTree nodes={section.children} />
          </section>
        ))}
      </div>
    </main>
  );
}
