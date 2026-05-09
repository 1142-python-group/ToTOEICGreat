// ════════════════════════════════════════════════
// Supabase 設定（填入你自己的值）
// ════════════════════════════════════════════════
const SUPABASE_URL = "https://xhlwsnflkrkfpweoljgj.supabase.co/"
const SUPABASE_KEY = "sb_publishable_zvLO9NWN8b8WM2TL7fcfHg_VMxwv67B"

const { createClient } = supabase
const supabaseClient = createClient(SUPABASE_URL, SUPABASE_KEY)

// ════════════════════════════════════════════════
// Auth 相關函式，給 app.js 呼叫
// ════════════════════════════════════════════════
// 註冊
async function authSignUp(email, password) {
  // 只需要呼叫這一行
  // 因為資料庫的 Trigger (on_auth_user_created) 會在你呼叫完這行的瞬間，
  // 自動在背景幫你把資料填入 public.users 表。
  const { data, error } = await supabaseClient.auth.signUp({ email, password })
  
  if (error) throw new Error(error.message)
  
  return data 
}
// 登入
async function authSignIn(email, password) {
  const { data, error } = await supabaseClient.auth.signInWithPassword({ email, password })
  if (error) throw new Error(error.message)
  return data
}

// 登出
async function authSignOut() {
  const { error } = await supabaseClient.auth.signOut()
  if (error) throw new Error(error.message)
}

// 取得目前登入狀態（頁面重整後恢復 session 用）
async function getSession() {
  const { data } = await supabaseClient.auth.getSession()
  return data.session  // 未登入時回傳 null
}