// static/js/dashboard.js
import { CATEGORY_MAP, CATEGORY_COLORS, formatCurrency } from './utils.js';

// Chart 인스턴스 보관 (재렌더링 시 .destroy() 후 재생성)
let categoryChartInstance   = null;
let dailyChartInstance      = null;
let comparisonChartInstance = null;

// =========================================
// 카테고리별 도넛 차트 (대시보드 탭)
// =========================================
function renderCategoryChart(byCategoryData) {
  const ctx = document.querySelector('#category-chart').getContext('2d');

  if (categoryChartInstance) {
    categoryChartInstance.destroy();
    categoryChartInstance = null;
  }

  const keys   = Object.keys(CATEGORY_MAP);
  const labels = keys.map(k => `${CATEGORY_MAP[k].icon} ${CATEGORY_MAP[k].label}`);
  const data   = keys.map(k => byCategoryData[k] || 0);

  categoryChartInstance = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{
        data,
        backgroundColor: CATEGORY_COLORS,
        borderWidth: 2,
        borderColor: '#fff',
        hoverOffset: 6,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'bottom',
          labels: {
            font: { size: 12 },
            padding: 12,
            usePointStyle: true,
          },
        },
        tooltip: {
          callbacks: {
            label: ctx => ` ${formatCurrency(ctx.parsed)}`,
          },
        },
      },
    },
  });
}

// =========================================
// 일별 누적 라인 차트 (대시보드 탭)
// =========================================
// 지출이 없는 날도 채워서 1일부터 누적한다. 쓴 날만 이으면 "이번 달 얼마나 빨리 쓰고 있는지"가 안 보인다.
// 이번 달은 오늘까지만 그린다 (미래 날짜를 평평하게 그리면 앞으로도 안 쓸 것처럼 읽힌다).
function buildCumulativeSeries(byDateData, month) {
  const [year, mon]  = month.split('-').map(Number);
  const daysInMonth  = new Date(year, mon, 0).getDate();
  const amountByDay  = new Map(byDateData.map(d => [Number(d.date.slice(8, 10)), d.amount]));

  const today          = new Date();
  const isCurrentMonth = today.getFullYear() === year && today.getMonth() + 1 === mon;
  // 오늘 이후 날짜로 저장된 거래가 있어도 총액과 어긋나지 않게 그날까지는 그린다
  const lastDataDay = Math.max(0, ...amountByDay.keys());
  const lastDay     = isCurrentMonth ? Math.max(today.getDate(), lastDataDay) : daysInMonth;

  const labels = [];
  const data   = [];
  let sum = 0;

  for (let day = 1; day <= lastDay; day++) {
    sum += amountByDay.get(day) || 0;
    labels.push(`${day}일`);
    data.push(sum);
  }

  return { labels, data };
}

// 1만 원 미만은 그대로, 이상은 '1.5만'처럼 줄인다 (작은 금액이 '0만'으로 겹쳐 보이지 않게)
function formatWonTick(val) {
  return val >= 10000 ? `${Number((val / 10000).toFixed(1))}만` : val.toLocaleString('ko-KR');
}

function renderDailyChart(byDateData, month) {
  const ctx = document.querySelector('#daily-chart').getContext('2d');

  if (dailyChartInstance) {
    dailyChartInstance.destroy();
    dailyChartInstance = null;
  }

  const { labels, data } = buildCumulativeSeries(byDateData, month);

  dailyChartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: '누적 지출',
        data,
        borderColor: '#4F46E5',
        backgroundColor: 'rgba(79, 70, 229, 0.1)',
        borderWidth: 2,
        fill: true,
        // 누적값은 줄어들지 않는다. 일반 곡선은 계단 앞뒤에서 아래·위로 튀어나와 금액이 줄어든 것처럼 보인다.
        cubicInterpolationMode: 'monotone',
        pointRadius: 0,
        pointHoverRadius: 4,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: ctx => ` 누적 ${formatCurrency(ctx.parsed.y)}`,
          },
        },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { maxTicksLimit: 8 },
        },
        y: {
          beginAtZero: true,
          grid: { color: '#F3F4F6' },
          ticks: { callback: formatWonTick },
        },
      },
    },
  });
}

// =========================================
// 또래 비교 가로 막대 차트 (AI 분석 탭)
// =========================================
function renderComparisonChart(byCategoryData) {
  const ctx = document.querySelector('#comparison-chart').getContext('2d');

  if (comparisonChartInstance) {
    comparisonChartInstance.destroy();
    comparisonChartInstance = null;
  }

  const keys     = Object.keys(CATEGORY_MAP);
  const labels   = keys.map(k => `${CATEGORY_MAP[k].icon} ${CATEGORY_MAP[k].label}`);
  const userData = keys.map(k => byCategoryData[k]?.user     || 0);
  const peerData = keys.map(k => byCategoryData[k]?.peer_avg || 0);

  comparisonChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: '내 지출',
          data: userData,
          backgroundColor: '#4F46E5',
          borderRadius: 4,
        },
        {
          label: '또래 평균',
          data: peerData,
          backgroundColor: '#E5E7EB',
          borderRadius: 4,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'top',
          labels: {
            usePointStyle: true,
            font: { size: 12 },
          },
        },
        tooltip: {
          callbacks: {
            label: ctx => ` ${ctx.dataset.label}: ${formatCurrency(ctx.parsed.y)}`,
          },
        },
      },
      scales: {
        x: {
          grid: { display: false },
        },
        y: {
          grid: { color: '#F3F4F6' },
          ticks: {
            callback: val => `${(val / 10000).toFixed(0)}만`,
          },
        },
      },
    },
  });
}

export { renderCategoryChart, renderDailyChart, renderComparisonChart };
