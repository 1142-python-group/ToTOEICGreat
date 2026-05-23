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
  const email = document.getElementById("login-email").value.trim()
  const password = document.getElementById("login-password").value
  const errorEl = document.getElementById("login-error")
  const btn = document.getElementById("login-btn")

  if (!email || !password) {
    errorEl.textContent = "請填入 Email 和密碼"
    return
  }

  btn.textContent = "登入中..."
  btn.disabled = true

  try {
    const data = await authSignIn(email, password)
    const displayUser = data.user.user_metadata?.username || data.user.email
    document.querySelector(".navbar-username").textContent = displayUser
    document.querySelector(".navbar-avatar").textContent =
      displayUser.charAt(0).toUpperCase()
    hideAuthScreen()
  } catch (e) {
    errorEl.textContent = e.message === "Invalid login credentials"
      ? "Email 或密碼錯誤" : e.message
  } finally {
    btn.textContent = "登入"
    btn.disabled = false
  }
}

async function handleRegister() {
  const username = document.getElementById("register-username").value.trim()
  const email = document.getElementById("register-email").value.trim()
  const password = document.getElementById("register-password").value
  const errorEl = document.getElementById("register-error")
  const btn = document.getElementById("register-btn")

  if (!email || !password || !username) {
    errorEl.textContent = "請填入名稱、Email和密碼"
    return
  }
  if (password.length < 6) {
    errorEl.textContent = "密碼至少需要 6 個字元"
    return
  }

  btn.textContent = "註冊中..."
  btn.disabled = true

  try {
    await authSignUp(email, password, username)
    document.getElementById("register-username").value = ""
    document.getElementById("register-email").value = ""
    document.getElementById("register-password").value = ""
    const data = await authSignIn(email, password)
    const displayUser = data.user.user_metadata?.username || username || data.user.email
    document.querySelector(".navbar-username").textContent = displayUser
    document.querySelector(".navbar-avatar").textContent = displayUser.charAt(0).toUpperCase()
    hideAuthScreen()
  } catch (e) {
    errorEl.textContent = e.message
  } finally {
    btn.textContent = "註冊"
    btn.disabled = false
  }
}

async function handleLogout() {
  try {
    await authSignOut()
    showAuthScreen()
    document.querySelector(".navbar-username").textContent = "遊客"
    document.querySelector(".navbar-avatar").textContent = "遊"
    const appInstance = document.getElementById("app").__vue_app__
    if (appInstance && appInstance._instance.proxy.showView) {
      appInstance._instance.proxy.showView('home')
    }
  } catch (e) {
    alert("登出失敗：" + e.message)
  }
}


const API_BASE = "http://localhost:8000/api"

async function fetchWithAuth(endpoint, options = {}) {
  const session = await getSession();
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {})
  };

  if (session && session.access_token) {
    headers["Authorization"] = `Bearer ${session.access_token}`;
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers
  });

  if (!response.ok) {
    let errorData;
    try {
      errorData = await response.json();
    } catch (e) {
      errorData = { detail: response.statusText };
    }
    throw new Error(errorData.detail || "API 請求失敗");
  }

  if (response.status === 204) return null;
  return response.json();
}

const api = {
  async startQuiz(params = {}) {
    const {
      vocabCount = 5,
      listeningCount = 3,
      readingGroups = 1,
      includeListening = true,
      includeVocab = true,
      includeReading = true,
    } = params
    const qs = new URLSearchParams({
      vocab_count: vocabCount,
      listening_count: listeningCount,
      reading_groups: readingGroups,
      include_listening: includeListening,
      include_vocab: includeVocab,
      include_reading: includeReading,
    })
    const res = await fetch(`${API_BASE}/quiz/start?${qs}`)
    if (!res.ok) throw new Error("無法取得題目，請確認後端是否正在運作")
    return res.json()
  },

  async submitQuiz(sessionId, answers, timeSpentPerQ) {
    return fetchWithAuth("/quiz/submit", {
      method: "POST",
      body: JSON.stringify({
        session_id: sessionId,
        answers: answers,
        time_spent_per_q: timeSpentPerQ,
        attempt_type: "practice"
      })
    })
  },

  async getUserStats(userId) {
    const res = await fetch(`${API_BASE}/user/${userId}/stats`)
    if (!res.ok) throw new Error("無法取得使用者資料")
    return res.json()
  },

  async generatePractice(questionId) {
    const res = await fetch(`${API_BASE}/quiz/generate-practice`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question_id: questionId })
    })
    if (!res.ok) throw new Error("生成失敗")
    return res.json()
  },

  async generateHistoryPractice() {
    return fetchWithAuth("/quiz/generate-history-practice", {
      method: "POST"
    });
  },

  async getFriendCode() {
    return fetchWithAuth("/v1/friends/my-code");
  },
  async sendFriendRequest(friendCode) {
    return fetchWithAuth("/v1/friends/requests", {
      method: "POST",
      body: JSON.stringify({ friend_code: friendCode })
    });
  },
  async handleFriendRequest(friendshipId, action) {
    return fetchWithAuth(`/v1/friends/requests/${friendshipId}`, {
      method: "PATCH",
      body: JSON.stringify({ action })
    });
  },
  async getFriendsList(status = "accepted") {
    return fetchWithAuth(`/v1/friends?status=${status}`);
  },
  async removeFriend(friendUserId) {
    return fetchWithAuth(`/v1/friends/${friendUserId}`, {
      method: "DELETE"
    });
  },

  async getExamHistory(limit = 10) {
    return fetchWithAuth(`/v1/exams/history?limit=${limit}`);
  },
  async getErrorBook(status = "needs_review") {
    return fetchWithAuth(`/v1/exams/errors?status=${status}`);
  },
  async getExamAnswers(attemptId) {
    return fetchWithAuth(`/v1/exams/history/${attemptId}/answers`);
  },

  async getScoreLeaderboard(timeframe = "all_time") {
    return fetchWithAuth(`/v1/leaderboard/scores?timeframe=${timeframe}`);
  },
  async getDiligenceLeaderboard(timeframe = "this_week") {
    return fetchWithAuth(`/v1/leaderboard/diligence?timeframe=${timeframe}`);
  }
}

// ════════════════════════════════════════════════════════════
// 第二部分：Vue 元件定義
// ════════════════════════════════════════════════════════════

const { createApp, ref, reactive, computed, onMounted, onUnmounted, watch, nextTick } = Vue

