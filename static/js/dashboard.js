// static/js/dashboard.js
import { CATEGORY_MAP, CATEGORY_COLORS, formatCurrency, formatMonth } from './utils.js';

// Chart 인스턴스 보관 (재렌더링 시 .destroy() 후 재생성)
let categoryChartInstance   = null;
let dailyChartInstance      = null;
let comparisonChartInstance = null;
let monthlyChartInstance    = null;

// 차트 색은 style.css의 토큰에서 읽는다. 여기에 hex를 따로 적으면 테마를 바꿀 때 차트만 옛 색으로 남는다.
function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

// Chart.js 기본 글자색은 회색(#666)이라 어두운 배경에서 축 글자가 거의 안 보인다. 모든 차트에 한 번 적용한다.
Chart.defaults.color       = cssVar('--color-text-sub');
Chart.defaults.borderColor = cssVar('--chart-grid');
Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
Chart.defaults.plugins.tooltip.backgroundColor = cssVar('--color-surface-raised');
Chart.defaults.plugins.tooltip.borderColor     = cssVar('--color-border');
Chart.defaults.plugins.tooltip.borderWidth     = 1;
Chart.defaults.plugins.tooltip.titleColor      = cssVar('--color-text');
Chart.defaults.plugins.tooltip.bodyColor       = cssVar('--color-text');
Chart.defaults.plugins.tooltip.padding         = 12;
Chart.defaults.plugins.tooltip.cornerRadius    = 8;

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
        // 조각 사이 틈을 카드 배경색으로 그려야 조각이 떨어져 보인다
        borderWidth: 3,
        borderColor: cssVar('--color-surface'),
        hoverOffset: 6,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '68%',  // 고리를 얇게 해서 무게감을 줄인다
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
        borderColor: cssVar('--color-primary'),
        // 선 아래를 위→아래로 옅어지게 채운다. 영역 크기는 그릴 때 정해져서 함수로 넘긴다.
        backgroundColor: ({ chart }) => {
          const { ctx: c, chartArea } = chart;
          if (!chartArea) return 'transparent';
          const gradient = c.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
          gradient.addColorStop(0, cssVar('--chart-dim-bar'));
          gradient.addColorStop(1, 'transparent');
          return gradient;
        },
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
          grid: { color: cssVar('--chart-grid') },
          ticks: { callback: formatWonTick },
        },
      },
    },
  });
}

// =========================================
// 월별 추이 막대 차트 (대시보드 탭)
// =========================================
// monthlyTotals: [{ month: 'YYYY-MM', total: 352000 }, ...] 오래된 달부터, 마지막이 선택한 달
function renderMonthlyChart(monthlyTotals) {
  const ctx = document.querySelector('#monthly-chart').getContext('2d');

  if (monthlyChartInstance) {
    monthlyChartInstance.destroy();
    monthlyChartInstance = null;
  }

  const lastIndex = monthlyTotals.length - 1;
  // 선택한 달만 주색으로 칠해 "지금 보고 있는 달"이 어디인지 바로 보이게 한다
  const colors = monthlyTotals.map((_, i) => cssVar(i === lastIndex ? '--color-primary' : '--chart-dim-bar'));

  monthlyChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: monthlyTotals.map(m => `${Number(m.month.slice(5))}월`),
      datasets: [{
        label: '월 지출',
        data: monthlyTotals.map(m => m.total),
        backgroundColor: colors,
        borderRadius: 4,
        maxBarThickness: 40,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            // 막대 라벨은 '10월'뿐이라 해가 바뀌는 구간에서 헷갈리지 않게 툴팁에는 연도까지 쓴다
            title: items => formatMonth(monthlyTotals[items[0].dataIndex].month),
            label: ctx => ` ${formatCurrency(ctx.parsed.y)}`,
          },
        },
      },
      scales: {
        x: {
          grid: { display: false },
        },
        y: {
          beginAtZero: true,
          grid: { color: cssVar('--chart-grid') },
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
          backgroundColor: cssVar('--color-primary'),
          borderRadius: 4,
        },
        {
          label: '또래 평균',
          data: peerData,
          backgroundColor: cssVar('--chart-muted-bar'),
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
          grid: { color: cssVar('--chart-grid') },
          ticks: {
            callback: val => `${(val / 10000).toFixed(0)}만`,
          },
        },
      },
    },
  });
}

export { renderCategoryChart, renderDailyChart, renderMonthlyChart, renderComparisonChart };
