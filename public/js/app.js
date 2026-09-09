const navToggle = document.querySelector(".nav-toggle");
const mainNav = document.querySelector(".main-nav");

if (navToggle && mainNav) {
  navToggle.addEventListener("click", () => {
    const open = mainNav.classList.toggle("open");
    navToggle.setAttribute("aria-expanded", String(open));
  });
}

const heroSearch = document.querySelector("#hero-search");
if (heroSearch) {
  heroSearch.addEventListener("submit", (event) => {
    event.preventDefault();
    const riotId = document.querySelector("#hero-riot-id").value.trim();
    if (!riotId.includes("#")) {
      document.querySelector("#hero-riot-id").setCustomValidity("게임이름#태그 형식으로 입력하세요.");
      document.querySelector("#hero-riot-id").reportValidity();
      return;
    }
    window.location.href = `/analysis?riot_id=${encodeURIComponent(riotId)}&count=10`;
  });
}

const analysisApp = document.querySelector("#analysis-app");

if (analysisApp) {
  const form = document.querySelector("#analysis-search");
  const riotIdInput = document.querySelector("#analysis-riot-id");
  const matchCountInput = document.querySelector("#match-count");

  const escapeHtml = (value) =>
    String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");

  const initials = (value) =>
    value
      .split(/[\s_-]+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0])
      .join("")
      .toUpperCase();

  const setLoading = (loading) => {
    document.querySelector("#loading-state").hidden = !loading;
    document.querySelector("#analysis-results").hidden = loading;
    document.querySelector("#error-state").hidden = true;
    const status = document.querySelector("#analysis-status");
    status.classList.toggle("ready", !loading);
    status.querySelector("span").textContent = loading ? "동기화 중" : "분석 완료";
  };

  const showError = (message) => {
    document.querySelector("#loading-state").hidden = true;
    document.querySelector("#analysis-results").hidden = true;
    document.querySelector("#error-state").hidden = false;
    document.querySelector("#error-message").textContent = message;
    const status = document.querySelector("#analysis-status");
    status.classList.remove("ready");
    status.querySelector("span").textContent = "중단됨";
  };

  const metricCard = (label, value, detail) => `
    <article class="metric-card">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
      <small>${escapeHtml(detail)}</small>
    </article>`;

  const render = (data) => {
    const summary = data.summary;
    const sourceLabels = {
      live: "라이브",
      cache: "캐시",
      "cache-fallback": "캐시 대체",
    };
    document.querySelector("#player-name").textContent = data.riot_id;
    document.querySelector("#analysis-subtitle").textContent =
      `랭크 ${summary.games}경기 · 챔피언 ${summary.champion_pool}개 분석`;
    document.querySelector("#data-source").textContent =
      sourceLabels[data.source] || data.source;
    document.querySelector("#favorite-role").textContent =
      `주 포지션 / ${summary.favorite_role}`;

    document.querySelector("#summary-metrics").innerHTML = [
      metricCard("승률", `${summary.win_rate}%`, `${summary.wins}승 · ${summary.losses}패`),
      metricCard("평균 KDA", summary.avg_kda, "킬과 어시스트 대비 데스"),
      metricCard("분당 CS", summary.avg_cs_min, `평균 CS ${summary.avg_cs}`),
      metricCard("주 포지션", summary.favorite_role, `챔피언 풀 ${summary.champion_pool}개`),
    ].join("");

    document.querySelector("#benchmark-cohort").textContent =
      `${data.benchmark.cohort} / ${data.benchmark.sample_games}경기`;
    document.querySelector("#benchmark-disclaimer").textContent =
      `${data.benchmark.disclaimer} 표본 신뢰도: ${data.benchmark.confidence}.`;
    document.querySelector("#player-comparison").innerHTML = data.benchmark.comparisons
      .map((item) => {
        const ratio = item.key === "avg_deaths"
          ? Math.min((item.target / Math.max(item.player, 0.1)) * 100, 100)
          : Math.min((item.player / Math.max(item.target, 0.1)) * 100, 100);
        return `
          <article class="comparison-item ${item.status}">
            <div><span>${escapeHtml(item.label)}</span><b>${item.status === "focus" ? "집중 훈련" : "기준 충족"}</b></div>
            <div class="comparison-values">
              <strong>${item.player}${escapeHtml(item.unit)}</strong>
              <small>나</small>
              <i>→</i>
              <strong>${item.target}${escapeHtml(item.unit)}</strong>
              <small>최상위 티어</small>
            </div>
            <div class="comparison-track"><i style="width:${Math.max(ratio, 4)}%"></i></div>
          </article>`;
      })
      .join("");

    const routine = data.training_plan;
    const routineKey = `rift-routine:${data.riot_id.toLowerCase()}`;
    let routineState = { completed: {}, startedAt: new Date().toISOString() };
    try {
      const saved = JSON.parse(localStorage.getItem(routineKey) || "null");
      if (Array.isArray(saved)) {
        saved.forEach((day) => { routineState.completed[day] = null; });
      } else if (saved && typeof saved === "object") {
        routineState = { ...routineState, ...saved, completed: saved.completed || {} };
      }
    } catch (_) {
      routineState = { completed: {}, startedAt: new Date().toISOString() };
    }
    const saveRoutine = () => localStorage.setItem(routineKey, JSON.stringify(routineState));
    const completedDays = () => Object.keys(routineState.completed).map(Number).sort((a, b) => a - b);
    const completedAt = (day) => {
      const stamp = routineState.completed[day];
      if (!stamp) return "완료";
      return `${new Intl.DateTimeFormat("ko-KR", { month: "long", day: "numeric", hour: "numeric", minute: "2-digit" }).format(new Date(stamp))} 완료`;
    };
    const updateRoutineState = () => {
      const completed = completedDays();
      const total = routine.schedule.length;
      const percent = Math.round((completed.length / total) * 100);
      let streak = 0;
      while (completed.includes(streak + 1)) streak += 1;
      const next = routine.schedule.find((day) => !completed.includes(day.day));

      document.querySelector("#routine-progress").textContent =
        `${completed.length} / ${total} 완료`;
      document.querySelector("#routine-progress-fill").style.width = `${percent}%`;
      document.querySelector("#routine-percent").textContent = `${percent}%`;
      document.querySelector("#routine-streak").textContent = `${streak}일`;
      document.querySelector("#routine-retest").textContent = completed.length === total ? "준비 완료" : `${total - completed.length}일`;
      document.querySelector("#next-session").hidden = !next;
      document.querySelector("#routine-celebration").hidden = Boolean(next);

      if (next) {
        document.querySelector("#next-session-kicker").textContent = `${next.day}일 차 · 오늘의 훈련`;
        document.querySelector("#next-session-task").textContent = next.task;
        document.querySelector("#next-session-detail").textContent = next.detail;
      }
      document.querySelectorAll(".routine-day").forEach((card) => {
        const day = Number(card.querySelector("input").dataset.routineDay);
        const isComplete = completed.includes(day);
        card.classList.toggle("complete", isComplete);
        card.classList.toggle("current", Boolean(next) && next.day === day);
        card.querySelector(".day-completed-at").textContent = isComplete ? completedAt(day) : "";
      });
    };
    document.querySelector("#routine-title").textContent = routine.title;
    document.querySelector("#routine-role").textContent = routine.primary_role;
    document.querySelector("#routine-pick").textContent = routine.primary_pick;
    document.querySelector("#focus-areas").innerHTML = routine.focus_areas
      .map((item) => `
        <article class="focus-item">
          <span>우선순위 ${item.priority}</span>
          <strong>${escapeHtml(item.title)}</strong>
          <p>${escapeHtml(item.goal)}</p>
        </article>`)
      .join("");
    document.querySelector("#routine-days").innerHTML = routine.schedule
      .map((day) => {
        const complete = completedDays().includes(day.day);
        return `
        <label class="routine-day ${complete ? "complete" : ""}">
          <input type="checkbox" data-routine-day="${day.day}" ${complete ? "checked" : ""}>
          <span class="day-index">${String(day.day).padStart(2, "0")}</span>
          <span class="day-copy"><strong>${escapeHtml(day.task)}</strong><small>${escapeHtml(day.detail)}</small><em class="day-completed-at">${complete ? completedAt(day.day) : ""}</em></span>
          <span class="day-check">✓</span>
        </label>`;
      })
      .join("");
    document.querySelectorAll("[data-routine-day]").forEach((input) => {
      input.addEventListener("change", () => {
        const day = Number(input.dataset.routineDay);
        if (input.checked) routineState.completed[day] = new Date().toISOString();
        else delete routineState.completed[day];
        saveRoutine();
        updateRoutineState();
      });
    });
    document.querySelector("#complete-next-session").onclick = () => {
      const next = routine.schedule.find((day) => !completedDays().includes(day.day));
      document.querySelector(`[data-routine-day="${next?.day}"]`)?.click();
    };
    document.querySelector("#routine-reanalyze").onclick = () => {
      routineState.retestedAt = new Date().toISOString();
      saveRoutine();
      loadAnalysis(data.riot_id, summary.games, true);
    };
    saveRoutine();
    updateRoutineState();

    document.querySelector("#role-bars").innerHTML = data.roles
      .map(
        (role) => `
        <div class="role-row">
          <span class="role-name">${escapeHtml(role.role)}</span>
          <div class="role-track"><i style="width:${Math.max(role.share, 3)}%"></i></div>
          <span class="role-value">${role.share}%</span>
        </div>`
      )
      .join("");

    document.querySelector("#recommendations").innerHTML = data.recommendations
      .map(
        (pick, index) => `
        <div class="recommendation-item">
          <span class="rank">${String(index + 1).padStart(2, "0")}</span>
          <div>
            <strong>${escapeHtml(pick.champion)}</strong>
            <small>${escapeHtml(pick.signal)} · ${pick.avg_kda} KDA</small>
          </div>
          <b>${pick.win_rate}%</b>
        </div>`
      )
      .join("");

    document.querySelector("#champion-count").textContent =
      `${data.champions.length}개 픽`;
    document.querySelector("#champion-table").innerHTML = data.champions
      .map(
        (champion) => `
        <tr>
          <td>
            <div class="champion-cell">
              <span class="champion-initial">${escapeHtml(initials(champion.champion))}</span>
              ${escapeHtml(champion.champion)}
            </div>
          </td>
          <td>${champion.games}</td>
          <td class="${champion.win_rate >= 50 ? "winrate-good" : "winrate-low"}">${champion.win_rate}%</td>
          <td>${champion.avg_kda}</td>
          <td>${champion.avg_cs}</td>
        </tr>`
      )
      .join("");

    document.querySelector("#recent-matches").innerHTML = data.recent_matches
      .map(
        (match) => `
        <article class="match-item ${match.win ? "win" : "loss"}">
          <i class="match-result"></i>
          <strong>${escapeHtml(match.champion)}</strong>
          <span>${escapeHtml(match.role)}</span>
          <span class="match-score">${escapeHtml(match.score)}</span>
          <span>${match.duration}분</span>
        </article>`
      )
      .join("");
  };

  const loadAnalysis = async (riotId, matchCount, refresh = false) => {
    setLoading(true);
    try {
      const response = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          riot_id: riotId,
          match_count: Number(matchCount),
          refresh,
        }),
      });
      const payload = await response.json();
      if (!response.ok) {
        const detail = typeof payload.detail === "string"
          ? payload.detail
          : "입력값을 확인한 뒤 다시 시도해 주세요.";
        throw new Error(detail);
      }
      render(payload);
      setLoading(false);
    } catch (error) {
      showError(error.message);
    }
  };

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const riotId = riotIdInput.value.trim();
    if (!riotId.includes("#")) {
      riotIdInput.setCustomValidity("게임이름#태그 형식으로 입력하세요.");
      riotIdInput.reportValidity();
      return;
    }
    riotIdInput.setCustomValidity("");
    const count = matchCountInput.value;
    window.history.replaceState({}, "", `/analysis?riot_id=${encodeURIComponent(riotId)}&count=${count}`);
    loadAnalysis(riotId, count, true);
  });

  loadAnalysis(analysisApp.dataset.riotId, analysisApp.dataset.count);
}