// ── 首頁元件 ──────────────────────────────────────────────
const HomeView = {
  emits: ["start-quiz", "start-history-practice", "go-profile", "go-leaderboard"],
  props: {
    loading: { type: Boolean, default: false },
    error: { type: String, default: "" }
  },
  setup(props, { emit }) {
    const vocabCount = ref(5)
    const listeningCount = ref(3)
    const readingGroupCount = ref(1)
    const includeListening = ref(true)
    const includeVocab = ref(true)
    const includeReading = ref(true)

    function startQuiz() {
      emit("start-quiz", {
        vocabCount: vocabCount.value,
        listeningCount: listeningCount.value,
        readingGroups: readingGroupCount.value,
        includeListening: includeListening.value,
        includeVocab: includeVocab.value,
        includeReading: includeReading.value,
      })
    }

    return { vocabCount, listeningCount, readingGroupCount, includeListening, includeVocab, includeReading, startQuiz }
  },
  template: `
    <section class="view home-view">
      <div class="home-bg-watermark">益</div>
      <div class="home-card" style="position: relative; max-width: 620px;">
        <div v-if="loading" style="position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: rgba(255,255,255,0.85); display: flex; flex-direction: column; align-items: center; justify-content: center; z-index: 10; border-radius: 12px;">
          <div style="width: 40px; height: 40px; border: 4px solid #378ADD; border-top-color: transparent; border-radius: 50%; animation: spin 1s linear infinite; margin-bottom: 15px;"></div>
          <div style="color: #378ADD; font-weight: bold;">載入題目中...</div>
        </div>

        <div class="home-eyebrow">★ AI 驅動練習</div>
        <h1 class="home-title">準備好突破你的<br>多益極限了嗎？</h1>

        <!-- 題型設定 -->
        <div class="quiz-config-grid">
          <label class="quiz-config-item" :class="{ active: includeListening }">
            <input type="checkbox" v-model="includeListening" style="display:none">
            <div class="quiz-config-icon">🎧</div>
            <div class="quiz-config-label">聽力題</div>
            <input v-if="includeListening" type="number" v-model.number="listeningCount" min="1" max="10" class="quiz-config-num" @click.stop>
            <div v-else class="quiz-config-off">關閉</div>
          </label>

          <label class="quiz-config-item" :class="{ active: includeVocab }">
            <input type="checkbox" v-model="includeVocab" style="display:none">
            <div class="quiz-config-icon">📝</div>
            <div class="quiz-config-label">單字題</div>
            <input v-if="includeVocab" type="number" v-model.number="vocabCount" min="1" max="20" class="quiz-config-num" @click.stop>
            <div v-else class="quiz-config-off">關閉</div>
          </label>

          <label class="quiz-config-item" :class="{ active: includeReading }">
            <input type="checkbox" v-model="includeReading" style="display:none">
            <div class="quiz-config-icon">📖</div>
            <div class="quiz-config-label">閱讀題</div>
            <input v-if="includeReading" type="number" v-model.number="readingGroupCount" min="1" max="5" class="quiz-config-num" @click.stop>
            <div v-else class="quiz-config-off">關閉</div>
          </label>
        </div>

        <div class="home-btns" style="margin-top: 20px; display: flex; flex-direction: column; gap: 10px;">
          <button class="btn-primary" @click="startQuiz" :disabled="loading || (!includeListening && !includeVocab && !includeReading)">
            ▶ 開始模擬測驗
          </button>
          <div style="border-top: 1px solid #eee; margin: 10px 0; padding-top: 15px;">
            <div style="font-size: 0.9rem; color: #666; margin-bottom: 10px; display: flex; align-items: center; gap: 5px;">
            </div>
            <button class="btn-primary btn-lightblue" style="width: 100%;" @click="$emit('start-history-practice')" :disabled="loading">
              ▶ 生成客製化易錯測驗
            </button>
          </div>
        </div>
        <div v-if="error" style="background: #fff5f5; border: 1px solid #feb2b2; color: #c53030; padding: 12px; border-radius: 8px; margin-top: 15px; font-size: 14px; display: flex; align-items: flex-start; gap: 10px;">
          <span style="font-size: 18px;">⚠️</span>
          <div>
            <div style="font-weight: bold; margin-bottom: 3px;">載入失敗</div>
            {{ error }}
          </div>
        </div>
      </div>
    </section>
  `
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

        <div v-if="!userStats" style="text-align:center;padding:60px;color:#888">
          載入資料中...
        </div>

        <template v-else>
          <div class="profile-header-card">
            <div class="profile-big-avatar">
              {{ userStats.username.charAt(0) }}
            </div>
            <div>
              <div class="profile-name">{{ userStats.username }}</div>
              <div class="profile-meta">總作答題數：{{ userStats.total_questions }} 題</div>
            </div>
          </div>

          <div class="stats-grid">
            <!-- 註解掉分數計算：
            <div class="stat-card">
              <div class="stat-label">預估測驗分數</div>
              <div class="stat-value">{{ userStats.estimated_score }}</div>
            </div>
            -->
            <div class="stat-card">
              <div class="stat-label">預估正確率</div>
              <div class="stat-value">{{ userStats.estimated_score > 100 ? Math.round(userStats.estimated_score / 990 * 100) : userStats.estimated_score }}<small>%</small></div>
            </div>
            <div class="stat-card">
              <div class="stat-label">平均單次作答時間</div>
              <div class="stat-value">{{ userStats.avg_time_per_q.toFixed(0) }}<small> 秒</small></div>
            </div>
            <div class="stat-card">
              <div class="stat-label">好友排行</div>
              <div class="stat-value">{{ userStats.friend_rank }}</div>
            </div>
          </div>

          <div class="charts-grid">
            <div class="chart-card">
              <div class="chart-title">歷史正確率趨勢</div>
              <div class="chart-wrap">
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
  setup(props) {
    const lineCanvas = ref(null)
    const radarCanvas = ref(null)
    let lineChart = null
    let radarChart = null

    onMounted(async () => {
      await nextTick()
      if (props.userStats) initCharts()
    })

    watch(() => props.userStats, async (newVal) => {
      if (newVal) {
        await nextTick()
        initCharts()
      }
    })

    function initCharts() {
      if (lineChart) lineChart.destroy()
      if (radarChart) radarChart.destroy()

      const stats = props.userStats

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
          plugins: { 
            legend: { display: false }, 
            tooltip: {
              callbacks: {
                label: (ctx) => `${ctx.parsed.y}%`
              }
            },
          },
          
          scales: {
            y: { 
              min: 0, 
              max: 100,
              ticks: {
                callback: (value) => `${value}%`   // ← 順手把 Y 軸刻度也加 %
              },
            },
            x: { grid: { display: false } }
          }
        }
      })

      radarChart = new Chart(radarCanvas.value, {
        type: "radar",
        data: {
          labels: stats.radar_data.map(d => d.label),
          datasets: [
            // 1. 60% 及格線（畫在底層）
            {
              label: "及格線",
              data: stats.radar_data.map(() => 60),
              borderColor: "rgba(220, 53, 69, 0.6)",     // 紅色虛線
              backgroundColor: "rgba(220, 53, 69, 0.04)",
              borderWidth: 1.5,
              borderDash: [5, 5],                         // 虛線樣式
              pointRadius: 0,                             // 不顯示節點
              pointHoverRadius: 0,
              fill: false,
              order: 2
            },
            // 2. 使用者實際數據（畫在上層）
            {
              label: "你的能力",
              data: stats.radar_data.map(d => d.value),
              borderColor: "#BA7517",
              backgroundColor: "rgba(186,117,23,0.12)",
              borderWidth: 2,
              pointRadius: 4,
              pointBackgroundColor: "#BA7517",
              order: 1
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              display: true,                              // 顯示圖例
              position: "bottom",
              labels: {
                font: { size: 12 },
                boxWidth: 20,
                padding: 12
              }
            },
            tooltip: {
              callbacks: {
                label: (ctx) => `${ctx.parsed.r}%`
              }
            }
          },
          scales: {
            r: {
              min: 0,
              max: 100,
              ticks: {
                display: false,
                stepSize: 20
              },
              grid: { color: "rgba(0,0,0,0.08)" },
              angleLines: { color: "rgba(0,0,0,0.08)" }
            }
          }
        }
      })
    }

    onUnmounted(() => {
      if (lineChart) lineChart.destroy()
      if (radarChart) radarChart.destroy()
    })

    return { lineCanvas, radarCanvas }
  }
}

