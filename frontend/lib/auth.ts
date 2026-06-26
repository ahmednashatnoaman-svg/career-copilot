import { createClient } from './supabase'

export async function getUser() {
  const supabase = createClient()
  const { data: { user } } = await supabase.auth.getUser()
  return user
}

export async function signOut() {
  const supabase = createClient()
  await supabase.auth.signOut()
  window.location.href = '/login'
}

export async function getUserId(): Promise<string> {
  const user = await getUser()
  return user?.id ?? 'anonymous'
}
