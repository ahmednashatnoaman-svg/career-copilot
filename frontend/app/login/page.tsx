"use client"
import { useState } from "react"
import Link from "next/link"
import { createClient } from "@/lib/supabase"
import { useRouter } from "next/navigation"

export default function LoginPage() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const router = useRouter()
  const supabase = createClient()

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) {
      setError(error.message)
      setLoading(false)
    } else {
      router.push("/")
      router.refresh()
    }
  }

  async function handleGoogleLogin() {
    await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${window.location.origin}/auth/callback` }
    })
  }

  return (
    <main className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm space-y-8">
        <div className="space-y-1">
          <span className="editorial-rule" aria-hidden="true" />
          <h1 className="font-display text-3xl font-semibold text-foreground">Career Copilot</h1>
          <p className="text-sm text-muted-foreground">Sign in to your account</p>
        </div>

        <form onSubmit={handleLogin} className="space-y-4">
          <div className="space-y-1">
            <label htmlFor="email" className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              className="w-full px-3 py-2 bg-transparent border border-border rounded-md text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-1 focus:ring-foreground/20"
              placeholder="you@example.com"
            />
          </div>
          <div className="space-y-1">
            <label htmlFor="password" className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              className="w-full px-3 py-2 bg-transparent border border-border rounded-md text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-1 focus:ring-foreground/20"
              placeholder="••••••••"
            />
          </div>
          {error && <p className="text-sm text-red-500">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2 px-4 bg-foreground text-background text-sm font-medium rounded-md hover:bg-foreground/90 transition-colors disabled:opacity-50"
          >
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <div className="relative">
          <div className="absolute inset-0 flex items-center"><span className="w-full border-t border-border" /></div>
          <div className="relative flex justify-center text-xs text-muted-foreground"><span className="bg-background px-2">or</span></div>
        </div>

        <button
          onClick={handleGoogleLogin}
          className="w-full py-2 px-4 border border-border text-sm font-medium rounded-md hover:bg-foreground/5 transition-colors"
        >
          Continue with Google
        </button>

        <p className="text-center text-sm text-muted-foreground">
          No account?{" "}
          <Link href="/signup" className="text-foreground underline underline-offset-2">Sign up</Link>
        </p>
      </div>
    </main>
  )
}
