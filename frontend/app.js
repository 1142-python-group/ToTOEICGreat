// ════════════════════════════════════════════════════════════
// 第一部分：API 層
// 所有打後端的請求都集中在這裡，元件不直接用 fetch
// ════════════════════════════════════════════════════════════

// ════════════════════════════════════════════════
// 登入畫面控制
// ════════════════════════════════════════════════

function showAuthScreen() {
  document.getElementById("auth-screen").style.display = "block"
  document.getElementById("app").style.display = "none"
}

function hideAuthScreen() {
  document.getElementById("auth-screen").style.display = "none"
  document.getElementById("app").style.display = "block"
}

function toggleAuthForm(type) {
  document.getElementById("login-error").textContent = ""
  document.getElementById("register-error").textContent = ""
  if (type === "register") {
    document.getElementById("login-form").style.display = "none"
    document.getElementById("register-form").style.display = "block"
  } else {
    document.getElementById("register-form").style.display = "none"
    document.getElementById("login-form").style.display = "block"
  }
}

async function handleLogin() {
  const email    = document.getElementById("login-email").value.trim()
  const password = document.getElementById("login-password").value
  const errorEl  = document.getElementById("login-error")
  const btn      = document.getElementById("login-btn")

  if (!email || !password) {
    errorEl.textContent = "請填入 Email 和密碼"
    return
  }

  btn.textContent = "登入中..."
  btn.disabled = true

  try {
    const data = await authSignIn(email, password)
    // 登入成功，更新 navbar 顯示的使用者名稱
    const appInstance = document.getElementById("app").__vue_app__
    // 直接更新 DOM 比較簡單
    document.querySelector(".navbar-username").textContent = data.user.email
    document.querySelector(".navbar-avatar").textContent =
      data.user.email.charAt(0).toUpperCase()
    hideAuthScreen()
  } catch(e) {
    errorEl.textContent = e.message === "Invalid login credentials"
      ? "Email 或密碼錯誤" : e.message
  } finally {
    btn.textContent = "登入"
    btn.disabled = false
  }
}

async function handleRegister() {
  const email    = document.getElementById("register-email").value.trim()
  const password = document.getElementById("register-password").value
  const errorEl  = document.getElementById("register-error")
  const btn      = document.getElementById("register-btn")

  if (!email || !password) {
    errorEl.textContent = "請填入 Email 和密碼"
    return
  }
  if (password.length < 6) {
    errorEl.textContent = "密碼至少需要 6 個字元"
    return
  }

  btn.textContent = "註冊中..."
  btn.disabled = true

  try {
    await authSignUp(email, password)
    // 註冊完直接登入
    const data = await authSignIn(email, password)
    document.querySelector(".navbar-username").textContent = data.user.email
    document.querySelector(".navbar-avatar").textContent =
      data.user.email.charAt(0).toUpperCase()
    hideAuthScreen()
  } catch(e) {
    errorEl.textContent = e.message
  } finally {
    btn.textContent = "註冊"
    btn.disabled = false
  }
}
// 登出
async function handleLogout() {
  try {
    // 1. 呼叫 Supabase 登出 API
    await authSignOut()

    // 2. 顯示回你的登入/註冊彈窗或畫面 (假設你有這個函數，與 hideAuthScreen 相反)
    showAuthScreen()

    // 3. 把 Navbar 上的名字重置回預設狀態
    document.querySelector(".navbar-username").textContent = "遊客"
    document.querySelector(".navbar-avatar").textContent = "遊"

    // 4. 通知 Vue 切回首頁 (避免登出後還停留在需要權限的個人分析頁)
    const appInstance = document.getElementById("app").__vue_app__
    if (appInstance && appInstance._instance.proxy.showView) {
        appInstance._instance.proxy.showView('home')
    }

  } catch(e) {
    alert("登出失敗：" + e.message)
  }
}


const API_BASE = "http://localhost:8000/api"