// ── 測驗作答元件 ───────────────────────────────────────────
// 【改動】：加入閱讀題文章顯示區塊
const QuizView = {
  emits: ["submit"],
  props: {
    session: { type: Object, required: true }
  },
  setup(props, { emit }) {
    const currentIndex = ref(0)
    const userAnswers = reactive({})
    const timeSpentPerQ = reactive({})
    const secondsLeft = ref(props.session.time_limit_seconds)
    // 文章翻譯展開狀態
    const showArticleTranslation = ref(false)
    let timerInterval = null
    const endTime = Date.now() + props.session.time_limit_seconds * 1000;

    onMounted(() => {
      timerInterval = setInterval(() => {
        const now = Date.now();
        const newSecondsLeft = Math.max(0, Math.ceil((endTime - now) / 1000));
        
        if (newSecondsLeft < secondsLeft.value) {
          const qid = currentQuestion.value.id
          timeSpentPerQ[qid] = (timeSpentPerQ[qid] || 0) + (secondsLeft.value - newSecondsLeft);
        }
        
        secondsLeft.value = newSecondsLeft;

        if (secondsLeft.value <= 0) {
          clearInterval(timerInterval)
          doSubmit()
        }
      }, 500)
    })

    onUnmounted(() => clearInterval(timerInterval))

    const questions = computed(() => props.session.questions)
    const currentQuestion = computed(() => questions.value[currentIndex.value])
    const isLastQ = computed(() => currentIndex.value === questions.value.length - 1)

    const timerDisplay = computed(() => {
      const m = Math.floor(secondsLeft.value / 60)
      const s = secondsLeft.value % 60
      return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`
    })

    // 切題時重置翻譯展開狀態
    watch(currentIndex, () => {
      showArticleTranslation.value = false
    })

    function selectOption(optionIndex) {
      userAnswers[currentQuestion.value.id] = optionIndex
      try {
        localStorage.setItem("exam_backup", JSON.stringify({
          session_id: props.session.session_id,
          answers: userAnswers,
          currentIndex: currentIndex.value
        }))
      } catch (e) { }
    }

    function recordTimeAndJump(newIndex) {
      // timeSpentPerQ is already incrementally tracked in the setInterval
      currentIndex.value = newIndex
    }

    function prevQ() { if (currentIndex.value > 0) recordTimeAndJump(currentIndex.value - 1) }
    function nextQ() { if (!isLastQ.value) recordTimeAndJump(currentIndex.value + 1) }
    function jumpToQ(i) { recordTimeAndJump(i) }

    function doSubmit() {
      clearInterval(timerInterval)
      localStorage.removeItem("exam_backup")
      emit("submit", {
        session_id: props.session.session_id,
        answers: { ...userAnswers },
        time_spent_per_q: { ...timeSpentPerQ }
      })
    }

    return {
      currentIndex, userAnswers, secondsLeft,
      currentQuestion, questions, isLastQ, timerDisplay,
      showArticleTranslation,
      selectOption, prevQ, nextQ, jumpToQ, doSubmit
    }
  },
  template: `
    <section class="view">
      <div class="quiz-inner" :class="{ 'quiz-reading-layout': currentQuestion.article_text }">

        <!-- ══ 閱讀題：左欄文章 ══ -->
        <div v-if="currentQuestion.article_text" class="quiz-article-panel">
          <div class="quiz-article-type-badge">{{ currentQuestion.article_type || 'Article' }}</div>
          <pre class="quiz-article-text">{{ currentQuestion.article_text }}</pre>
          <!-- 作答時不顯示中文譯文，結果頁才顯示 -->
        </div>

        <!-- ══ 左側（無文章）或右側（有文章）主作答區 ══ -->
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
            <!-- 聽力題：播放器取代題目文字 -->
            <div v-if="currentQuestion.audio_url" class="audio-player-block">
              <div class="audio-play-hint">🎧 請播放音檔後作答</div>
              <audio
                :key="currentQuestion.id"
                controls
                controlsList="nodownload"
                class="audio-player"
                :src="currentQuestion.audio_url"
              ></audio>
              <div class="audio-play-limit">⚠️ 建議只播放一次，模擬正式考試</div>
            </div>
            <!-- 非聽力題：正常顯示題目文字 -->
            <p class="quiz-question-text">{{ currentQuestion.text }}</p>
            <div class="option-list">
              <button
                v-for="(opt, i) in currentQuestion.options"
                :key="i"
                v-show="!(currentQuestion.part === 2 && i === 3)"
                class="option-btn"
                :class="{ selected: userAnswers[currentQuestion.id] === i }"
                @click="selectOption(i)"
              >
                <span class="option-letter">{{ ['A','B','C','D'][i] }}</span>
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

        <!-- ══ 右側題號導覽（無文章時才顯示） ══ -->
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
// 【改動】：ResultView 加入閱讀題文章顯示區塊
const ResultView = {
  emits: ["go-home", "go-profile"],
  props: {
    result: { type: Object, required: true }
  },
  setup(props) {
    const openItems = reactive({})
    const showArticleTranslation = reactive({})  // 各題的文章翻譯展開狀態

    function toggleItem(id) {
      openItems[id] = !openItems[id]
    }

    function toggleArticleTranslation(id) {
      showArticleTranslation[id] = !showArticleTranslation[id]
    }

    const practiceQuestion = ref(null)
    const practiceLoading = ref(false)

    async function requestPractice(questionId) {
      practiceLoading.value = true
      try {
        const data = await api.generatePractice(questionId)
        practiceQuestion.value = { ...data, selectedAnswer: null }
      } catch (e) {
        alert("生成失敗，請稍後再試")
      } finally {
        practiceLoading.value = false
      }
    }

    const optLetters = ["A", "B", "C", "D"]
    const totalSeconds = props.result.total_time_seconds
    const timeDisplay = `${Math.floor(totalSeconds / 60)}:${String(totalSeconds % 60).padStart(2, "0")}`
    const passed = props.result.score >= 60

    return { openItems, toggleItem, showArticleTranslation, toggleArticleTranslation,
             requestPractice, practiceQuestion, practiceLoading, optLetters, timeDisplay, passed }
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
              <span class="score-denom">% 正確率</span>
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
            <!-- 面板標頭 -->
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

            <!-- 面板內容 -->
            <div class="result-body" v-show="openItems[qr.question_id]">

              <!-- 聽力題音檔區塊 -->
              <div v-if="qr.audio_url" class="audio-player-block" style="margin-bottom: 15px;">
                <audio
                  controls
                  class="audio-player"
                  :src="qr.audio_url"
                  style="width: 100%; border-radius: 8px;"
                ></audio>
              </div>

              <!-- 【新增】閱讀題：在題目上方顯示原文 -->
              <div v-if="qr.article_text" class="result-article-block">
                <div class="result-article-header">
                  <span class="result-article-type-badge">{{ qr.article_type || 'Article' }}</span>
                  <span class="result-article-label">閱讀原文</span>
                </div>
                <pre class="result-article-text">{{ qr.article_text }}</pre>
                <!-- 文章中文翻譯（可展開） -->
                <div v-if="qr.article_translation" class="quiz-article-translation-toggle">
                  <button class="btn-translation-toggle" @click="toggleArticleTranslation(qr.question_id)">
                    {{ showArticleTranslation[qr.question_id] ? '▲ 隱藏中文譯文' : '▼ 顯示中文譯文' }}
                  </button>
                  <div v-show="showArticleTranslation[qr.question_id]" class="quiz-article-translation-text">
                    {{ qr.article_translation }}
                  </div>
                </div>
              </div>

              <p class="result-q-text">{{ qr.question_text }}</p>

              <!-- 四個選項，標色 -->
              <div class="result-options-grid">
                <div
                  v-for="(opt, i) in qr.options"
                  :key="i"
                  v-show="!(qr.part === 2 && i === 3)"
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

              <button
                v-if="!qr.is_correct"
                class="btn-ai-practice"
                @click="requestPractice(qr.question_id)"
                :disabled="practiceLoading"
              >
                {{ practiceLoading ? '生成中...' : '★ 產生類似考點練習題' }}
              </button>
            </div>
          </div>
        </div>

        <!-- 練習題彈窗 -->
        <div v-if="practiceQuestion" class="practice-modal-backdrop" @click.self="practiceQuestion = null">
          <div class="practice-modal">
            <button class="practice-modal-close" @click="practiceQuestion = null">✕</button>
            <div class="practice-modal-label">★ AI 生成練習題</div>
            <p class="practice-modal-tag">{{ practiceQuestion.tag }}</p>

            <!-- 閱讀題：顯示文章 -->
            <div v-if="practiceQuestion.article_text" class="practice-article-block">
              <div class="quiz-article-type-badge">{{ practiceQuestion.article_type || 'Article' }}</div>
              <pre class="quiz-article-text">{{ practiceQuestion.article_text }}</pre>
            </div>

            <!-- 聽力題：播放器 -->
            <div v-if="practiceQuestion.audio_url" class="audio-player-block" style="margin-bottom: 16px;">
              <div class="audio-play-hint">🎧 請播放音檔後作答</div>
              <audio :key="practiceQuestion.id" controls controlsList="nodownload"
                class="audio-player" :src="practiceQuestion.audio_url"></audio>
            </div>
            <!-- 題目文字（Part 2 沒有文字所以不顯示，其他都顯示） -->
            <p v-if="practiceQuestion.text && practiceQuestion.text.trim()" class="practice-modal-text">{{ practiceQuestion.text }}</p>

            <div class="option-list">
              <button
                v-for="(opt, i) in practiceQuestion.options"
                :key="i"
                v-show="!(practiceQuestion.part === 2 && i === 3)"
                class="option-btn"
                :class="{
                  selected: practiceQuestion.selectedAnswer === i,
                  'correct-highlight': practiceQuestion.selectedAnswer !== null && i === practiceQuestion.correct_index,
                  'wrong-highlight': practiceQuestion.selectedAnswer !== null && i === practiceQuestion.selectedAnswer && practiceQuestion.selectedAnswer !== practiceQuestion.correct_index
                }"
                @click="practiceQuestion.selectedAnswer === null && (practiceQuestion.selectedAnswer = i)"
              >
                <span class="option-letter">{{ ['A','B','C','D'][i] }}</span>
                <span>{{ opt }}</span>
              </button>
            </div>

            <!-- 選完後顯示解析 -->
            <div v-if="practiceQuestion.selectedAnswer !== null" class="practice-result-block">
              <div :class="practiceQuestion.selectedAnswer === practiceQuestion.correct_index ? 'practice-result-correct' : 'practice-result-wrong'">
                {{ practiceQuestion.selectedAnswer === practiceQuestion.correct_index ? '✓ 答對了！' : '✗ 答錯了，正確答案是 ' + ['A','B','C','D'][practiceQuestion.correct_index] }}
              </div>
              <div v-if="practiceQuestion.explanation" style="margin-top: 12px; font-size: 14px; line-height: 1.7; color: #2d3748;">
                {{ practiceQuestion.explanation }}
              </div>
              <div v-if="practiceQuestion.translation" style="margin-top: 8px; font-size: 13px; color: #666;">
                <strong>中文翻譯：</strong>{{ practiceQuestion.translation }}
              </div>
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

// ── 好友系統元件 ───────────────────────────────────────────
const FriendsView = {
  template: `
    <section class="view">
      <div class="profile-inner">
        <button class="profile-back-btn" @click="$emit('go-home')">← 返回首頁</button>
        <h2 class="view-title" style="margin-bottom: 20px;">好友系統</h2>
        
        <div class="stats-grid" style="grid-template-columns: 1fr;">
          <div class="stat-card" style="display: flex; flex-direction: column; gap: 15px; align-items: flex-start;">
            <div style="width: 100%; display: flex; justify-content: space-between; align-items: center;">
              <div class="stat-label">我的好友代碼</div>
              <div class="stat-value" style="font-size: 1.2rem; background: #f0f4f8; padding: 5px 10px; border-radius: 8px;">
                {{ myCode || '載入中...' }}
              </div>
            </div>
            <div style="width: 100%; display: flex; gap: 10px;">
              <input type="text" v-model="addFriendCode" placeholder="輸入好友代碼..." style="flex: 1; padding: 10px; border: 1px solid #ddd; border-radius: 8px;">
              <button class="btn-primary" @click="addFriend" :disabled="!addFriendCode">發送邀請</button>
            </div>
            <p v-if="addMessage" :style="{ color: addStatus === 'success' ? 'green' : 'red' }">{{ addMessage }}</p>
          </div>

          <div class="stat-card" v-if="pendingRequests.length > 0">
            <div class="stat-label" style="margin-bottom: 10px;">待處理邀請</div>
            <div v-for="req in pendingRequests" :key="req.friendship_id" style="display: flex; justify-content: space-between; align-items: center; padding: 10px; border-bottom: 1px solid #eee;">
              <div>
                <span class="profile-avatar" style="font-size: 14px; width: 24px; height: 24px; margin-right: 10px; display: inline-flex; align-items: center; justify-content: center; border-radius: 50%; background: #e0f2fe; color: #378ADD;">{{ (req.friend_username || '?').charAt(0).toUpperCase() }}</span>
                {{ req.friend_username || '匿名使用者' }}
              </div>
              <div style="display: flex; gap: 10px;">
                <template v-if="!req.is_requester">
                  <button class="btn-primary" style="padding: 5px 15px; font-size: 0.9rem;" @click="handleRequest(req.friendship_id, 'accept')">接受</button>
                  <button class="btn-secondary" style="padding: 5px 15px; font-size: 0.9rem;" @click="handleRequest(req.friendship_id, 'reject')">拒絕</button>
                </template>
                <template v-else>
                  <button class="btn-secondary" style="padding: 5px 15px; font-size: 0.9rem; color: #dc3545; border-color: #dc3545;" @click="removeFriend(req.friend_user_id)">收回邀請</button>
                </template>
              </div>
            </div>
          </div>

          <div class="stat-card">
            <div class="stat-label" style="margin-bottom: 10px;">我的好友 ({{ friends.length }})</div>
            <div v-if="friends.length === 0" style="color: #888; padding: 10px;">目前還沒有好友，趕快去新增吧！</div>
            <div v-for="friend in friends" :key="friend.friend_user_id" style="display: flex; justify-content: space-between; align-items: center; padding: 10px; border-bottom: 1px solid #eee;">
              <div style="display: flex; align-items: center;">
                <div class="profile-big-avatar" style="width: 40px; height: 40px; font-size: 1.2rem; margin-right: 15px; border-radius: 50%; background: #e0f2fe; color: #378ADD; display: flex; align-items: center; justify-content: center;">{{ (friend.friend_username || '?').charAt(0).toUpperCase() }}</div>
                <div style="font-weight: 500;">{{ friend.friend_username || '匿名使用者' }}</div>
              </div>
              <button class="btn-secondary" style="padding: 5px 15px; font-size: 0.9rem; color: #dc3545; border-color: #dc3545;" @click="removeFriend(friend.friend_user_id)">解除好友</button>
            </div>
          </div>
        </div>
      </div>
    </section>
  `,
  setup() {
    const myCode = Vue.ref('');
    const addFriendCode = Vue.ref('');
    const addMessage = Vue.ref('');
    const addStatus = Vue.ref('');
    const friends = Vue.ref([]);
    const pendingRequests = Vue.ref([]);

    const fetchData = async () => {
      try {
        const codeRes = await api.getFriendCode();
        myCode.value = codeRes.friend_code;
        const friendsRes = await api.getFriendsList("accepted");
        friends.value = friendsRes.data;
        const pendingRes = await api.getFriendsList("pending");
        pendingRequests.value = pendingRes.data;
      } catch (e) {
        console.error(e);
      }
    };

    Vue.onMounted(fetchData);

    const addFriend = async () => {
      try {
        addMessage.value = '發送中...';
        await api.sendFriendRequest(addFriendCode.value);
        addStatus.value = 'success';
        addMessage.value = '好友邀請發送成功！';
        addFriendCode.value = '';
        fetchData();
      } catch (e) {
        addStatus.value = 'error';
        addMessage.value = e.message;
      }
    };

    const handleRequest = async (id, action) => {
      try {
        await api.handleFriendRequest(id, action);
        fetchData();
      } catch (e) {
        alert(e.message);
      }
    };

    const removeFriend = async (userId) => {
      if (confirm('確定要解除好友嗎？')) {
        try {
          await api.removeFriend(userId);
          fetchData();
        } catch (e) {
          alert(e.message);
        }
      }
    };

    return { myCode, addFriendCode, addFriend, addMessage, addStatus, friends, pendingRequests, handleRequest, removeFriend };
  }
};

// ── 作答紀錄列表元件 ───────────────────────────────────────
const RecordsView = {
  template: `
    <section class="view">
      <div class="profile-inner">
        <button class="profile-back-btn" @click="$emit('go-home')">← 返回首頁</button>
        <h2 class="view-title" style="margin-bottom: 20px;">個人作答紀錄</h2>
        
        <div v-if="loading" style="text-align:center;padding:40px;color:#888;">載入中...</div>
        <div v-else-if="records.length === 0" style="text-align:center;padding:40px;color:#888;">
          目前還沒有作答紀錄喔！
        </div>
        <div v-else class="stats-grid" style="grid-template-columns: 1fr;">
          <div v-for="record in records" :key="record.id" 
               class="stat-card" 
               style="display: flex; justify-content: space-between; align-items: center; cursor: pointer; transition: transform 0.2s;"
               @click="$emit('view-detail', record)"
               onmouseover="this.style.transform='translateY(-2px)'"
               onmouseout="this.style.transform='translateY(0)'">
            <div>
              <div style="font-weight: 600; font-size: 1.1rem; margin-bottom: 5px; color: #185FA5;">
                測驗類型：{{ formatAttemptType(record.attempt_type) }}
              </div>
              <div style="color: #666; font-size: 0.9rem;">
                測驗時間：{{ new Date(record.created_at).toLocaleString() }}
              </div>
            </div>
            <div style="text-align: right;">
              <!-- 註解掉多益分數的推估
              <div v-if="record.attempt_type === 'full_mock' || record.attempt_type === 'mock'" style="font-size: 1.5rem; font-weight: 700; color: #378ADD;">
                {{ Math.round(record.accuracy_rate * 990) }} 分
              </div>
              -->
              <div style="font-size: 1.2rem; font-weight: 600;" :style="{ color: record.accuracy_rate >= 0.6 ? '#378ADD' : '#BA7517' }">
                {{ record.correct_answers }} / {{ record.total_questions }}
              </div>
              <div style="color: #888; font-size: 0.85rem;">正確率: {{ Math.round(record.accuracy_rate * 100) }}%</div>
            </div>
          </div>
        </div>
      </div>
    </section>
  `,
  setup() {
    const records = Vue.ref([]);
    const loading = Vue.ref(true);

    const formatAttemptType = (type) => {
      if (type === 'full_mock' || type === 'mock') return '完整模考';
      if (type === 'custom_practice' || type === 'practice') return '部分練習';
      return type;
    };

    Vue.onMounted(async () => {
      try {
        const data = await api.getExamHistory(20);
        records.value = data;
      } catch (e) {
        console.error(e);
      } finally {
        loading.value = false;
      }
    });

    return { records, loading, formatAttemptType };
  }
};

// ── 單次測驗錯題本元件 ─────────────────────────────────────
const RecordDetailView = {
  props: { record: Object },
  template: `
    <section class="view">
      <div class="profile-inner">
        <button class="profile-back-btn" @click="$emit('go-records')">← 返回紀錄列表</button>
        
        <div class="result-header" style="margin-bottom: 30px;">
          <h2 class="result-title">作答詳情</h2>
          <p style="color: #666; margin-top: 10px;">測驗時間：{{ new Date(record.created_at).toLocaleString() }}</p>
          <div style="margin-top: 15px;">
            <label style="cursor: pointer; display: flex; align-items: center; gap: 8px;">
              <input type="checkbox" v-model="showErrorsOnly"> 只顯示錯題
            </label>
          </div>
        </div>
        
        <div v-if="loading" style="text-align:center;padding:40px;color:#888;">載入中...</div>
        <div v-else-if="filteredAnswers.length === 0" style="text-align:center;padding:40px;color:#378ADD; font-weight: 500; font-size: 1.1rem;">
          太棒了！沒有錯題可以顯示 🎉
        </div>
        
        <div v-else class="result-items">
          <div v-for="(ans, idx) in filteredAnswers" :key="ans.id" class="result-item open">
             <div class="result-item-header" style="cursor: default;">
              <div class="result-status-icon" :class="ans.is_correct ? 'correct' : 'wrong'">{{ ans.is_correct ? '✓' : '✗' }}</div>
              <div class="result-item-label">
                <div class="result-item-num">題目</div>
                <div class="result-item-tag">{{ ans.questions.skill_tag || '綜合' }}</div>
              </div>
              <span v-if="!ans.is_correct" class="result-wrong-ans">你的答案：{{ ans.user_answer || '未作答' }}</span>
              <span v-else style="color: green; font-weight: 500; margin-left: auto;">回答正確</span>
            </div>
            
            <div class="result-body" style="display: block;">
              <!-- 聽力題音檔區塊 -->
              <div v-if="ans.questions.audio_path" class="audio-player-block" style="margin-bottom: 15px;">
                <audio
                  controls
                  class="audio-player"
                  :src="getAudioUrl(ans.questions.audio_path)"
                  style="width: 100%; border-radius: 8px;"
                ></audio>
              </div>

              <!-- 【新增】閱讀題：顯示文章 -->
              <div v-if="ans.questions.article" class="result-article-block">
                <div class="result-article-header">
                  <span class="result-article-type-badge">{{ ans.questions.article.article_type || 'Article' }}</span>
                  <span class="result-article-label">閱讀原文</span>
                </div>
                <pre class="result-article-text">{{ ans.questions.article.article_text }}</pre>
                <!-- 文章中文翻譯（可展開） -->
                <div v-if="ans.questions.article.article_translation" class="quiz-article-translation-toggle">
                  <button class="btn-translation-toggle" @click="ans.showTranslation = !ans.showTranslation">
                    {{ ans.showTranslation ? '▲ 隱藏中文譯文' : '▼ 顯示中文譯文' }}
                  </button>
                  <div v-show="ans.showTranslation" class="quiz-article-translation-text">
                    {{ ans.questions.article.article_translation }}
                  </div>
                </div>
              </div>

              <p class="result-q-text">{{ ans.questions.question_text }}</p>
              
              <div class="result-options-grid" style="margin-top: 15px;">
                <div class="result-option" :class="{ 'correct-ans': ans.questions.correct_answer === 'A', 'user-wrong': ans.user_answer === 'A' && !ans.is_correct }">
                  <span class="opt-letter">A</span><span>{{ ans.questions.option_a }}</span>
                </div>
                <div class="result-option" :class="{ 'correct-ans': ans.questions.correct_answer === 'B', 'user-wrong': ans.user_answer === 'B' && !ans.is_correct }">
                  <span class="opt-letter">B</span><span>{{ ans.questions.option_b }}</span>
                </div>
                <div class="result-option" v-if="ans.questions.option_c" :class="{ 'correct-ans': ans.questions.correct_answer === 'C', 'user-wrong': ans.user_answer === 'C' && !ans.is_correct }">
                  <span class="opt-letter">C</span><span>{{ ans.questions.option_c }}</span>
                </div>
                <div class="result-option" v-if="ans.questions.option_d" :class="{ 'correct-ans': ans.questions.correct_answer === 'D', 'user-wrong': ans.user_answer === 'D' && !ans.is_correct }">
                  <span class="opt-letter">D</span><span>{{ ans.questions.option_d }}</span>
                </div>
              </div>
              
              <div class="ai-block" style="margin-top: 20px;">
                <div class="ai-block-title">正確答案：{{ ans.questions.correct_answer }}</div>
                <div class="ai-block-content" style="margin-top: 10px;">
                  <p>{{ ans.questions.explanation || '暫無解析' }}</p>
                  <p v-if="ans.questions.translation" style="margin-top:8px;opacity:0.8">
                    <strong>中文翻譯：</strong>{{ ans.questions.translation }}
                  </p>
                </div>
                <div class="ai-block-vocab" v-if="ans.questions.vocabulary && ans.questions.vocabulary.trim()" style="margin-top: 10px;">
                  <span v-for="v in ans.questions.vocabulary.split(',')" :key="v" v-show="v.trim()" class="vocab-pill" style="display:inline-block; background: #e0f2fe; color: #378ADD; padding: 4px 10px; border-radius: 99px; font-size: 0.85rem; margin-right: 6px; margin-bottom: 6px;">{{ v.trim() }}</span>
                </div>
              </div>
              
              <div v-if="!ans.is_correct" style="margin-top: 15px; text-align: right; display: flex; justify-content: flex-end; align-items: center; gap: 10px;">
                <label style="font-size: 0.9rem; color: #666;">複習狀態：</label>
                <select v-model="ans.review_status" @change="updateStatus(ans.id, ans.review_status)" style="padding: 5px; border-radius: 5px; border: 1px solid #ddd;">
                  <option value="needs_review">需要複習</option>
                  <option value="reviewed">已複習</option>
                  <option value="mastered">已精通</option>
                </select>
                <button v-if="ans.review_status !== 'mastered'" class="btn-outline" style="padding: 4px 10px; font-size: 0.85rem;" @click="updateStatus(ans.id, 'mastered'); ans.review_status = 'mastered'">標記為已學會</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  `,
  setup(props) {
    const allAnswers = Vue.ref([]);
    const loading = Vue.ref(true);
    const showErrorsOnly = Vue.ref(true);

    Vue.onMounted(async () => {
      try {
        const data = await api.getExamAnswers(props.record.id);
        allAnswers.value = data;
      } catch (e) {
        console.error(e);
      } finally {
        loading.value = false;
      }
    });

    const filteredAnswers = Vue.computed(() => {
      if (showErrorsOnly.value) {
        return allAnswers.value.filter(a => !a.is_correct);
      }
      return allAnswers.value;
    });

    const updateStatus = async (id, status) => {
      try {
        await fetchWithAuth(`/v1/exams/errors/${id}`, {
          method: 'PATCH',
          body: JSON.stringify({ review_status: status })
        });
      } catch (e) {
        alert("更新狀態失敗");
      }
    };

    const getAudioUrl = (path) => {
      if (!path) return null;
      return `https://xhlwsnflkrkfpweoljgj.supabase.co/storage/v1/object/public/audio/${path}`;
    };

    return { loading, showErrorsOnly, filteredAnswers, updateStatus, getAudioUrl };
  }
};

// ── 排行榜元件 ───────────────────────────────────────────
const LeaderboardView = {
  template: `
    <section class="view">
      <div class="profile-inner">
        <button class="profile-back-btn" @click="$emit('go-home')">← 返回首頁</button>
        <h2 class="view-title" style="margin-bottom: 20px;">排行榜</h2>
        
        <div style="display: flex; gap: 10px; margin-bottom: 20px; border-bottom: 1px solid #ddd; padding-bottom: 10px;">
          <button @click="tab = 'score'" :class="tab === 'score' ? 'btn-primary' : 'btn-outline'" style="padding: 8px 16px;">正確率排行</button>
          <button @click="tab = 'diligence'" :class="tab === 'diligence' ? 'btn-primary' : 'btn-outline'" style="padding: 8px 16px;">勤勉度排行</button>
          
          <select v-model="timeframe" @change="fetchData" style="margin-left: auto; padding: 8px; border-radius: 8px; border: 1px solid #ddd;">
            <option value="this_week">本週</option>
            <option value="this_month">本月</option>
            <option value="all_time">歷史總和</option>
          </select>
        </div>
        
        <div v-if="loading" style="text-align:center;padding:40px;color:#888;">載入中...</div>
        
        <div v-else class="stats-grid" style="grid-template-columns: 1fr;">
          <div class="stat-card" style="padding: 0; overflow: hidden;">
            <div style="display: grid; grid-template-columns: 60px 1fr 100px; padding: 15px 20px; background: #f8fafc; font-weight: bold; border-bottom: 1px solid #eee;">
              <div>名次</div>
              <div>使用者</div>
              <div style="text-align: right;">{{ tab === 'score' ? '正確率' : '刷題數' }}</div>
            </div>
            
            <div v-if="list.length === 0" style="padding: 30px; text-align: center; color: #888;">
              目前沒有排行資料
            </div>
            
            <div v-for="(item, idx) in list" :key="item.user_id" 
                 style="display: grid; grid-template-columns: 60px 1fr 100px; padding: 15px 20px; border-bottom: 1px solid #eee; align-items: center;"
                 :style="item.is_me ? 'background-color: rgba(55,138,221,0.05); font-weight: 500;' : ''">
              <div style="font-size: 1.2rem; font-weight: bold;" :style="getRankStyle(item.rank)">
                {{ item.rank <= 3 ? ['🥇','🥈','🥉'][item.rank-1] : item.rank }}
              </div>
              <div style="display: flex; align-items: center; gap: 10px;">
                <div class="profile-avatar" style="width: 32px; height: 32px; font-size: 14px; border-radius: 50%; background: #e0f2fe; color: #378ADD; display: flex; align-items: center; justify-content: center;">{{ (item.username || '?').charAt(0).toUpperCase() }}</div>
                <span>{{ item.username || '匿名使用者' }}</span>
                <span v-if="item.is_me" style="font-size: 0.75rem; background: #378ADD; color: white; padding: 2px 6px; border-radius: 10px; margin-left: 5px;">你</span>
              </div>
              <div style="text-align: right; font-size: 1.1rem; font-weight: bold; color: #333;">
                {{ tab === 'score' ? (item.score > 1 ? Math.round(item.score / 990 * 100) : item.score*100) + '%' : item.total_questions_solved }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  `,
  setup() {
    const tab = Vue.ref('score');
    const timeframe = Vue.ref('this_week');
    const list = Vue.ref([]);
    const loading = Vue.ref(true);

    const fetchData = async () => {
      loading.value = true;
      try {
        if (tab.value === 'score') {
          const tf = timeframe.value === 'this_week' ? 'this_month' : timeframe.value;
          const data = await api.getScoreLeaderboard(tf);
          list.value = data;
        } else {
          const data = await api.getDiligenceLeaderboard(timeframe.value);
          list.value = data;
        }
      } catch (e) {
        console.error(e);
      } finally {
        loading.value = false;
      }
    };

    Vue.watch(tab, fetchData);
    Vue.onMounted(fetchData);

    const getRankStyle = (rank) => {
      if (rank === 1) return 'color: #FFD700; text-shadow: 1px 1px 2px rgba(0,0,0,0.1);';
      if (rank === 2) return 'color: #C0C0C0; text-shadow: 1px 1px 2px rgba(0,0,0,0.1);';
      if (rank === 3) return 'color: #CD7F32; text-shadow: 1px 1px 2px rgba(0,0,0,0.1);';
      return 'color: #888;';
    };

    return { tab, timeframe, list, loading, fetchData, getRankStyle };
  }
};

// ════════════════════════════════════════════════════════════
// 第三部分：App 根元件 — 負責路由切換與 API 呼叫
// ════════════════════════════════════════════════════════════

const App = {
  components: {
    "home-view": HomeView,
    "profile-view": ProfileView,
    "quiz-view": QuizView,
    "result-view": ResultView,
    "friends-view": FriendsView,
    "records-view": RecordsView,
    "record-detail-view": RecordDetailView,
    "leaderboard-view": LeaderboardView
  },
  setup() {
    const currentView = ref("home")

    const state = reactive({
      username: "遊客",
      quizSession: null,
      examResult: null,
      userStats: null,
      selectedRecord: null,
      loading: false,
      error: "",
      showDropdown: false
    })

    function showView(view, payload = null) {
      currentView.value = view
      state.showDropdown = false
      if (view === "profile") {
        fetchUserStats()
      }
      if (view === "record-detail" && payload) {
        state.selectedRecord = payload;
      }
    }

    function toggleDropdown() {
      state.showDropdown = !state.showDropdown
    }

    function closeDropdown() {
      if (state.showDropdown) {
        state.showDropdown = false
      }
    }

    async function performLogout() {
      state.showDropdown = false
      try {
        await authSignOut()
        toggleAuthForm('login');
        document.getElementById("login-email").value = "";
        document.getElementById("login-password").value = "";
        document.getElementById("register-username").value = "";
        document.getElementById("register-email").value = "";
        document.getElementById("register-password").value = "";
        showAuthScreen()
        document.querySelector(".navbar-username").textContent = "遊客"
        document.querySelector(".navbar-avatar").textContent = "遊"
        currentView.value = "home"
        state.username = "遊客"
        state.quizSession = null
        state.examResult = null
        state.userStats = null
        state.selectedRecord = null
      } catch (e) {
        alert("登出失敗：" + e.message)
      }
    }

    async function fetchUserStats() {
      try {
        const session = await getSession()
        if (!session) return
        
        const userId = session.user.id  // 用真實登入者的 id
        state.userStats = await api.getUserStats(userId)
        const scoreLeaderboard = await api.getScoreLeaderboard("all_time")
        const meInLeaderboard = scoreLeaderboard.find(item => item.is_me === true)
        state.userStats.friend_rank = meInLeaderboard
          ? `Top ${meInLeaderboard.rank} `
          : "夯爆了"
      } catch (e) {
        console.error("無法取得使用者資料：", e)
      }
    }

    async function startQuiz(quizConfig = {}) {
      state.loading = true
      state.error = ""
      try {
        state.quizSession = await api.startQuiz(quizConfig)
        showView("quiz")
      } catch (e) {
        state.error = e.message
      } finally {
        state.loading = false
      }
    }

    async function startHistoryPractice() {
      state.loading = true
      state.error = ""

      const timeoutPromise = new Promise((_, reject) =>
        setTimeout(() => reject(new Error("生成時間過久，請稍後再試")), 90000)
      );

      try {
        state.quizSession = await Promise.race([
          api.generateHistoryPractice(),
          timeoutPromise
        ]);
        showView("quiz")
      } catch (e) {
        state.error = e.message
      } finally {
        state.loading = false
      }
    }

    async function handleSubmit(payload) {
      try {
        state.examResult = await api.submitQuiz(
          payload.session_id,
          payload.answers,
          payload.time_spent_per_q
        )
        showView("result")
      } catch (e) {
        alert("交卷失敗：" + e.message)
      }
    }

    return {
      currentView,
      state,
      showView,
      startQuiz,
      startHistoryPractice,
      handleSubmit,
      toggleDropdown,
      performLogout,
      closeDropdown
    }
  },
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
            <div class="dropdown-item" @click="showView('friends')">
                <span style="margin-right: 8px;">👥</span> 好友
            </div>
            <div class="dropdown-item" @click="showView('records')">
                <span style="margin-right: 8px;">📝</span> 個人作答紀錄
            </div>
            <div class="dropdown-item" @click="showView('leaderboard')">
                <span style="margin-right: 8px;">🏆</span> 排行榜
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
      @start-history-practice="startHistoryPractice"
      @go-profile="showView('profile')"
      @go-leaderboard="showView('leaderboard')"
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
    <friends-view
      v-if="currentView === 'friends'"
      @go-home="showView('home')"
    />
    <records-view
      v-if="currentView === 'records'"
      @go-home="showView('home')"
      @view-detail="showView('record-detail', $event)"
    />
    <record-detail-view
      v-if="currentView === 'record-detail' && state.selectedRecord"
      :record="state.selectedRecord"
      @go-records="showView('records')"
    />
    <leaderboard-view
      v-if="currentView === 'leaderboard'"
      @go-home="showView('home')"
    />
  `
}

createApp(App).mount("#app")

setTimeout(async () => {
  const session = await getSession()
  if (session) {
    const displayUser = session.user.user_metadata?.username || session.user.email
    document.querySelector(".navbar-username").textContent = displayUser
    document.querySelector(".navbar-avatar").textContent =
      displayUser.charAt(0).toUpperCase()
    hideAuthScreen()
  } else {
    showAuthScreen()
  }
}, 100)