import { useState, useEffect } from 'react'
import { supabase } from '@/lib/supabase'
import type { User } from '@supabase/supabase-js'

export function useAuth() {
  const [user,    setUser]    = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [isAdmin, setIsAdmin] = useState(false)

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      const u = data.session?.user ?? null
      setUser(u)
      setLoading(false)
      if (u) checkAdmin(u.id)
    })
    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      const u = session?.user ?? null
      setUser(u)
      if (u) checkAdmin(u.id)
      else   setIsAdmin(false)
    })
    return () => listener.subscription.unsubscribe()
  }, [])

  async function checkAdmin(userId: string) {
    const { data } = await supabase
      .from('admin_users')
      .select('user_id')
      .eq('user_id', userId)
    setIsAdmin((data?.length ?? 0) > 0)
  }

  const signUp = (email: string, password: string) =>
    supabase.auth.signUp({ email, password })

  const signIn = (email: string, password: string) =>
    supabase.auth.signInWithPassword({ email, password })

  const signOut = () => supabase.auth.signOut()

  const getToken = async () => {
    const { data } = await supabase.auth.getSession()
    return data.session?.access_token ?? null
  }

  return { user, loading, isAdmin, signUp, signIn, signOut, getToken }
}