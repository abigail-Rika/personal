import { notFound } from 'next/navigation';
import Link from 'next/link';
import { marked } from 'marked';
import { getAllMarkdownPaths, getMarkdownContent } from '@/lib/content';

marked.use({
  gfm: true,
  breaks: true,
});

export function generateStaticParams() {
  return getAllMarkdownPaths().map((p) => ({
    path: p.split('/'),
  }));
}

export default async function ViewPage({
  params,
}: {
  params: Promise<{ path: string[] }>;
}) {
  const { path: segments } = await params;
  const filePath = segments.join('/');
  const data = getMarkdownContent(filePath);

  if (!data) notFound();

  const html = await marked(data.content);

  return (
    <main className="max-w-2xl mx-auto px-4 py-6">
      <nav className="mb-4">
        <Link href="/" className="text-blue-600 hover:underline text-sm">
          ← 返回目录
        </Link>
      </nav>

      <article className="bg-white rounded-lg border border-slate-200 p-5">
        <div
          className="prose prose-slate prose-sm max-w-none
            prose-headings:font-semibold
            prose-a:text-blue-600
            prose-code:bg-slate-100 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-sm
            prose-pre:bg-slate-800 prose-pre:text-slate-100
            prose-table:text-sm
            prose-th:bg-slate-50
            prose-img:rounded-lg"
          dangerouslySetInnerHTML={{ __html: html }}
        />
      </article>

      <footer className="mt-4 text-center">
        <Link href="/" className="text-blue-600 hover:underline text-sm">
          ← 返回目录
        </Link>
      </footer>
    </main>
  );
}
