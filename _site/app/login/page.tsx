'use client';

import { Suspense, useState } from 'react';
import { useRouter } from 'next/navigation';

function LoginForm() {
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(false);

    const res = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password }),
    });

    if (res.ok) {
      router.push('/');
      router.refresh();
    } else {
      setError(true);
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-lg border border-slate-200 p-6">
      <label htmlFor="password" className="block text-sm font-medium text-slate-700 mb-2">
        输入密码
      </label>
      <input
        id="password"
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm
          focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        placeholder="请输入访问密码"
        autoFocus
        required
      />
      {error && (
        <p className="text-red-500 text-sm mt-2">密码错误，请重试</p>
      )}
      <button
        type="submit"
        disabled={loading}
        className="w-full mt-4 px-4 py-2 bg-blue-600 text-white text-sm font-medium
          rounded-md hover:bg-blue-700 disabled:opacity-50 transition-colors"
      >
        {loading ? '验证中...' : '进入'}
      </button>
    </form>
  );
}

export default function LoginPage() {
  return (
    <main className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <h1 className="text-xl font-bold text-slate-800 text-center mb-6">个人空间</h1>
        <Suspense>
          <LoginForm />
        </Suspense>
      </div>
    </main>
  );
}
