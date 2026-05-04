如何用API創建user/登入user




Reasoned

Ran load_knowledge

Ran search_docs

Ran search_docs

Ran search_docs

Ran search_docs

Ran search_docs
下面用 Supabase Auth API 說明「如何用 API 建立 user / 登入 user」。我先給你最常用的兩條路徑：(A) 一般註冊/登入（Client 端）、(B) 用管理 API（Admin）直接建立使用者（後台用）。

A. 一般流程：Sign up（建立 user） + Sign in（登入）
這種是讓使用者用 email+password 註冊/登入。

1) 註冊（建立 user）
用 supabase.auth.signUp()（需要 anon / sb_publishable... 這類 publishable key）

import
 { createClient } 
from
 
'@supabase/supabase-js'

const
 supabase = createClient(
'https://<project-ref>.supabase.co'
, 
'sb_publishable_...'
)
const
 { data, error } = 
await
 supabase.auth.signUp({
  
email
: 
'user@example.com'
,
  
password
: 
'example-password'
,
  
options
: {
    
// 若你有 email confirmation，可加 redirect

    
emailRedirectTo
: 
'https://example.com/welcome'
,
  },
})

註冊成功後，通常需要使用者去收信完成確認（依你的 Auth 設定）。

2) 登入（Sign in）
用 supabase.auth.signInWithPassword()

const
 { data, error } = 
await
 supabase.auth.signInWithPassword({
  
email
: 
'user@example.com'
,
  
password
: 
'example-password'
,
})

登入成功後 data.session 會有 access_token/refresh_token。

B. Admin API：直接用 API 建立 user（後台用）
若你想「不用使用者手動註冊」，而是你後台程式用 API 直接建立（例如邀請、匯入使用者），用 admin createUser。

重點：這需要 service_role key（絕對不能放前端）。

import
 { createClient } 
from
 
'@supabase/supabase-js'

const
 supabaseAdmin = createClient(
  
'https://<project-ref>.supabase.co'
,
  
'SUPABASE_SERVICE_ROLE_KEY'

)
const
 { data, error } = 
await
 supabaseAdmin.auth.admin.createUser({
  
email
: 
'user@example.com'
,
  
password
: 
'supersecurepassword123!'
, 
// 或你有 password_hash 也可以走 password_hash

  
email_confirm
: 
true
, 
// 是否直接視為已確認（依你的需求）

})

你要用哪一種「登入/註冊」？
你回我兩個問題，我就可以把 API 路徑寫到完全對應你的情境（含 curl 或程式碼）：

你用的是 email+password 還是 magic link / OTP？
建 user 你希望是 使用者自行註冊（用 anon）還是 你後台直接建立（用 service_role admin）？
（另外：你是要用 curl 還是 Node/TS？）