const api = {
  // 開始考試：GET /api/quiz/start?count=5
  async startQuiz(count = 5) {
    const res = await fetch(`${API_BASE}/quiz/start?count=${count}`)
    if (!res.ok) throw new Error("無法取得題目，請確認後端是否正在運作")
    return res.json()  // 回傳 QuizSession { session_id, questions, time_limit_seconds }
  },

  // 交卷：POST /api/quiz/submit
  async submitQuiz(sessionId, answers, timeSpentPerQ) {
    const res = await fetch(`${API_BASE}/quiz/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessionId,
        answers: answers,           // { questionId(int): answerIndex(int) }
        time_spent_per_q: timeSpentPerQ
      })
    })
    if (!res.ok) throw new Error("交卷失敗")
    return res.json()  // 回傳 ExamResult
  },

  // 取得儀表板資料：GET /api/user/:id/stats
  async getUserStats(userId = "user_001") {
    const res = await fetch(`${API_BASE}/user/${userId}/stats`)
    if (!res.ok) throw new Error("無法取得使用者資料")
    return res.json()  // 回傳 UserStats
  },

  // 生成類似練習題：POST /api/quiz/generate-practice
  async generatePractice(questionId) {
    const res = await fetch(`${API_BASE}/quiz/generate-practice`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question_id: questionId })
    })
    if (!res.ok) throw new Error("生成失敗")
    return res.json()
  }
}

// ════════════════════════════════════════════════════════════
// 第二部分：Vue 元件定義
// ════════════════════════════════════════════════════════════

const { createApp, ref, reactive, computed, onMounted, onUnmounted, watch, nextTick } = Vue

// ── 首頁元件 ──────────────────────────────────────────────
const HomeView = {
  emits: ["start-quiz", "go-profile"],
  template: `
    <section class="view home-view">
      <div class="home-bg-watermark">益</div>
      <div class="home-card">
        <div class="home-eyebrow">★ AI 驅動練習</div>
        <h1 class="home-title">準備好突破你的<br>多益極限了嗎？</h1>
        <p class="home-subtitle">系統已根據你的歷史弱點，為你精選本次個人化試題。</p>
        <div class="home-btns">
          <button class="btn-primary" @click="$emit('start-quiz')" :disabled="loading">
            {{ loading ? "載入題目中..." : "▶ 開始專屬模擬測驗" }}
          </button>
          <button class="btn-secondary" @click="$emit('go-profile')">查看個人分析</button>
        </div>
        <div class="home-tags">
          <span class="home-tag">5 題</span>
          <span class="home-tag">限時 15 分鐘</span>
          <span class="home-tag">AI 解析啟用</span>
        </div>
        <p v-if="error" style="color:red;margin-top:12px;font-size:14px">{{ error }}</p>
      </div>
    </section>
  `,
  // props 從父元件接收 loading 和 error 狀態
  props: {
    loading: { type: Boolean, default: false },
    error:   { type: String,  default: "" }
  }
}

// ── 個人儀表板元件 ─────────────────────────────────────────
const ProfileView = {
  emits: ["go-home"],
  props: {
    userStats: { type: Object, default: null }
  },
  template: `
    <section class="view">
      <div class="profile-inner">
        <button class="profile-back-btn" @click="$emit('go-home')">← 返回首頁</button>

        <!-- 載入中 -->
        <div v-if="!userStats" style="text-align:center;padding:60px;color:#888">
          載入資料中...
        </div>

        <template v-else>
          <!-- 使用者資訊卡 -->
          <div class="profile-header-card">
            <div class="profile-big-avatar">黃</div>
            <div>
              <div class="profile-name">{{ userStats.username }}</div>
              <div class="profile-meta">總作答題數：{{ userStats.total_questions }} 題</div>
            </div>
          </div>

          <!-- 統計數字 -->
          <div class="stats-grid">
            <div class="stat-card">
              <div class="stat-label">預估測驗分數</div>
              <div class="stat-value">{{ userStats.estimated_score }}</div>
            </div>
            <div class="stat-card">
              <div class="stat-label">平均單題作答時間</div>
              <div class="stat-value">{{ userStats.avg_time_per_q.toFixed(0) }}<small> 秒</small></div>
            </div>
            <div class="stat-card">
              <div class="stat-label">好友排行</div>
              <div class="stat-value">Top 3</div>
            </div>
          </div>

          <!-- 圖表 -->
          <div class="charts-grid">
            <div class="chart-card">
              <div class="chart-title">歷史分數趨勢</div>
              <div class="chart-wrap">
                <!-- ref="lineCanvas" 讓我們在 JS 裡拿到這個 canvas 元素 -->
                <canvas ref="lineCanvas"></canvas>
              </div>
            </div>
            <div class="chart-card">
              <div class="chart-title">能力弱點分析</div>
              <div class="chart-wrap">
                <canvas ref="radarCanvas"></canvas>
              </div>
            </div>
          </div>
        </template>
      </div>
    </section>
  `,
  // setup() 是 Vue 3 Composition API 的核心
  setup(props) {
    const lineCanvas  = ref(null)  // 對應 template 裡的 ref="lineCanvas"
    const radarCanvas = ref(null)
    let lineChart = null
    let radarChart = null

    // 當元件掛載後，且有資料時，初始化圖表
    onMounted(async () => {
      // 等 Vue 把 DOM 畫完才能操作 canvas
      await nextTick()
      if (props.userStats) initCharts()
    })

    // 監聽 userStats 變化（第一次資料回來時畫圖）
    watch(() => props.userStats, async (newVal) => {
      if (newVal) {
        await nextTick()
        initCharts()
      }
    })

    function initCharts() {
      // 避免重複建立圖表（切換頁面回來時）
      if (lineChart) lineChart.destroy()
      if (radarChart) radarChart.destroy()

      const stats = props.userStats

      // 折線圖
      lineChart = new Chart(lineCanvas.value, {
        type: "line",
        data: {
          labels: stats.score_history.map(d => d.month),
          datasets: [{
            data: stats.score_history.map(d => d.score),
            borderColor: "#378ADD",
            backgroundColor: "rgba(55,138,221,0.08)",
            fill: true,
            tension: 0.4,
            pointBackgroundColor: "#185FA5",
            pointRadius: 4,
            borderWidth: 2
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            y: { min: 500, max: 990 },
            x: { grid: { display: false } }
          }
        }
      })

      // 雷達圖
      radarChart = new Chart(radarCanvas.value, {
        type: "radar",
        data: {
          labels: stats.radar_data.map(d => d.label),
          datasets: [{
            data: stats.radar_data.map(d => d.value),
            borderColor: "#BA7517",
            backgroundColor: "rgba(186,117,23,0.12)",
            borderWidth: 2,
            pointRadius: 4
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            r: { min: 0, max: 100, ticks: { display: false } }
          }
        }
      })
    }

    // 元件被銷毀前，釋放圖表資源（避免記憶體洩漏）
    onUnmounted(() => {
      if (lineChart)  lineChart.destroy()
      if (radarChart) radarChart.destroy()
    })

    return { lineCanvas, radarCanvas }
  }
}

// ── 測驗作答元件 ───────────────────────────────────────────
const QuizView = {
  emits: ["submit"],
  props: {
    session: { type: Object, required: true }
  },
  setup(props, { emit }) {
    const currentIndex = ref(0)
    const userAnswers  = reactive({})   // { questionId: answerIndex }
    const timeSpentPerQ = reactive({})  // { questionId: seconds }
    const secondsLeft  = ref(props.session.time_limit_seconds)
    let timerInterval  = null
    let qStartTime     = Date.now()

    // ── 計時器：只建立一次 ────────────────────────────────
    onMounted(() => {
      timerInterval = setInterval(() => {
        secondsLeft.value--
        // 同時累積當前題目的作答時間
        const qid = currentQuestion.value.id
        timeSpentPerQ[qid] = (timeSpentPerQ[qid] || 0) + 1

        if (secondsLeft.value <= 0) {
          clearInterval(timerInterval)
          doSubmit()
        }
      }, 1000)
    })

    onUnmounted(() => clearInterval(timerInterval))

    // ── Computed ──────────────────────────────────────────
    const questions      = computed(() => props.session.questions)
    const currentQuestion = computed(() => questions.value[currentIndex.value])
    const isLastQ        = computed(() => currentIndex.value === questions.value.length - 1)

    const timerDisplay = computed(() => {
      const m = Math.floor(secondsLeft.value / 60)
      const s = secondsLeft.value % 60
      return `${String(m).padStart(2,"0")}:${String(s).padStart(2,"0")}`
    })

    // ── 作答操作 ──────────────────────────────────────────
    function selectOption(optionIndex) {
      userAnswers[currentQuestion.value.id] = optionIndex
      // localStorage 備份
      try {
        localStorage.setItem("exam_backup", JSON.stringify({
          session_id: props.session.session_id,
          answers: userAnswers,
          currentIndex: currentIndex.value
        }))
      } catch(e) {}
    }

    function recordTimeAndJump(newIndex) {
      // 記錄離開當前題目時的花費時間
      const qid = currentQuestion.value.id
      timeSpentPerQ[qid] = (timeSpentPerQ[qid] || 0) +
        Math.round((Date.now() - qStartTime) / 1000)
      qStartTime = Date.now()
      currentIndex.value = newIndex
    }

    function prevQ() { if (currentIndex.value > 0) recordTimeAndJump(currentIndex.value - 1) }
    function nextQ() { if (!isLastQ.value) recordTimeAndJump(currentIndex.value + 1) }
    function jumpToQ(i) { recordTimeAndJump(i) }

    function doSubmit() {
      clearInterval(timerInterval)
      localStorage.removeItem("exam_backup")
      // 把所有資料往上傳給父元件處理（父元件負責打 API）
      emit("submit", {
        session_id: props.session.session_id,
        answers: { ...userAnswers },
        time_spent_per_q: { ...timeSpentPerQ }
      })
    }

    return {
      currentIndex, userAnswers, secondsLeft,
      currentQuestion, questions, isLastQ, timerDisplay,
      selectOption, prevQ, nextQ, jumpToQ, doSubmit
    }
  },
  template: `
    <section class="view">
      <div class="quiz-inner">
        <!-- 左側主作答區 -->
        <div class="quiz-main">
          <div class="quiz-header">
            <div>
              <div class="quiz-question-label">Question</div>
              <div class="quiz-question-num">
                {{ currentIndex + 1 }}
                <span style="color:#888;font-size:18px"> / {{ questions.length }}</span>
              </div>
            </div>
            <div class="quiz-timer" :class="{ urgent: secondsLeft < 120 }">
              ⏱ {{ timerDisplay }}
            </div>
          </div>

          <div class="quiz-card">
            <div class="quiz-tag">{{ currentQuestion.tag }}</div>
            <p class="quiz-question-text">{{ currentQuestion.text }}</p>
            <div class="option-list">
              <button
                v-for="(opt, i) in currentQuestion.options"
                :key="i"
                class="option-btn"
                :class="{ selected: userAnswers[currentQuestion.id] === i }"
                @click="selectOption(i)"
              >
                <!-- 選項字母圓圈 -->
                <span class="option-letter">{{ ['A','B','C','D'][i] }}</span>
                <!-- 去掉 "A. " 前綴只顯示內文 -->
                <span>{{ opt.replace(/^[A-D]\\. /, '') }}</span>
              </button>
            </div>
          </div>

          <div class="quiz-controls">
            <button class="btn-nav" @click="prevQ" :disabled="currentIndex === 0">← 上一題</button>
            <button v-if="!isLastQ" class="btn-nav" @click="nextQ">下一題 →</button>
            <button v-else class="btn-submit" @click="doSubmit">交卷</button>
          </div>
        </div>

        <!-- 右側題號導覽 -->
        <div class="quiz-sidebar">
          <div class="sidebar-card">
            <div class="sidebar-title">題目導覽</div>
            <div class="q-grid">
              <button
                v-for="(q, i) in questions"
                :key="q.id"
                class="q-btn"
                :class="{
                  current:  i === currentIndex,
                  answered: userAnswers[q.id] !== undefined
                }"
                @click="jumpToQ(i)"
              >{{ i + 1 }}</button>
            </div>
            <div class="q-legend">
              <div class="legend-item"><span class="legend-dot current-dot"></span>目前題目</div>
              <div class="legend-item"><span class="legend-dot answered-dot"></span>已作答</div>
              <div class="legend-item"><span class="legend-dot empty-dot"></span>未作答</div>
            </div>
          </div>
        </div>
      </div>
    </section>
  `
}

// ── 考後解析元件 ───────────────────────────────────────────
const ResultView = {
  emits: ["go-home", "go-profile"],
  props: {
    result: { type: Object, required: true }
  },
  setup(props) {
    const openItems = reactive({})   // 哪些題目面板是展開的

    function toggleItem(id) {
      openItems[id] = !openItems[id]
    }

    async function requestPractice(questionId) {
      try {
        const data = await api.generatePractice(questionId)
        alert(`AI 生成的練習題：\n${data.text}`)
        // TODO: 正式版改成在頁面上渲染新題目
      } catch(e) {
        alert("生成失敗，請稍後再試")
      }
    }

    const optLetters = ["A", "B", "C", "D"]
    const totalSeconds = props.result.total_time_seconds
    const timeDisplay = `${Math.floor(totalSeconds/60)}:${String(totalSeconds%60).padStart(2,"0")}`
    const passed = props.result.score >= 60

    return { openItems, toggleItem, requestPractice, optLetters, timeDisplay, passed }
  },
  template: `
    <section class="view">
      <div class="result-inner">
        <!-- 得分卡 -->
        <div class="result-header">
          <h2 class="result-title">測驗完成！</h2>
          <div class="score-circle-wrap">
            <div class="score-circle" :class="{ fail: !passed }">
              <span class="score-value">{{ result.score }}</span>
              <span class="score-denom">/ 100</span>
            </div>
          </div>
          <div class="result-stats">
            <div class="result-stat">
              <div class="result-stat-num correct">{{ result.correct_count }}</div>
              <div class="result-stat-label">答對</div>
            </div>
            <div class="result-stat">
              <div class="result-stat-num wrong">{{ result.wrong_count }}</div>
              <div class="result-stat-label">答錯</div>
            </div>
            <div class="result-stat">
              <div class="result-stat-num">{{ result.unanswered_count }}</div>
              <div class="result-stat-label">未作答</div>
            </div>
            <div class="result-stat">
              <div class="result-stat-num" style="color:#BA7517">{{ timeDisplay }}</div>
              <div class="result-stat-label">作答時間</div>
            </div>
          </div>
        </div>

        <!-- 逐題解析 -->
        <div class="result-section-title">逐題解析</div>
        <div class="result-items">
          <div
            v-for="qr in result.question_results"
            :key="qr.question_id"
            class="result-item"
            :class="{ open: openItems[qr.question_id] }"
          >
            <!-- 面板標頭（點擊展開/收合）-->
            <div class="result-item-header" @click="toggleItem(qr.question_id)">
              <div class="result-status-icon" :class="qr.is_correct ? 'correct' : 'wrong'">
                {{ qr.is_correct ? '✓' : '✗' }}
              </div>
              <div class="result-item-label">
                <div class="result-item-num">第 {{ qr.question_id }} 題</div>
                <div class="result-item-tag">{{ qr.tag }}</div>
              </div>
              <span v-if="!qr.is_correct && qr.user_answer !== null" class="result-wrong-ans">
                你的答案：{{ optLetters[qr.user_answer] }}
              </span>
              <span class="result-chevron">▼</span>
            </div>

            <!-- 面板內容（展開後顯示）-->
            <div class="result-body" v-show="openItems[qr.question_id]">
              <p class="result-q-text">{{ qr.question_text }}</p>

              <!-- 四個選項，標色 -->
              <div class="result-options-grid">
                <div
                  v-for="(opt, i) in qr.options"
                  :key="i"
                  class="result-option"
                  :class="{
                    'correct-ans': i === qr.correct_index,
                    'user-wrong':  i === qr.user_answer && !qr.is_correct
                  }"
                >
                  <span class="opt-letter">{{ optLetters[i] }}</span>
                  <span>{{ opt.replace(/^[A-D]\\. /, '') }}</span>
                </div>
              </div>

              <!-- AI 解析區塊 -->
              <div class="ai-block">
                <div class="ai-block-title">✦ AI 專屬解析</div>
                <div class="ai-block-content">
                  <p>{{ qr.ai_analysis }}</p>
                  <p v-if="qr.translation" style="margin-top:8px;opacity:0.8">
                    <strong>中文翻譯：</strong>{{ qr.translation }}
                  </p>
                </div>
                <div class="ai-block-vocab" v-if="qr.vocab && qr.vocab.length">
                  <span v-for="v in qr.vocab" :key="v" class="vocab-pill">{{ v }}</span>
                </div>
              </div>

              <!-- 錯題才顯示「生成練習題」按鈕 -->
              <button
                v-if="!qr.is_correct"
                class="btn-ai-practice"
                @click="requestPractice(qr.question_id)"
              >
                ★ 產生類似考點練習題
              </button>
            </div>
          </div>
        </div>

        <!-- 底部按鈕 -->
        <div class="result-footer">
          <button class="btn-outline" @click="$emit('go-profile')">查看學習數據</button>
          <button class="btn-primary"  @click="$emit('go-home')">回到首頁</button>
        </div>
      </div>
    </section>
  `
}

// ════════════════════════════════════════════════════════════
// 第三部分：App 根元件 — 負責路由切換與 API 呼叫
// ════════════════════════════════════════════════════════════

const App = {
  components: {
    "home-view":    HomeView,
    "profile-view": ProfileView,
    "quiz-view":    QuizView,
    "result-view":  ResultView
  },
  setup() {
    const currentView = ref("home")

    // 全域共享狀態
    const state = reactive({
      username:    "遊客",
      quizSession: null,   // 從 /api/quiz/start 取得
      examResult:  null,   // 從 /api/quiz/submit 取得
      userStats:   null,   // 從 /api/user/:id/stats 取得
      loading:     false,
      error:       "",
      showDropdown: false
    })

    function showView(view) {
      currentView.value = view
      state.showDropdown = false
      // 切換到 Profile 頁面時才抓資料（懶加載）
      if (view === "profile" && !state.userStats) {
        fetchUserStats()
      }
    }

    // 🔥 新增：切換下拉選單狀態
    function toggleDropdown() {
      state.showDropdown = !state.showDropdown
    }

    // 點擊頁面其他地方時關閉選單
    function closeDropdown() {
      if (state.showDropdown) {
        state.showDropdown = false
      }
    }

    // 🔥 新增：Vue 裡面的登出處理
    async function performLogout() {
      state.showDropdown = false // 先把選單收起來
      try {
        // 呼叫 Supabase 登出 API
        await authSignOut()
        
        // 顯示登入畫面
        showAuthScreen()
        
        // 重置 Navbar
        document.querySelector(".navbar-username").textContent = "遊客"
        document.querySelector(".navbar-avatar").textContent = "遊"
        
        // 通知 Vue 切回首頁
        currentView.value = "home"
        state.username = "遊客"
        state.quizSession = null
        state.examResult = null
        state.userStats = null
      } catch(e) {
        alert("登出失敗：" + e.message)
      }
    }

    async function fetchUserStats() {
      try {
        state.userStats = await api.getUserStats("user_001")
      } catch(e) {
        console.error("無法取得使用者資料：", e)
      }
    }

    // 點擊「開始測驗」時呼叫
    async function startQuiz() {
      state.loading = true
      state.error   = ""
      try {
        state.quizSession = await api.startQuiz(5)
        showView("quiz")
      } catch(e) {
        state.error = e.message
      } finally {
        state.loading = false
      }
    }

    // QuizView 交卷後呼叫
    async function handleSubmit(payload) {
      try {
        state.examResult = await api.submitQuiz(
          payload.session_id,
          payload.answers,
          payload.time_spent_per_q
        )
        showView("result")
      } catch(e) {
        alert("交卷失敗：" + e.message)
      }
    }

    return { currentView, 
              state, 
              showView, 
              startQuiz, 
              handleSubmit,
              toggleDropdown,
              performLogout,
              closeDropdown
            }
  },
  // App 根層的 template 就只有 Navbar + 動態視圖切換
  template: `
    <nav class="navbar" @click="closeDropdown">
      <a class="navbar-logo" @click.stop="showView('home')">
        <div class="logo-icon">益</div>
        <span class="logo-text">多多益善</span>
      </a>
      
      <div class="navbar-right" style="position: relative;" @click.stop>
        <span class="navbar-username">{{ state.username }}</span>
        
        <button class="navbar-avatar" type="button" @click.stop="toggleDropdown">
          {{ state.username.charAt(0).toUpperCase() }}
        </button>

        <div v-show="state.showDropdown" class="profile-dropdown" @click.stop>
            <div class="dropdown-item" @click="showView('profile')">
                <span style="margin-right: 8px;">📊</span> 查看個人分析
            </div>
            <hr style="margin: 4px 0; border: 0; border-top: 1px solid #eee;">
            <div class="dropdown-item logout-item" @click="performLogout()">
                <span style="margin-right: 8px;">🚪</span> 登出系統
            </div>
        </div>
      </div>
    </nav>

    <home-view
      v-if="currentView === 'home'"
      :loading="state.loading"
      :error="state.error"
      @start-quiz="startQuiz"
      @go-profile="showView('profile')"
    />
    <profile-view
      v-if="currentView === 'profile'"
      :user-stats="state.userStats"
      @go-home="showView('home')"
    />
    <quiz-view
      v-if="currentView === 'quiz' && state.quizSession"
      :session="state.quizSession"
      @submit="handleSubmit"
    />
    <result-view
      v-if="currentView === 'result' && state.examResult"
      :result="state.examResult"
      @go-home="showView('home')"
      @go-profile="showView('profile')"
    />
  `
}

createApp(App).mount("#app")

setTimeout(async () => {
  const session = await getSession()
  if (session) {
    document.querySelector(".navbar-username").textContent = session.user.email
    document.querySelector(".navbar-avatar").textContent =
      session.user.email.charAt(0).toUpperCase()
    hideAuthScreen()
  } else {
    showAuthScreen()
  }
}, 100)