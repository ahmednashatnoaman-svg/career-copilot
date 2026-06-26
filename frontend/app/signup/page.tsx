"use client"
import { useState } from "react"
import Link from "next/link"
import { createClient } from "@/lib/supabase"
import { useRouter } from "next/navigation"

export default function SignupPage() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [name, setName] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState(false)
  const router = useRouter()
  const supabase = createClient()

  async function handleSignup(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: { data: { full_name: name } }
    })
    if (error) {
      setError(error.message)
      setLoading(false)
    } else {
      setSuccess(true)
    }
  }

  if (success) {
    return (
      <main className="min-h-screen flex items-center justify-center bg-background px-4">
        <div className="w-full max-w-sm space-y-4 text-center">
          <h2 className="font-display text-2xl font-semibold text-foreground">Check your email</h2>
          <p className="text-sm text-muted-foreground">We sent a confirmation link to <strong>{email}</strong>. Click it to activate your account.</p>
          <Link href="/login" className="text-sm text-foreground underline underline-offset-2">Back to sign in</Link>
        </div>
      </main>
    )
  }

  return (
    <main className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm space-y-8">
        <div className="space-y-1">
          <span className="editorial-rule" aria-hidden="true" />
          <h1 className="font-display text-3xl font-semibold text-foreground">Create account</h1>
          <p className="text-sm text-muted-foreground">Start your career journey</p>
        </div>
        <form onSubmit={handleSignup} className="space-y-4">
          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Full name</label>
            <input
              type="text"
              value={name}
              onChange={e => setName(e.target.value)}
              className="w-full px-3 py-2 bg-transparent border border-border rounded-md text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-foreground/20"
              placeholder="Alex Johnson"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Email</label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              className="w-full px-3 py-2 bg-transparent border border-border rounded-md text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-foreground/20"
              placeholder="you@example.com"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Password</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              minLength={6}
              className="w-full px-3 py-2 bg-transparent border border-border rounded-md text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-foreground/20"
              placeholder="min 6 characters"
            />
          </div>
          {error && <p className="text-sm text-red-500">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2 px-4 bg-foreground text-background text-sm font-medium rounded-md hover:bg-foreground/90 transition-colors disabled:opacity-50"
          >
            {loading ? "Creating…" : "Create account"}
          </button>
        </form>
        <p className="text-center text-sm text-muted-foreground">
          Have an account?{" "}
          <Link href="/login" className="text-foreground underline underline-offset-2">Sign in</Link>
        </p>
      </div>
    </main>
  )
}
